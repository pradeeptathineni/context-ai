# tests/test_word_limit.py - Exercise delivered-byte boundaries and repair invalidation


import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WordLimit(unittest.TestCase):
    """Exercise the real CLI on saved output files."""
    def setUp(self):
        """Keep each saved sample in a separate temporary folder."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.artifact = Path(self.temporary.name) / "answer.md"

    def check(self, option, limit):
        """Run the checker on the saved sample.

        Args:
            option: Inclusive or strict word-limit CLI flag.
            limit: Word bound to pass to the CLI.

        Returns:
            Completed process with captured output and exit status.
        """
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/check_word_limit.py"),
                str(self.artifact),
                option,
                str(limit),
            ],
            capture_output=True,
            text=True,
        )

    def test_exact_boundary(self):
        """Distinguish strictly under from at most at the exact boundary."""
        self.artifact.write_text("word " * 120)
        self.assertEqual(self.check("--under-words", 120).returncode, 1)
        self.assertEqual(self.check("--max-words", 120).returncode, 0)

    def test_repair_then_edit(self):
        """Reject excess words, accept repair, then reject a later edit."""
        receipts = []
        for body, expected in [
            ("one two three", 1),
            ("one two", 0),
            ("one two three four", 1),
        ]:
            self.artifact.write_text(body)
            result = self.check("--max-words", 2)
            self.assertEqual(result.returncode, expected)
            receipt = json.loads(result.stdout)
            self.assertEqual(
                receipt["sha256"], hashlib.sha256(self.artifact.read_bytes()).hexdigest()
            )
            self.assertEqual(self.artifact.read_text(), body)
            receipts.append(receipt)
        self.assertNotEqual(receipts[1]["sha256"], receipts[2]["sha256"])

    def test_whole_markdown(self):
        """Count the complete Markdown and Unicode whitespace."""
        self.artifact.write_text("# Title\n\n```sh\nprintf café\u2003deux\n```\n")
        result = self.check("--max-words", 6)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["words"], 7)

    def test_invalid_input(self):
        """Reject missing and invalid UTF-8 files."""
        self.assertEqual(self.check("--max-words", 100).returncode, 2)
        self.artifact.write_bytes(b"\xff")
        self.assertEqual(self.check("--max-words", 100).returncode, 2)
