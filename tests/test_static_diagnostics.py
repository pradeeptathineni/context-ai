import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import static_diagnostics


NODE = os.environ.get("CONTEXT_CODE_NAV_NODE") or "/Users/pradeeptathineni/.nvm/versions/node/v24.19.0/bin/node"
TYPESCRIPT = os.environ.get("CONTEXT_TYPESCRIPT_PATH") or "/Users/pradeeptathineni/.admin/Codex/2026-10-20/task-3/deep-program-wave1/node_modules/typescript/lib/typescript.js"


class StaticDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        if not Path(NODE).is_file() or not Path(TYPESCRIPT).is_file():
            self.skipTest("uses existing configured Node 24 and TypeScript 6 installations; never installs dependencies")
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "diagnostics@example.invalid")
        self.git("config", "user.name", "Diagnostics Test")
        (self.root / "src").mkdir()
        (self.root / "src/broken.ts").write_text("export const value: = 3;\n", encoding="utf-8")
        (self.root / "src/broken.py").write_text('label = "😀"\nif "😀" print(label)\n', encoding="utf-8")
        (self.root / "src/unknown.rs").write_text("fn main() {}\n", encoding="utf-8")
        (self.root / "src/must_not_run.js").write_text(
            'require("fs").writeFileSync("execution-marker", "ran");\nconst value = ;\n', encoding="utf-8"
        )
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def analyze(self):
        return static_diagnostics.analyze_project(
            self.root, node_executable=NODE, typescript_path=TYPESCRIPT
        )

    def test_mixed_syntax_partial_unknown_hashes_and_fixed_bytes(self):
        with patch.object(static_diagnostics, "MAX_DIAGNOSTICS", 2):
            first = self.analyze()
        self.assertEqual(first["schema"], "context.static-diagnostics.v1")
        self.assertTrue(first["stable"])
        self.assertEqual(first["status"], "partial")
        files = {row["path"]: row for row in first["files"]}
        self.assertEqual(files["src/unknown.rs"]["status"], "unsupported")
        self.assertEqual(files["src/broken.ts"]["status"], "analyzed")
        self.assertEqual(files["src/broken.py"]["status"], "analyzed")
        by_code = {item["code"]: item for row in files.values() for item in row["diagnostics"]}
        diagnostic_coverage = first["coverage"]["diagnostics"]
        self.assertEqual(diagnostic_coverage["total"], sum(row["diagnostic_total"] for row in files.values()))
        self.assertEqual(diagnostic_coverage["returned"], sum(len(row["diagnostics"]) for row in files.values()))
        self.assertEqual(diagnostic_coverage["omitted"], diagnostic_coverage["total"] - diagnostic_coverage["returned"])
        self.assertEqual(diagnostic_coverage["returned"], 2)
        self.assertEqual(diagnostic_coverage["omitted"], 1)
        for row in files.values():
            self.assertLessEqual(len(row["diagnostics"]), row["diagnostic_total"])
        self.assertTrue(any(code.startswith("TS") for code in by_code))
        python = by_code["PY-SYNTAX"]
        self.assertEqual(python["range"]["start"]["line"], 2)
        self.assertEqual(python["range"]["start"]["column"], 9)
        self.assertNotIn("label", json.dumps(first))  # responses contain no source excerpts
        self.assertFalse((self.root / "execution-marker").exists())
        for row in first["files"]:
            if row["sha256"]:
                self.assertEqual(row["sha256"], hashlib.sha256((self.root / row["path"]).read_bytes()).hexdigest())
            for item in row["diagnostics"]:
                self.assertEqual(item["fileSha256"], row["sha256"])
                self.assertEqual(item["diagnosticId"], static_diagnostics._diagnostic_id(
                    item["path"], item["fileSha256"], item["code"], item["severity"], item["range"]
                ))

        (self.root / "src/broken.py").write_text('label = "😀"\nprint(label)\n', encoding="utf-8")
        (self.root / "src/broken.ts").write_text("export const value: number = 3;\n", encoding="utf-8")
        second = self.analyze()
        self.assertTrue(second["snapshot"]["dirty"])
        self.assertNotEqual(first["source_digest"], second["source_digest"])
        self.assertNotEqual(first["snapshot"]["id"], second["snapshot"]["id"])
        fixed_row = second["files"][[row["path"] for row in second["files"]].index("src/broken.py")]
        self.assertEqual(fixed_row["sha256"], hashlib.sha256((self.root / "src/broken.py").read_bytes()).hexdigest())
        self.assertEqual(fixed_row["diagnostics"], [])
        self.assertFalse((self.root / "execution-marker").exists())

    def test_source_edit_during_worker_is_rejected_as_stale(self):
        source = self.root / "src/broken.py"
        original = static_diagnostics.code_navigation._run_worker

        def run_then_edit(*args, **kwargs):
            reply = original(*args, **kwargs)
            source.write_text("print('changed')\n", encoding="utf-8")
            return reply

        with patch.object(static_diagnostics.code_navigation, "_run_worker", side_effect=run_then_edit):
            with self.assertRaises(static_diagnostics.StaticDiagnosticsError) as caught:
                self.analyze()
        self.assertEqual(caught.exception.kind, "stale_snapshot")


if __name__ == "__main__":
    unittest.main()
