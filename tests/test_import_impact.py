from pathlib import Path
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import import_impact


class ImportImpactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "impact@example.invalid")
        self.git("config", "user.name", "Impact Test")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def put(self, path, source):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        return target

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")

    def test_chain_cycle_relative_imports_and_source_bytes(self):
        leaf = self.put("src/pkg/leaf.py", "VALUE = 1\n")
        self.put("src/pkg/__init__.py", "")
        self.put("src/pkg/relative.py", "from . import leaf\n")
        self.put("src/middle.py", "from pkg.leaf import VALUE\n")
        self.put("src/top.py", "import middle\n")
        self.put("src/cycle_a.py", "import cycle_b\n")
        self.put("src/cycle_b.py", "import cycle_a\n")
        before = leaf.read_bytes()
        self.commit()

        result = import_impact.inspect_impact(self.root, "src/pkg/leaf.py")
        by_path = {row["path"]: row for row in result["nodes"]}
        self.assertEqual(by_path["src/pkg/leaf.py"]["depth"], 0)
        self.assertEqual(by_path["src/pkg/relative.py"]["depth"], 1)
        self.assertEqual(by_path["src/middle.py"]["depth"], 1)
        self.assertEqual(by_path["src/top.py"]["depth"], 2)
        self.assertIn(
            {"from": "src/pkg/relative.py", "to": "src/pkg/leaf.py", "line": 1},
            result["edges"],
        )
        cycle = import_impact.inspect_impact(self.root, "src/cycle_a.py")
        self.assertEqual({row["path"] for row in cycle["nodes"]}, {"src/cycle_a.py", "src/cycle_b.py"})
        self.assertEqual(leaf.read_bytes(), before)

    def test_namespace_package_child_is_candidate_and_namespace_is_disclosed(self):
        self.put("src/ns/leaf.py", "VALUE = 1\n")
        self.put("src/consumer.py", "from ns import leaf\n")
        self.commit()
        result = import_impact.inspect_impact(self.root, "src/ns/leaf.py")
        self.assertIn("src/consumer.py", {row["path"] for row in result["nodes"]})
        self.assertFalse(result["complete"])
        self.assertEqual(result["diagnostics"]["counts"]["namespace_package_without_file"], 1)

    def test_module_file_cannot_be_assumed_to_be_a_package_parent(self):
        self.put("foo.py", "")
        self.put("foo/bar.py", "")
        self.put("consumer.py", "import foo.bar\n")
        self.commit()
        result = import_impact.inspect_impact(self.root, "foo/bar.py")
        self.assertFalse(result["complete"])
        self.assertEqual(result["diagnostics"]["counts"]["module_parent_not_package"], 1)

    def test_diamond_uses_deterministic_lexical_via_and_sorted_results(self):
        self.put("base.py", "")
        self.put("parent_b.py", "import base\n")
        self.put("parent_a.py", "import base\n")
        self.put("caller.py", "import parent_b\nimport parent_a\n")
        self.commit()
        first = import_impact.inspect_impact(self.root, "base.py")
        second = import_impact.inspect_impact(self.root, "base.py")
        self.assertEqual(first, second)
        caller = next(row for row in first["nodes"] if row["path"] == "caller.py")
        self.assertEqual(caller["via"], "parent_a.py")

    def test_ambiguity_dynamic_import_and_external_import_are_disclosed(self):
        self.put("foo.py", "")
        self.put("src/foo.py", "")
        self.put(
            "consumer.py",
            "import foo\nimport external_package\n__import__('anything')\n"
            "from importlib import import_module as load\nload('other')\n",
        )
        self.commit()
        result = import_impact.inspect_impact(self.root, "foo.py")
        self.assertFalse(result["complete"])
        counts = result["diagnostics"]["counts"]
        self.assertEqual(counts["ambiguous_module"], 1)
        self.assertEqual(counts["unresolved_import"], 2)
        self.assertEqual(counts["dynamic_import"], 2)
        self.assertNotIn("consumer.py", {row["path"] for row in result["nodes"]})

    def test_regular_calls_and_raise_syntax_are_not_mistaken_for_dynamic_imports(self):
        self.put("seed.py", "")
        self.put("consumer.py", "import seed\nraise RuntimeError('statically parsed')\nvalue = dict()\n")
        self.commit()
        result = import_impact.inspect_impact(self.root, "seed.py")
        self.assertIn("consumer.py", {row["path"] for row in result["nodes"]})
        self.assertNotIn("dynamic_import", result["diagnostics"]["counts"])

    def test_syntax_and_invalid_utf8_are_partial_not_silently_complete(self):
        self.put("seed.py", "")
        self.put("broken.py", "def nope(:\n")
        self.put("invalid.py", "")
        (self.root / "invalid.py").write_bytes(b"\xff")
        self.put("consumer.py", "import seed\n")
        self.commit()
        result = import_impact.inspect_impact(self.root, "seed.py")
        self.assertFalse(result["complete"])
        self.assertEqual(result["diagnostics"]["counts"]["syntax_or_parse_limit"], 1)
        self.assertEqual(result["diagnostics"]["counts"]["invalid_utf8"], 1)
        self.assertIn("consumer.py", {row["path"] for row in result["nodes"]})

    def test_caps_are_explicit_and_boolean_limits_are_rejected(self):
        self.put("seed.py", "")
        for index in range(6):
            self.put(f"caller_{index}.py", "import seed\n")
        self.put("deep.py", "import caller_0\n")
        self.commit()
        limited = import_impact.inspect_impact(self.root, "seed.py", max_nodes=2)
        self.assertFalse(limited["complete"])
        self.assertEqual(len(limited["nodes"]), 2)
        self.assertEqual(limited["diagnostics"]["counts"]["max_nodes_reached"], 1)
        depth_limited = import_impact.inspect_impact(self.root, "seed.py", max_depth=0)
        self.assertFalse(depth_limited["complete"])
        self.assertEqual(depth_limited["diagnostics"]["counts"]["max_depth_reached"], 1)
        with self.assertRaises(import_impact.ImpactError):
            import_impact.inspect_impact(self.root, "seed.py", max_depth=True)

    def test_edge_output_cap_is_explicit(self):
        self.put("seed.py", "")
        self.put("caller.py", "import seed\n" * (import_impact.MAX_EDGES + 1))
        self.commit()
        result = import_impact.inspect_impact(self.root, "seed.py")
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["edges"]), import_impact.MAX_EDGES)
        self.assertEqual(result["diagnostics"]["counts"]["max_edges_reached"], 1)

    def test_module_cli_emits_json_without_writing_target(self):
        self.put("seed.py", "")
        self.put("caller.py", "import seed\n")
        self.commit()
        before = self.git("status", "--porcelain", "--untracked-files=normal").stdout
        completed = subprocess.run(
            [
                sys.executable, "-m", "scripts.import_impact", "--project", str(self.root),
                "--seed", "seed.py", "--format", "json",
            ],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        output = json.loads(completed.stdout)
        self.assertEqual(output["schema"], import_impact.SCHEMA)
        self.assertIn("caller.py", {row["path"] for row in output["nodes"]})
        after = self.git("status", "--porcelain", "--untracked-files=normal").stdout
        self.assertEqual(after, before)

    def test_seed_path_and_tracked_policy_reject_escape_and_symlink(self):
        self.put("safe.py", "")
        self.put("secrets/token.py", "value = 1\n")
        outside = self.root.parent / f"{self.root.name}-outside-impact.py"
        outside.write_text("value = 1\n", encoding="utf-8")
        self.put("link.py", "")
        (self.root / "link.py").unlink()
        (self.root / "link.py").symlink_to(outside)
        self.commit()
        for unsafe in ("../outside.py", str(outside), "secrets/token.py", "link.py", "./safe.py"):
            with self.subTest(seed=unsafe), self.assertRaises(import_impact.ImpactError):
                import_impact.inspect_impact(self.root, unsafe)
        outside.unlink()

    def test_list_is_tracked_only_and_snapshot_reports_dirty(self):
        self.put("tracked.py", "")
        self.commit()
        (self.root / "untracked.py").write_text("", encoding="utf-8")
        result = import_impact.list_files(self.root)
        self.assertEqual(result["files"], ["tracked.py"])
        self.assertTrue(result["snapshot"]["dirty"])

    def test_source_change_during_read_refuses_mixed_snapshot(self):
        source = self.put("seed.py", "")
        self.commit()
        original = import_impact.repo_map._read_tracked
        changed = [False]

        def read_then_change(*args, **kwargs):
            data = original(*args, **kwargs)
            if not changed[0]:
                changed[0] = True
                source.write_text("value = 2\n", encoding="utf-8")
            return data

        with patch.object(import_impact.repo_map, "_read_tracked", side_effect=read_then_change):
            with self.assertRaisesRegex(import_impact.ImpactError, "changed during inspection"):
                import_impact.inspect_impact(self.root, "seed.py")

    def test_repository_fsmonitor_hook_is_not_invoked(self):
        self.put("seed.py", "")
        self.commit()
        marker = self.root / "fsmonitor-ran"
        hook = self.root / "fake-fsmonitor"
        hook.write_text(f"#!/bin/sh\n/usr/bin/touch {shlex.quote(str(marker))}\n", encoding="utf-8")
        hook.chmod(0o755)
        self.git("config", "core.fsmonitor", str(hook))

        import_impact.list_files(self.root)
        import_impact.inspect_impact(self.root, "seed.py")
        self.assertFalse(marker.exists())

    def test_git_timeout_is_bounded_and_reported_without_stderr(self):
        with patch.object(
            import_impact.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("git", import_impact.GIT_TIMEOUT_SECONDS),
        ) as run:
            with self.assertRaisesRegex(import_impact.ImpactError, "time limit"):
                import_impact._git(self.root, "status")
        self.assertEqual(run.call_args.kwargs["timeout"], import_impact.GIT_TIMEOUT_SECONDS)
        self.assertIn("--no-optional-locks", run.call_args.args[0])

    def test_source_byte_limits_are_enforced_by_the_shared_reader(self):
        self.put("seed.py", "x=1\n")
        self.commit()
        with patch.object(import_impact.repo_map, "MAX_FILE_BYTES", 2):
            with self.assertRaisesRegex(import_impact.ImpactError, "safely read"):
                import_impact.inspect_impact(self.root, "seed.py")
        with patch.object(import_impact, "MAX_TOTAL_BYTES", 2):
            with self.assertRaisesRegex(import_impact.ImpactError, "safely read"):
                import_impact.inspect_impact(self.root, "seed.py")


if __name__ == "__main__":
    unittest.main()
