import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import context_pack


class ContextPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.store = self.root / "store"
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "Test")
        (self.project / "billing.py").write_text(
            "from prices import calculate_total\n\ndef bill(items):\n    return calculate_total(items)\n")
        (self.project / "prices.py").write_bytes(
            b'def calculate_total(items):\r\n    # ```` and "snow" \xe9\x9b\xaa\r\n'
            b'    return sum(items)')
        (self.project / "calendar.py").write_text("def render_calendar():\n    return []\n")
        self._git("add", ".")
        self._git("commit", "-qm", "fixture")
        with (self.project / "prices.py").open("ab") as stream:
            stream.write(b"\r\n# already dirty")
        self.service = context_pack.ContextPackService(
            self.project, store=self.store,
            context_root=Path(__file__).resolve().parents[1], project_id="synthetic")

    def tearDown(self):
        self.temp.cleanup()

    def _git(self, *args):
        subprocess.run(["git", "-C", str(self.project), *args], check=True)

    def test_candidates_preview_export_restart_and_drift(self):
        candidates = self.service.candidates("change total pricing",
                                             guidance_ids=["guidance:core/testing.md"])
        src = [x for x in candidates["items"] if x["kind"] == "source"]
        pricing = next(x for x in src if x["title"] == "prices.py")
        self.assertIn("calculate_total", pricing["content"])
        self.assertIn("\r\n", pricing["content"])
        self.assertFalse(pricing["content"].endswith("\n"))
        self.assertFalse(any(x["title"] == "calendar.py" for x in src))
        preview = self.service.preview(candidates["candidate_set_id"], max_tokens=8192)
        self.assertIn("`````", preview["renders"]["text"]["content"])
        for fmt in ("text", "json"):
            expected = preview["renders"][fmt]
            self.assertLessEqual(expected["bytes"], 4 * 8192)
            self.assertTrue(expected["content"].endswith("\n"))
            actual = self.service.export(preview["preview_id"], format=fmt)
            self.assertEqual(actual, expected["content"].encode())
        reopened = context_pack.ContextPackService(
            self.project, store=self.store, context_root=self.service.context_root,
            project_id="synthetic")
        self.assertEqual(reopened.export(preview["preview_id"], format="json"),
                         preview["renders"]["json"]["content"].encode())
        code = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); import context_pack; "
            "s=context_pack.ContextPackService(Path(sys.argv[2]), store=Path(sys.argv[3]), "
            "context_root=Path(sys.argv[1]).parent, project_id='synthetic'); "
            "sys.stdout.buffer.write(s.export(sys.argv[4], format='text'))"
        )
        out = subprocess.check_output([
            "/Users/pradeeptathineni/code/personal/ai-systems/context-ai/.venv/bin/python",
            "-B", "-c", code, str(Path(__file__).resolve().parents[1] / "scripts"),
            str(self.project), str(self.store), preview["preview_id"]])
        self.assertEqual(out, preview["renders"]["text"]["content"].encode())
        source_id = next(x["item_id"] for x in src)
        smaller = reopened.preview(candidates["candidate_set_id"], include_ids=[source_id],
                                   max_tokens=8192)
        self.assertNotEqual(smaller["preview_id"], preview["preview_id"])
        self.assertEqual(reopened.export(preview["preview_id"]),
                         preview["renders"]["text"]["content"].encode())
        with (self.project / "prices.py").open("a") as stream:
            stream.write("# same dirty status\n")
        with self.assertRaises(context_pack.ContextPackError) as error:
            reopened.export(preview["preview_id"])
        self.assertEqual(error.exception.code, "source_drift")

    def test_fence_adaptation_and_budget(self):
        body = "before\n````\n雪\n"
        fence = context_pack._fence(body)
        self.assertEqual(len(fence), 5)
        candidate = self.service.candidates("pricing", focus=["prices.py"])
        item_id = next(x["item_id"] for x in candidate["items"] if x["kind"] == "source")
        with self.assertRaises(context_pack.ContextPackError) as error:
            self.service.preview(candidate["candidate_set_id"], include_ids=[item_id], max_tokens=1)
        self.assertEqual(error.exception.code, "budget_too_small")

    def test_cli_candidates_preview_export(self):
        cli = Path(__file__).resolve().parents[1] / "scripts" / "context_pack.py"
        base = ["/Users/pradeeptathineni/code/personal/ai-systems/context-ai/.venv/bin/python",
                "-B", str(cli)]
        common = ["--project", str(self.project), "--store", str(self.store),
                  "--context-root", str(Path(__file__).resolve().parents[1]),
                  "--project-id", "synthetic"]
        raw = subprocess.check_output(base + ["candidates"] + common + [
            "--task", "change total pricing", "--guidance", "guidance:core/testing.md"])
        candidates = json.loads(raw)
        raw_preview = subprocess.check_output(base + ["preview"] + common + [
            "--candidates", candidates["candidate_set_id"], "--max-tokens", "8192", "--format", "json"])
        preview = json.loads(raw_preview)
        exported = subprocess.check_output(base + ["export"] + common + [
            "--preview", preview["preview_id"], "--format", "json"])
        self.assertEqual(exported, raw_preview)


if __name__ == "__main__":
    unittest.main()
