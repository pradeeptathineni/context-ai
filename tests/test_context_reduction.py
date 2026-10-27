import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import context_pack


class ReductionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.store = self.root / "store"
        self._git("init", "-q")
        self._git("config", "user.email", "fixture@example.invalid")
        self._git("config", "user.name", "Fixture")
        self.path = self.project / "events.py"
        self.path.write_text("initial\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-qm", "fixture")
        self.service = context_pack.ContextPackService(
            self.project, store=self.store,
            context_root=Path(__file__).resolve().parents[1], project_id="synthetic")

    def tearDown(self):
        self.temp.cleanup()

    def _git(self, *args):
        subprocess.run(["git", "-C", str(self.project), *args], check=True)

    def _reduce(self, content, *, max_lines=12, guidance=False, protected_lines=()):
        self.path.write_bytes(content.encode("utf-8"))
        candidates = self.service.candidates(
            "inspect synthetic events", focus=["events.py"],
            guidance_ids=["guidance:core/testing.md"] if guidance else [],
            representation="full")
        source = next(row for row in candidates["items"] if row["kind"] == "source")
        preview = self.service.preview(candidates["candidate_set_id"],
                                       include_ids=[source["item_id"]], max_tokens=8192)
        result = context_pack.preview_pack_reduction(
            self.service, preview["preview_id"], source["item_id"], max_lines,
            protected_lines=protected_lines)
        return candidates, source, preview, result

    def test_exact_unicode_crlf_partition_determinism_and_priority(self):
        lines = [f"row {index} 雪\r\n" for index in range(70)]
        lines[20] = "ERROR could not load 雪\r\n"
        lines[21] = "WARN retrying\r\n"
        original = "".join(lines)
        _, source, pack, first = self._reduce(original, max_lines=12)
        second = context_pack.preview_pack_reduction(
            self.service, pack["preview_id"], source["item_id"], 12)
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], "context-ai/reduction-preview/v1")
        self.assertEqual(first["method"], "log-line-select-v1")
        self.assertEqual(first["offset_unit"], "unicode-codepoints")
        cursor = 0
        rebuilt = []
        selected = []
        for segment in first["segments"]:
            self.assertEqual(segment["start"], cursor)
            self.assertEqual(original[segment["start"]:segment["end"]], segment["text"])
            cursor = segment["end"]
            rebuilt.append(segment["text"])
            if segment["disposition"] == "kept":
                selected.append(segment["text"])
        self.assertEqual(cursor, len(original))
        self.assertEqual("".join(rebuilt), original)
        self.assertEqual("".join(selected), first["projected_text"])
        self.assertIn("ERROR could not load 雪", first["projected_text"])
        self.assertIn("WARN retrying", first["projected_text"])
        self.assertEqual(first["source_ref"]["raw_sha256"], hashlib.sha256(original.encode()).hexdigest())
        self.assertEqual(first["preview_id"], hashlib.sha256(
            context_pack._json({k: v for k, v in first.items() if k != "preview_id"}).encode()).hexdigest())
        self.assertTrue(first["estimate"]["is_estimate"])

    def test_error_priority_cap_and_explicit_dropped_warning(self):
        lines = [f"ordinary {index}\n" for index in range(60)]
        for index in range(4, 40):
            lines[index] = f"ERROR failure {index}\n"
        for index in range(40, 55):
            lines[index] = f"WARN retry {index}\n"
        _, _, _, result = self._reduce("".join(lines), max_lines=8)
        self.assertEqual(len(result["projected_text"].splitlines()), 8)
        self.assertIn("error_lines_dropped_by_cap", result["warnings"])
        self.assertIn("warning_lines_dropped_by_cap", result["warnings"])
        self.assertTrue(any(s["disposition"] == "cap-dropped" for s in result["segments"]))
        self.assertLessEqual(result["size"]["after_bytes"], result["size"]["before_bytes"])

    def test_explicit_protected_lines_are_exact_or_block_the_reduction(self):
        lines = [f"ordinary {index}\n" for index in range(60)]
        lines[28] = "Required qualification: this result is preliminary.\n"
        _, _, _, result = self._reduce("".join(lines), max_lines=8, protected_lines=[29])
        self.assertIn(lines[28], result["projected_text"])
        self.assertEqual(result["protected_lines"], [29])
        self.assertTrue(any(row["rule"] == "protected" for row in result["segments"]))
        with self.assertRaises(context_pack.ContextPackError) as error:
            self._reduce("".join(lines), max_lines=8, protected_lines=list(range(3, 12)))
        self.assertEqual(error.exception.code, "protected_content_exceeds_budget")

    def test_protected_line_selection_rejects_invalid_source_ranges(self):
        lines = "".join(f"line {index}\n" for index in range(60))
        with self.assertRaises(context_pack.ContextPackError) as error:
            self._reduce(lines, protected_lines=[61])
        self.assertEqual(error.exception.code, "invalid_request")

    def test_short_input_passthrough_and_empty_input(self):
        _, _, _, short = self._reduce("one\r\ntwo\nthree")
        self.assertEqual(short["projected_text"], "one\r\ntwo\nthree")
        self.assertEqual(short["warnings"], ["source_below_line_floor_passthrough"])
        _, _, _, empty = self._reduce("")
        self.assertEqual(empty["projected_text"], "")
        self.assertEqual(empty["segments"], [])
        self.assertEqual(empty["warnings"], ["empty_source_passthrough"])

    def test_guidance_excerpt_and_stale_source_are_refused(self):
        self.path.write_text("\n".join(f"line {i}" for i in range(60)), encoding="utf-8")
        candidates = self.service.candidates("inspect", focus=["events.py"],
                                             guidance_ids=["guidance:core/testing.md"],
                                             representation="full")
        guidance = next(row for row in candidates["items"] if row["kind"] == "guidance")
        pack = self.service.preview(candidates["candidate_set_id"],
                                    include_ids=[guidance["item_id"]], max_tokens=8192)
        with self.assertRaises(context_pack.ContextPackError) as error:
            context_pack.preview_pack_reduction(self.service, pack["preview_id"], guidance["item_id"])
        self.assertEqual(error.exception.code, "invalid_reduction_source")

        self.path.write_text("def inspect_events():\n" +
                             "".join(f"    # event {i}\n" for i in range(60)) +
                             "    return None\n", encoding="utf-8")
        excerpt_candidates = self.service.candidates("inspect events", focus=["events.py"])
        excerpt = next(row for row in excerpt_candidates["items"] if row["kind"] == "source")
        excerpt_pack = self.service.preview(excerpt_candidates["candidate_set_id"], max_tokens=8192)
        with self.assertRaises(context_pack.ContextPackError) as error:
            context_pack.preview_pack_reduction(self.service, excerpt_pack["preview_id"], excerpt["item_id"])
        self.assertEqual(error.exception.code, "invalid_reduction_source")

        full_candidates = self.service.candidates("inspect", focus=["events.py"], representation="full")
        full = next(row for row in full_candidates["items"] if row["kind"] == "source")
        full_pack = self.service.preview(full_candidates["candidate_set_id"], max_tokens=8192)
        self.path.write_text("changed after preview\n", encoding="utf-8")
        with self.assertRaises(context_pack.ContextPackError) as error:
            context_pack.preview_pack_reduction(self.service, full_pack["preview_id"], full["item_id"])
        self.assertEqual(error.exception.code, "source_drift")

    def test_cli_reduce_emits_preview_without_persisting_reduced_content(self):
        lines = [f"entry {i}\n" for i in range(55)]
        lines[28] = "retain this exact qualification\n"
        content = "".join(lines)
        candidates, source, pack, _ = self._reduce(content)
        cli = Path(__file__).resolve().parents[1] / "scripts" / "context_pack.py"
        raw = subprocess.check_output([
            sys.executable, "-B", str(cli), "reduce", "--project", str(self.project),
            "--store", str(self.store), "--context-root", str(Path(__file__).resolve().parents[1]),
            "--project-id", "synthetic", "--preview", pack["preview_id"],
            "--item", source["item_id"], "--max-lines", "8", "--protect-line", "29"])
        receipt = json.loads(raw)
        self.assertEqual(receipt["schema"], "context-ai/reduction-preview/v1")
        self.assertEqual(receipt["source_ref"]["preview_id"], pack["preview_id"])
        self.assertEqual(receipt["max_lines"], 8)
        self.assertEqual(receipt["protected_lines"], [29])
        self.assertIn("retain this exact qualification", receipt["projected_text"])
        self.assertIn("preview-" + pack["preview_id"] + ".json", [p.name for p in self.store.glob("preview-*.json")])
        self.assertEqual(len(list(self.store.glob("preview-*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
