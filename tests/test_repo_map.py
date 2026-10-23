import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.repo_map import MapError, build_map, render_text


REPO = Path(__file__).resolve().parents[1]


class RepoMapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "map-test@example.invalid")
        self.git("config", "user.name", "Map Test")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def add(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")

    def test_rank_symbols_focus_and_digest(self):
        self.add("billing.py", "from prices import calculate_total\n\ndef invoice(items):\n    return calculate_total(items)\n")
        prices = self.add("prices.py", "def calculate_total(items):\n    return sum(items)\n")
        self.add("unrelated.py", "def render_calendar():\n    return []\n")
        self.commit()

        result = build_map(self.root, "change total pricing", max_tokens=200)
        paths = {entry["path"] for entry in result["entries"]}
        self.assertIn("prices.py", paths)
        self.assertIn("billing.py", paths)
        self.assertNotIn("unrelated.py", paths)
        price_entry = next(entry for entry in result["entries"] if entry["path"] == "prices.py")
        self.assertEqual(price_entry["file_sha256"], __import__("hashlib").sha256(prices.read_bytes()).hexdigest())
        self.assertEqual(price_entry["symbols"][0]["line"], 1)
        self.assertIn("explicitly focused path", build_map(self.root, "change total pricing", focus=["unrelated.py"])["entries"][0]["reason"])

    def test_dirty_bytes_are_bound_and_ast_lines_preserved(self):
        target = self.add("module.py", "class Price:\n    def total(self):\n        def nested():\n            return 3\n        return nested()\n")
        self.commit()
        original = build_map(self.root, "price total nested")
        original_symbols = original["entries"][0]["symbols"]
        self.assertEqual([(s["name"], s["line"]) for s in original_symbols], [("Price", 1), ("total", 2), ("nested", 3)])
        target.write_text("class Price:\n    def total(self):\n        return 4\n", encoding="utf-8")
        result = build_map(self.root, "price total")
        self.assertTrue(result["dirty"])
        entry = result["entries"][0]
        self.assertEqual(entry["file_sha256"], __import__("hashlib").sha256(target.read_bytes()).hexdigest())
        self.assertEqual([(s["name"], s["line"]) for s in entry["symbols"]], [("Price", 1), ("total", 2)])

    def test_malformed_python_and_sensitive_paths_are_reported_as_skipped(self):
        self.add("broken.py", "def bad(:\n")
        self.add(".env", "SECRET=value\n")
        self.add("ok.py", "def payment_total():\n    return 1\n")
        self.commit()
        result = build_map(self.root, "payment total")
        self.assertEqual([entry["path"] for entry in result["entries"]], ["ok.py"])
        self.assertGreaterEqual(result["diagnostics"]["skipped_files"], 2)
        self.assertTrue(any("malformed Python" in item for item in result["diagnostics"]["warnings"]))

    def test_invalid_focus_and_small_budget(self):
        self.add("pricing.py", "def pricing_total():\n    return 1\n")
        self.commit()
        with self.assertRaises(MapError):
            build_map(self.root, "pricing", focus=["../outside"])
        result = build_map(self.root, "pricing", max_tokens=1)
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["diagnostics"]["omitted_files"], 1)
        self.assertIn("No matching files", render_text(result))

    def test_cli_text_and_json(self):
        self.add("prices.py", "def pricing_total():\n    return 1\n")
        self.commit()
        command = [sys.executable, str(REPO / "scripts/repo_map.py"), "--project", str(self.root), "--task", "pricing total"]
        text = subprocess.run(command, check=True, capture_output=True, text=True).stdout
        data = subprocess.run(command + ["--format", "json"], check=True, capture_output=True, text=True).stdout
        self.assertIn("prices.py", text)
        self.assertEqual(json.loads(data)["schema"], "context-ai/repo-map/v1")

    @unittest.skipIf(os.name == "nt", "symlink permissions vary on Windows")
    def test_focus_refuses_symlink(self):
        self.add("real.py", "def payment_total():\n    return 1\n")
        self.commit()
        (self.root / "link.py").symlink_to("real.py")
        self.git("add", "link.py")
        self.git("commit", "-qm", "symlink")
        with self.assertRaisesRegex(MapError, "symlink"):
            build_map(self.root, "payment", focus=["link.py"])

    def test_limits_unicode_and_empty_match(self):
        self.add("unicode.py", "def café_total():\n    return '東京'\n")
        self.add("large.py", "# " + "x" * 256_001)
        self.add(".env", "SECRET=value\n")
        self.commit()
        result = build_map(self.root, "café total")
        self.assertEqual([entry["path"] for entry in result["entries"]], ["unicode.py"])
        self.assertTrue(any("exceeds" in item for item in result["diagnostics"]["warnings"]))
        empty = build_map(self.root, "no matching identifier")
        self.assertEqual(empty["entries"], [])
        self.assertIn("No matching files", render_text(empty))


if __name__ == "__main__":
    unittest.main()
