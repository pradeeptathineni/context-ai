import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import scripts.repo_map as repo_map
from scripts.repo_map import MapError, build_map, render_json, render_text


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

        result = build_map(self.root, "change total pricing", max_tokens=400)
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
        self.assertIn("no files selected", render_text(result))

    def test_cli_text_and_json(self):
        self.add("prices.py", "def pricing_total():\n    return 1\n")
        self.commit()
        command = [sys.executable, str(REPO / "scripts/repo_map.py"), "--project", str(self.root), "--task", "pricing total"]
        text = subprocess.run(command, check=True, capture_output=True, text=True).stdout
        data = subprocess.run(command + ["--format", "json"], check=True, capture_output=True, text=True).stdout
        self.assertIn("prices.py", text)
        decoded = json.loads(data)
        self.assertEqual(decoded["schema"], "context-ai/repo-map/v1")
        self.assertIn("sha256", decoded["entries"][0])
        self.assertIn("total_tokens", decoded)

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
        self.assertIn("no files selected", render_text(empty))

    def test_leaf_and_parent_symlink_swaps_are_rejected_before_read(self):
        self.add("prices.py", "def calculate_total():\n    return 1\n")
        self.add("pkg/prices.py", "def calculate_total():\n    return 2\n")
        self.commit()
        outside_file = self.root.parent / (self.root.name + "-outside.py")
        outside_dir = self.root.parent / (self.root.name + "-outside-dir")
        outside_file.write_text("def calculate_outside_total():\n    return 999\n", encoding="utf-8")
        outside_dir.mkdir()
        (outside_dir / "prices.py").write_text("def calculate_outside_total():\n    return 998\n", encoding="utf-8")
        original_open = os.open

        def swap_leaf(path, flags, *args, **kwargs):
            if path == "prices.py" and kwargs.get("dir_fd") is not None:
                target = self.root / "prices.py"
                if target.is_file() and not target.is_symlink():
                    target.unlink()
                    target.symlink_to(outside_file)
            return original_open(path, flags, *args, **kwargs)

        with patch.object(repo_map.os, "open", swap_leaf):
            leaf_result = build_map(self.root, "calculate outside total")
        self.assertNotIn("prices.py", {entry["path"] for entry in leaf_result["entries"]})
        self.assertTrue(any("prices.py" in warning for warning in leaf_result["diagnostics"]["warnings"]))
        self.assertNotIn(hashlib.sha256(outside_file.read_bytes()).hexdigest(), {entry["file_sha256"] for entry in leaf_result["entries"]})

        (self.root / "prices.py").unlink()
        (self.root / "prices.py").write_text("def calculate_total():\n    return 1\n", encoding="utf-8")
        original_open = os.open

        def swap_parent(path, flags, *args, **kwargs):
            if path == "pkg" and kwargs.get("dir_fd") is not None:
                target = self.root / "pkg"
                if target.is_dir() and not target.is_symlink():
                    target.rename(self.root / "pkg-original")
                    target.symlink_to(outside_dir, target_is_directory=True)
            return original_open(path, flags, *args, **kwargs)

        with patch.object(repo_map.os, "open", swap_parent):
            parent_result = build_map(self.root, "calculate outside total")
        self.assertNotIn("pkg/prices.py", {entry["path"] for entry in parent_result["entries"]})
        self.assertTrue(any("pkg/prices.py" in warning for warning in parent_result["diagnostics"]["warnings"]))
        self.assertNotIn(hashlib.sha256((outside_dir / "prices.py").read_bytes()).hexdigest(), {entry["file_sha256"] for entry in parent_result["entries"]})

    def test_repository_status_and_head_are_rechecked(self):
        target = self.add("prices.py", "def pricing_total():\n    return 1\n")
        self.commit()
        original_status = repo_map._status
        changed = [False]

        def mutate_after_initial_status(root):
            status = original_status(root)
            if not changed[0]:
                changed[0] = True
                target.write_text("def pricing_total_changed():\n    return 2\n", encoding="utf-8")
            return status

        with patch.object(repo_map, "_status", mutate_after_initial_status):
            result = build_map(self.root, "pricing changed")
        self.assertTrue(result["dirty"])
        self.assertTrue(result["observation_changed"])
        self.assertEqual(result["consistency"], "non-atomic")

        target.write_text("def pricing_total():\n    return 1\n", encoding="utf-8")
        original_read = repo_map._read_tracked
        advanced = [False]

        def advance_head(root_fd, relative, remaining, on_bytes):
            data = original_read(root_fd, relative, remaining, on_bytes)
            if not advanced[0]:
                advanced[0] = True
                target.write_text("def pricing_total():\n    return 3\n", encoding="utf-8")
                self.git("add", "prices.py")
                self.git("commit", "-qm", "advance during map")
            return data

        with patch.object(repo_map, "_read_tracked", advance_head):
            with self.assertRaisesRegex(MapError, "HEAD or index changed"):
                build_map(self.root, "pricing")

    def test_raced_reads_are_charged_and_stay_within_total_limit(self):
        for n in range(3):
            self.add(f"prices_{n}.py", "def total():\n    return 1\n")
        self.commit()
        original_open = os.open
        original_read = os.read
        paths = {}
        consumed = [0]

        def identify_open(path, flags, *args, **kwargs):
            fd = original_open(path, flags, *args, **kwargs)
            if isinstance(path, str) and path.startswith("prices_") and kwargs.get("dir_fd") is not None:
                paths[fd] = self.root / path
            return fd

        def mutate_after_read(fd, amount):
            data = original_read(fd, amount)
            if data and fd in paths:
                consumed[0] += len(data)
                path = paths.pop(fd)
                replacement = path.with_suffix(".replacement")
                replacement.write_text("def total():\n    return 2\n", encoding="utf-8")
                replacement.replace(path)
            return data

        with patch.object(repo_map, "MAX_TOTAL_BYTES", 30), patch.object(repo_map.os, "open", identify_open), patch.object(repo_map.os, "read", mutate_after_read):
            result = build_map(self.root, "total")
        self.assertLessEqual(consumed[0], 30)
        self.assertEqual(result["diagnostics"]["read_bytes"], consumed[0])
        self.assertGreater(result["diagnostics"]["read_bytes"], 0)

    def test_output_budget_bounds_task_and_warning_metadata(self):
        for number in range(100):
            self.add(f"broken_{number:03}.py", "def bad(:\n")
        self.commit()
        result = build_map(self.root, "x" * 100_000, max_tokens=1)
        text = render_text(result).encode("utf-8")
        data = render_json(result).encode("utf-8")
        output_limit_bytes = max(repo_map.MIN_OUTPUT_BYTES, result["max_tokens"] * 4)
        self.assertLessEqual(len(text) + 1, output_limit_bytes)
        self.assertLessEqual(len(data) + 1, output_limit_bytes)
        self.assertLess(len(text), 4096)
        self.assertTrue(result["task_truncated"])
        self.assertEqual(result["estimated_entry_tokens"], 0)
        self.assertGreater(result["estimated_tokens"], result["max_tokens"])
        self.assertFalse(result["budget_satisfied"])
        self.assertEqual(result["diagnostics"]["warning_count"], 100)
        self.assertGreater(result["diagnostics"]["warnings_omitted"], 0)

    def test_final_output_cap_counts_json_escaped_control_characters(self):
        for number in range(8):
            name = "\x01" * 63 + f"{number}.py"
            self.add(name, "def broken(:\n")
        self.commit()

        result = build_map(self.root, "\x01" * 100_000, max_tokens=1)
        text_size = len(render_text(result).encode("utf-8")) + 1
        json_size = len(render_json(result).encode("utf-8")) + 1
        output_limit_bytes = max(repo_map.MIN_OUTPUT_BYTES, result["max_tokens"] * 4)
        self.assertLessEqual(text_size, output_limit_bytes)
        self.assertLessEqual(json_size, output_limit_bytes)
        self.assertLessEqual(repo_map._output_bytes(result), output_limit_bytes)
        self.assertEqual(result["diagnostics"]["warning_count"], 8)
        self.assertGreater(result["diagnostics"]["warnings_omitted"], 0)
        self.assertTrue(result["task_truncated"])

    def test_secret_style_directories_are_skipped_even_when_focused(self):
        self.add("secrets/config.py", "def secret_pricing_total():\n    return 1\n")
        self.add("credentials/config.json", '{"pricing_total": 2}')
        self.add("prices.py", "def pricing_total():\n    return 3\n")
        self.commit()
        original_read = repo_map._read_tracked
        read_paths = []

        def record_read(root_fd, relative, remaining, on_bytes):
            read_paths.append(relative)
            return original_read(root_fd, relative, remaining, on_bytes)

        with patch.object(repo_map, "_read_tracked", record_read):
            result = build_map(self.root, "pricing total")
            focused = build_map(self.root, "pricing total", focus=["secrets"])
        self.assertEqual({entry["path"] for entry in result["entries"]}, {"prices.py"})
        self.assertNotIn("secrets/config.py", read_paths)
        self.assertNotIn("credentials/config.json", read_paths)
        self.assertEqual(focused["entries"], [])
        self.assertGreaterEqual(focused["diagnostics"]["skipped_files"], 1)

    def test_parser_depth_failure_is_bounded_per_file(self):
        self.add("deep.py", "def deep_total():\n    return " + "+".join(["1"] * 10_000) + "\n")
        self.add("prices.py", "def pricing_total():\n    return 3\n")
        self.commit()
        result = build_map(self.root, "pricing total")
        self.assertEqual({entry["path"] for entry in result["entries"]}, {"prices.py"})
        self.assertTrue(any("parser/visitor depth limit" in item for item in result["diagnostics"]["warnings"]))

    def test_lexical_declaration_lines_allow_blank_lines(self):
        self.add("prices.js", "\n\nfunction calculate_total(items) { return 1; }\n")
        self.commit()
        result = build_map(self.root, "total")
        self.assertEqual(result["entries"][0]["symbols"][0]["line"], 3)


if __name__ == "__main__":
    unittest.main()
