import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

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
            sys.executable,
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

    def test_rehashed_render_tampering_is_rejected(self):
        candidates = self.service.candidates("change total pricing")
        preview = self.service.preview(candidates["candidate_set_id"], max_tokens=8192)
        path = self.store / ("preview-" + preview["preview_id"] + ".json")
        record = json.loads(path.read_text())
        content = "UNBOUND SYNTHETIC TEXT\n"
        raw = content.encode()
        record["renders"]["text"] = {
            "content": content,
            "bytes": len(raw),
            "sha256": __import__("hashlib").sha256(raw).hexdigest(),
            "estimated_tokens": (len(raw) + 3) // 4,
        }
        path.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")))
        with self.assertRaises(context_pack.ContextPackError) as error:
            self.service.export(preview["preview_id"])
        self.assertEqual(error.exception.code, "store_invalid")

    def test_fence_adaptation_and_budget(self):
        body = "before\n````\n雪\n"
        fence = context_pack._fence(body)
        self.assertEqual(len(fence), 5)
        candidate = self.service.candidates("pricing", focus=["prices.py"])
        item_id = next(x["item_id"] for x in candidate["items"] if x["kind"] == "source")
        with self.assertRaises(context_pack.ContextPackError) as error:
            self.service.preview(candidate["candidate_set_id"], include_ids=[item_id], max_tokens=1)
        self.assertEqual(error.exception.code, "budget_too_small")

    def test_full_and_structural_python_representations_replay_exact_segments(self):
        source = (
            "# Copyright 2026 Fixture Authors\n"
            "# SPDX-License-Identifier: MIT\n"
            '"""Invoice declarations for 雪 handling."""\n'
            "from __future__ import annotations\n"
            "from dataclasses import dataclass\n"
            "\n"
            'LABEL: str = "雪"\n'
            "\n"
            "@audit(\n"
            '    "invoice",\n'
            ")\n"
            "@dataclass\n"
            "class Invoice:\n"
            '    """Public invoice record."""\n'
            "    total: int\n"
            "\n"
            "    @classmethod\n"
            "    async def calculate(\n"
            "        cls, values: list[int], *,\n"
            "        tax: float = 0.0,\n"
            "    ) -> float:\n"
            '        """Calculate the taxed total."""\n'
            "        gross = sum(values)\n"
            "        return gross * (1 + tax)\n"
            "\n"
            "def helper(value: int) -> int:\n"
            "    return value + 1\n"
        )
        raw = source.replace("\n", "\r\n").encode("utf-8").removesuffix(b"\r\n")
        path = self.project / "invoice_api.py"
        path.write_bytes(raw)
        self._git("add", "invoice_api.py")
        self._git("commit", "-qm", "add structural fixture")
        full_candidates = self.service.candidates(
            "inspect invoice declarations", focus=["invoice_api.py"], representation="full")
        full_item = next(item for item in full_candidates["items"] if item["kind"] == "source")
        self.assertEqual(full_item["content"].encode("utf-8"), raw)
        self.assertEqual(full_item["representation"]["selected_bytes"], len(raw))
        self.assertEqual(full_item["representation"]["segments"][0]["line_start"], 1)
        full_preview = self.service.preview(full_candidates["candidate_set_id"], max_tokens=8192)
        self.assertEqual(self.service.export(full_preview["preview_id"], format="json"),
                         full_preview["renders"]["json"]["content"].encode("utf-8"))

        source_raw = raw + b"\r\n# already dirty before structural snapshot"
        path.write_bytes(source_raw)
        candidates = self.service.candidates(
            "inspect invoice declarations", focus=["invoice_api.py"], representation="structure")
        self.assertNotEqual(candidates["candidate_set_id"], full_candidates["candidate_set_id"])
        item = next(row for row in candidates["items"] if row["kind"] == "source")
        representation = item["representation"]
        self.assertEqual(representation["selected"], "structure")
        self.assertEqual(representation["algorithm"], "python-ast-segments-v1")
        self.assertNotIn("line_start", item["source"])
        self.assertNotIn("line_end", item["source"])
        self.assertEqual(representation["original_sha256"], hashlib.sha256(source_raw).hexdigest())
        self.assertEqual(representation["original_bytes"], len(source_raw))
        self.assertLess(representation["selected_bytes"], representation["original_bytes"])
        self.assertIn("@audit(\r\n    \"invoice\",\r\n)", item["content"])
        signature = ("async def calculate(\r\n        cls, values: list[int], *,\r\n"
                     "        tax: float = 0.0,\r\n    ) -> float:")
        self.assertIn(signature, item["content"])
        self.assertIn("Public invoice record.", item["content"])
        self.assertIn("# SPDX-License-Identifier: MIT", item["content"])
        self.assertIn("from dataclasses import dataclass", item["content"])
        self.assertIn('LABEL: str = "雪"', item["content"])
        self.assertNotIn("gross = sum(values)", item["content"])
        lines = context_pack._source_lines(source_raw)
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line))
        reconstructed = b"".join(b"".join(lines[segment["line_start"] - 1:segment["line_end"]])
                                 for segment in representation["segments"])
        self.assertEqual(reconstructed.decode("utf-8"), item["content"])
        for segment in representation["segments"]:
            selected = b"".join(lines[segment["line_start"] - 1:segment["line_end"]])
            self.assertEqual(segment["byte_start"], offsets[segment["line_start"] - 1])
            self.assertEqual(segment["byte_end"], offsets[segment["line_end"]])
            self.assertEqual(segment["sha256"], hashlib.sha256(selected).hexdigest())
        structure_preview = self.service.preview(candidates["candidate_set_id"], max_tokens=8192)
        rendered = structure_preview["renders"]["text"]["content"]
        self.assertIn("Presentation note (not source): omitted original lines", rendered)
        self.assertIn("Original source lines", rendered)
        self.assertNotIn("gross = sum(values)", rendered)
        self.assertEqual(self.service.export(structure_preview["preview_id"], format="text"),
                         rendered.encode("utf-8"))
        reopened = context_pack.ContextPackService(
            self.project, store=self.store, context_root=self.service.context_root,
            project_id="synthetic")
        self.assertEqual(reopened.export(structure_preview["preview_id"], format="text"),
                         rendered.encode("utf-8"))

        observation = context_pack._observation(self.project, "synthetic")
        path.write_bytes(source_raw.replace(b"gross = sum(values)", b"gross = sum(values) + 1"))
        self.assertEqual(context_pack._observation(self.project, "synthetic"), observation)
        with self.assertRaises(context_pack.ContextPackError) as error:
            self.service.export(structure_preview["preview_id"], format="text")
        self.assertEqual(error.exception.code, "source_drift")

    def test_structure_fallbacks_are_exact_and_explicit(self):
        fixtures = {
            "unsupported.ts": (b"export function run() { return 1; }\n", "unsupported_language"),
            "plain.txt": ("Plain text keeps 雪 and CRLF.\r\nNo syntax extraction.".encode("utf-8"),
                          "unsupported_language"),
            "broken.py": (b"def broken(:\n    pass\n", "malformed_python"),
            "small.py": (b"def small(): return 1\n", "one_line_declaration"),
            "licensed_body.py": (
                b"def licensed():\n    value = 1\n    # Copyright 2026 Fixture\n    return value\n",
                                 "source_notice_not_retained"),
        }
        for name, (raw, reason) in fixtures.items():
            with self.subTest(path=name):
                path = self.project / name
                path.write_bytes(raw)
                self._git("add", name)
                self._git("commit", "-qm", f"add {name}")
                candidates = self.service.candidates(
                    "inspect source", focus=[name], representation="structure")
                item = next(row for row in candidates["items"] if row["kind"] == "source")
                self.assertEqual(item["content"].encode("utf-8"), raw)
                self.assertEqual(item["representation"]["selected"], "full")
                self.assertEqual(item["representation"]["fallback_reason"], reason)
                preview = self.service.preview(candidates["candidate_set_id"], max_tokens=8192)
                self.assertEqual(self.service.export(preview["preview_id"]),
                                 preview["renders"]["text"]["content"].encode("utf-8"))

    def test_multiline_header_inline_suites_fall_back_without_truncation(self):
        fixtures = {
            "function.py": "def useful(\n    value: int,\n) -> int: return value + 1\n",
            "async_function.py": "async def useful(\n    value: int,\n) -> int: return value + 1\n",
            "class.py": "class Useful(\n    object,\n): pass\n",
        }
        for name, source in fixtures.items():
            with self.subTest(path=name):
                raw = source.encode("utf-8")
                path = self.project / name
                path.write_bytes(raw)
                self._git("add", name)
                self._git("commit", "-qm", f"add {name}")
                candidates = self.service.candidates(
                    "inspect declaration", focus=[name], representation="structure")
                item = next(row for row in candidates["items"] if row["kind"] == "source")
                self.assertEqual(item["content"].encode("utf-8"), raw)
                self.assertEqual(item["representation"]["selected"], "full")
                self.assertEqual(item["representation"]["fallback_reason"],
                                 "inline_suite_on_header_line")

    def test_multiline_header_with_ordinary_indented_body_stays_structural(self):
        source = ("def useful(\n    value: int,\n) -> int:\n"
                  "    return value + 1\n")
        raw = source.encode("utf-8")
        (self.project / "multiline.py").write_bytes(raw)
        self._git("add", "multiline.py")
        self._git("commit", "-qm", "add ordinary multiline declaration")
        candidates = self.service.candidates(
            "inspect declaration", focus=["multiline.py"], representation="structure")
        item = next(row for row in candidates["items"] if row["kind"] == "source")
        self.assertEqual(item["representation"]["selected"], "structure")
        self.assertIn("def useful(\n    value: int,\n) -> int:\n", item["content"])
        self.assertNotIn("return value + 1", item["content"])

    def test_multiline_header_with_multiline_inline_suite_falls_back_exactly(self):
        fixtures = {
            "function_multiline_suite.py": (
                "def useful(\n    value: int,\n) -> int: return (\n"
                "    value + 1\n)\n"),
            "async_multiline_suite.py": (
                "async def useful(\n    value: int,\n) -> int: return (\n"
                "    value + 1\n)\n"),
            "class_multiline_suite.py": (
                "class Useful(\n    object,\n): value = (\n    1\n)\n"),
        }
        for name, source in fixtures.items():
            with self.subTest(path=name):
                raw = source.encode("utf-8")
                (self.project / name).write_bytes(raw)
                self._git("add", name)
                self._git("commit", "-qm", f"add {name}")
                candidates = self.service.candidates(
                    "inspect declaration", focus=[name], representation="structure")
                item = next(row for row in candidates["items"] if row["kind"] == "source")
                self.assertEqual(item["content"].encode("utf-8"), raw)
                self.assertEqual(item["representation"]["selected"], "full")
                self.assertEqual(item["representation"]["fallback_reason"],
                                 "inline_suite_on_header_line")

    def test_overdeep_python_falls_back_to_exact_source(self):
        raw = ("value = " + "[" * 105 + "1" + "]" * 105 + "\n").encode("utf-8")
        (self.project / "deep.py").write_bytes(raw)
        self._git("add", "deep.py")
        self._git("commit", "-qm", "add deep fixture")
        candidates = self.service.candidates(
            "inspect deep source", focus=["deep.py"], representation="structure")
        item = next(row for row in candidates["items"] if row["kind"] == "source")
        self.assertEqual(item["content"].encode("utf-8"), raw)
        self.assertIn(item["representation"]["fallback_reason"],
                      {"parser_depth_limit", "ast_depth_limit", "malformed_python"})

    def test_overlimit_focus_is_omitted_whole_with_exact_reason(self):
        name = "oversized.py"
        (self.project / name).write_bytes(b"# " + b"x" * context_pack.repo_map.MAX_FILE_BYTES)
        self._git("add", name)
        self._git("commit", "-qm", "add oversized source")
        candidates = self.service.candidates(
            "inspect oversized source", focus=[name], representation="full")
        self.assertFalse(any(item["kind"] == "source" for item in candidates["items"]))
        self.assertTrue(any(item.get("path") == name and
                            "exceeds 256000 byte file limit" in item["reason"]
                            for item in candidates["omissions"]["items"]))

    def test_export_rejects_rehashed_representation_metadata_tampering(self):
        mutations = (
            lambda representation: representation["segments"][0].update(sha256="0" * 64),
            lambda representation: representation.update(algorithm="unreviewed-v99"),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate.__code__.co_consts):
                candidates = self.service.candidates(
                    "inspect prices", focus=["prices.py"], representation="structure")
                preview = self.service.preview(candidates["candidate_set_id"], max_tokens=8192)
                candidate_path = self.store / ("candidates-" + candidates["candidate_set_id"] + ".json")
                candidate_record = json.loads(candidate_path.read_text())
                item = next(row for row in candidate_record["items"] if row["kind"] == "source")
                mutate(item["representation"])
                candidate_path.write_text(json.dumps(candidate_record, sort_keys=True,
                                                      separators=(",", ":")))

                preview_path = self.store / ("preview-" + preview["preview_id"] + ".json")
                preview_record = json.loads(preview_path.read_text())
                manifest = preview_record["_manifest"]
                manifest["items"] = [item if row["item_id"] == item["item_id"] else row
                                      for row in manifest["items"]]
                _, wire, renders = context_pack._render_pack(
                    {key: value for key, value in manifest.items() if key != "pack_id"})
                preview_record["_manifest"] = wire
                preview_record["pack_id"] = wire["pack_id"]
                preview_record["renders"] = renders
                preview_path.write_text(json.dumps(preview_record, sort_keys=True,
                                                   separators=(",", ":")))
                with self.assertRaises(context_pack.ContextPackError) as error:
                    self.service.export(preview["preview_id"], format="text")
                self.assertEqual(error.exception.code, "store_invalid")

    def test_cli_candidates_preview_export(self):
        cli = Path(__file__).resolve().parents[1] / "scripts" / "context_pack.py"
        base = [sys.executable,
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
        raw_full = subprocess.check_output(base + ["candidates"] + common + [
            "--task", "inspect exact prices source", "--focus", "prices.py",
            "--representation", "full"])
        full = json.loads(raw_full)
        self.assertEqual(full["representation"], "full")
        exact_source = next(item for item in full["items"] if item["kind"] == "source")
        self.assertEqual(exact_source["representation"]["selected"], "full")
        raw_full_preview = subprocess.check_output(base + ["preview"] + common + [
            "--candidates", full["candidate_set_id"], "--max-tokens", "8192", "--format", "json"])
        full_preview = json.loads(raw_full_preview)
        self.assertEqual(subprocess.check_output(base + ["export"] + common + [
            "--preview", full_preview["preview_id"], "--format", "json"]), raw_full_preview)

    def test_default_exclusion_and_omission_budget_remain_within_both_caps(self):
        candidates = self.service.candidates("change total pricing")
        source_ids = [x["item_id"] for x in candidates["items"] if x["kind"] == "source"]
        preview = self.service.preview(candidates["candidate_set_id"], exclude_ids=[source_ids[0]],
                                       max_tokens=8192)
        self.assertNotIn(source_ids[0], preview["included_ids"])

        for number in range(32):
            name = f"pricing_helper_{number:02}.py"
            body = (f"def pricing_total_{number:02}(items):\n"
                    f"    # supporting pricing behavior number {number}\n"
                    "    return sum(items)\n")
            (self.project / name).write_text(body + "# padding " + ("x" * 180) + "\n")
        self._git("add", ".")
        self._git("commit", "-qm", "add pricing helpers")
        expanded = self.service.candidates("change total pricing")
        bounded = self.service.preview(expanded["candidate_set_id"], max_tokens=1000)
        self.assertGreater(len(bounded["omissions"][0]["item_ids"]), 0)
        for render in bounded["renders"].values():
            self.assertLessEqual(render["bytes"], 4000)

    def test_context_resolver_is_bound_to_each_configured_root_in_one_process(self):
        root_a = Path(__file__).resolve().parents[1]
        service_a = context_pack.ContextPackService(
            self.project, store=self.root / "store-a", context_root=root_a,
            project_id="synthetic-a")
        service_a.candidates("change total pricing", guidance_ids=["guidance:core/testing.md"])

        root_b = self.root / "context-b"
        subprocess.run(["git", "clone", "--local", "--no-hardlinks", "-q", str(root_a), str(root_b)],
                       check=True)
        registry_path = root_b / "resources.yaml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["dependencies"]["core/testing.md"] = ["core/acceptance-required.md"]
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
        required = "Required acceptance guidance unique to configured root B.\n"
        (root_b / "core/acceptance-required.md").write_text(required, encoding="utf-8")
        subprocess.run(["git", "-C", str(root_b), "add", "resources.yaml", "core/acceptance-required.md"],
                       check=True)
        subprocess.run(["git", "-C", str(root_b), "-c", "user.name=Fixture", "-c",
                        "user.email=fixture@example.invalid", "commit", "-qm", "fixture dependency"],
                       check=True)

        service_b = context_pack.ContextPackService(
            self.project, store=self.root / "store-b", context_root=root_b,
            project_id="synthetic-b")
        candidates = service_b.candidates("change total pricing", guidance_ids=["guidance:core/testing.md"])
        required_row = next(item for item in candidates["items"]
                            if item["title"] == "core/acceptance-required.md")
        self.assertEqual(required_row["content"], required)
        self.assertEqual(required_row["source"]["owner"], "context")
        preview = service_b.preview(candidates["candidate_set_id"], max_tokens=8192)
        exported = service_b.export(preview["preview_id"], format="text").decode("utf-8")
        self.assertIn(required, exported)


if __name__ == "__main__":
    unittest.main()
