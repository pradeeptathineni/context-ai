from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import code_navigation


REPOSITORY = Path(__file__).resolve().parents[1]
NODE = os.environ.get("CONTEXT_CODE_NAV_NODE") or shutil.which("node")
TYPESCRIPT = os.environ.get("CONTEXT_TYPESCRIPT_PATH")
ENGINE_HINT = (
    "set CONTEXT_TYPESCRIPT_PATH to an installed typescript/lib/typescript.js (6.x) and "
    "CONTEXT_CODE_NAV_NODE to a Node executable; these tests never install either"
)
FIXTURE = {
    "src/a.ts": "export function add(x: number, y: number) {\n  return x + y;\n}\n",
    "src/b.ts": (
        'import { add as sum } from "./a";\nimport { helper } from "@app/helper";\n\n'
        "export function run() {\n  return sum(1, 2) + helper();\n}\n"
    ),
    "src/c.ts": 'function add(text: string) {\n  return text;\n}\nexport const local = add("x");\n',
    "src/shadow.ts": (
        'import { add } from "./a";\n\nexport function shadow() {\n'
        "  const add = (value: number) => value;\n  return add(1);\n}\n"
    ),
    # the emoji is two UTF-16 units, so the add call starts at column 26, not code point 25
    "src/view.tsx": (
        'import { add } from "./a";\n\nexport function Badge() {\n'
        '  return <b title="😀é">{add(1, 2)}</b>;\n}\n'
    ),
    "src/helper/index.ts": "export function helper() {\n  return 1;\n}\n",
    "src/util.mts": "export const twice = (value: number) => value * 2;\n",
    "src/side_effect.js": 'require("fs").writeFileSync(__dirname + "/executed.txt", "x");\n',
    "src/secrets.ts": "export function leakedSecretValue() {\n  return 1;\n}\n",
    "node_modules/pkg/index.ts": "export function leakedVendorValue() {}\n",
    "tsconfig.json": '{"compilerOptions": {"baseUrl": ".", "paths": {"@app/*": ["src/*"]}}}\n',
    "package.json": '{"scripts": {"postinstall": "touch installed.txt"}}\n',
    ".env": "TOKEN=leakedSecretValue\n",
}


def at(location):
    return location["file"], location["line"], location["column"]


class CodeNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "navigation@example.invalid")
        self.git("config", "user.name", "Navigation Test")
        for path, source in FIXTURE.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")
        os.symlink("a.ts", self.root / "src" / "link.ts")
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

    def status(self, ignored=False):
        return self.git("status", "--porcelain", "--untracked-files=all", *(["--ignored"] if ignored else [])).stdout

    def sha(self, path):
        return hashlib.sha256((self.root / path).read_bytes()).hexdigest()

    def node(self):
        if not NODE or not Path(NODE).is_file():
            self.skipTest(ENGINE_HINT)
        return NODE

    def engine(self):
        if not TYPESCRIPT or not Path(TYPESCRIPT).is_file():
            self.skipTest(ENGINE_HINT)
        return {"node_executable": self.node(), "typescript_path": TYPESCRIPT}

    def search(self, query):
        return code_navigation.search_symbols(self.root, query, **self.engine())

    def inspect(self, found, name, file):
        location = next(
            row["location"] for row in found["symbols"] if row["name"] == name and row["location"]["file"] == file
        )
        return code_navigation.inspect_symbol(
            self.root, location, expected_snapshot=found["snapshot"]["id"], **self.engine()
        )

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "scripts.code_navigation", *args],
            cwd=REPOSITORY, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )

    def test_imported_alias_same_name_shadowing_tsx_and_utf16_positions(self):
        found = self.search("add")
        self.assertRegex(found["engine"]["version"], r"^6\.")
        self.assertEqual(found["engine"]["sha256"], hashlib.sha256(Path(TYPESCRIPT).read_bytes()).hexdigest())
        first = found["symbols"][0]
        self.assertEqual((first["name"], first["kind"]), ("add", "function"))
        self.assertEqual(first["location"], {
            "file": "src/a.ts", "sha256": self.sha("src/a.ts"),
            "line": 1, "column": 17, "endLine": 1, "endColumn": 20,
        })
        self.assertIn(("src/c.ts", 1, 10), {at(row["location"]) for row in found["symbols"]})

        detail = self.inspect(found, "add", "src/a.ts")
        self.assertEqual(detail["selected"], first["location"])
        self.assertEqual([at(row["location"]) for row in detail["definitions"]], [("src/a.ts", 1, 17)])
        references = {at(row["location"]) for row in detail["references"]}
        self.assertLessEqual({
            ("src/a.ts", 1, 17), ("src/b.ts", 1, 10), ("src/b.ts", 1, 17), ("src/b.ts", 5, 10),
            ("src/view.tsx", 1, 10), ("src/view.tsx", 4, 26), ("src/shadow.ts", 1, 10),
        }, references)
        self.assertFalse({("src/shadow.ts", 4, 9), ("src/shadow.ts", 5, 10)} & references)
        self.assertNotIn("src/c.ts", {file for file, _, _ in references})
        for row in detail["references"]:
            self.assertEqual(row["location"]["sha256"], self.sha(row["location"]["file"]))
        incoming = {
            (call["name"], at(call["location"])): [at(site) for site in call["sites"]]
            for call in detail["incoming"]
        }
        self.assertEqual(incoming, {
            ("run", ("src/b.ts", 4, 17)): [("src/b.ts", 5, 10)],
            ("Badge", ("src/view.tsx", 3, 17)): [("src/view.tsx", 4, 26)],
        })

    def test_inspection_excerpt_is_bound_to_the_captured_source(self):
        found = self.search("add")
        detail = self.inspect(found, "add", "src/a.ts")
        excerpt = detail["excerpt"]
        self.assertEqual(excerpt["text"], FIXTURE["src/a.ts"])
        self.assertEqual(excerpt["location"]["sha256"], self.sha("src/a.ts"))
        self.assertEqual(excerpt["location"]["file"], "src/a.ts")
        self.assertFalse(excerpt["truncatedBefore"])
        self.assertFalse(excerpt["truncatedAfter"])
        self.assertEqual(detail["limits"]["max_excerpt_utf16_units"], 4096)

    def test_excerpt_keeps_long_line_selected_point_and_exact_utf16_bounds(self):
        text = "before\r\n" + "😀x" * 5000 + "\r\nafter\n"
        source = code_navigation._Source("src/long.ts", "a" * 64, text, 0)
        positions = source.positions()
        point = positions.starts[1] + 9000
        excerpt = code_navigation._excerpt(source, point)
        location = excerpt["location"]
        start = positions.offset(location["line"], location["column"])
        end = positions.offset(location["endLine"], location["endColumn"])
        self.assertLessEqual(start, point)
        self.assertGreater(end, point)
        self.assertLessEqual(end - start, 4096)
        self.assertEqual(excerpt["text"], positions.units[start * 2:end * 2].decode("utf-16-le"))
        self.assertTrue(excerpt["truncatedBefore"])
        self.assertTrue(excerpt["truncatedAfter"])
        # CRLF and EOF remain exact when the whole small source fits
        small = code_navigation._Source("src/small.ts", "b" * 64, "😀\r\nx\r\n", 0)
        self.assertEqual(code_navigation._excerpt(small, 0)["text"], small.text)
        self.assertEqual(code_navigation._excerpt(small, small.positions().length)["text"], small.text)

    def test_outgoing_calls_resolve_through_a_renamed_import(self):
        found = self.search("run")
        detail = self.inspect(found, "run", "src/b.ts")
        outgoing = {
            (call["name"], at(call["location"])): [at(site) for site in call["sites"]]
            for call in detail["outgoing"]
        }
        self.assertEqual(outgoing.get(("add", ("src/a.ts", 1, 17))), [("src/b.ts", 5, 10)])
        self.assertEqual(detail["incoming"], [])
        self.assertEqual(detail["omitted"], {"definitions": 0, "references": 0, "incoming": 0, "outgoing": 0})

    def test_exclusions_unresolved_alias_and_empty_search_are_explicit(self):
        found = self.search("leaked")
        self.assertEqual(found["symbols"], [])
        self.assertEqual(found["omitted"], {"symbols": 0})
        paths = {row["path"] for row in found["snapshot"]["files"]}
        self.assertLessEqual({"src/a.ts", "src/util.mts", "src/side_effect.js", "src/view.tsx"}, paths)
        self.assertFalse(paths & {
            "src/secrets.ts", "src/link.ts", "node_modules/pkg/index.ts", "tsconfig.json", "package.json", ".env",
        })
        kinds = {row["kind"] for row in found["diagnostics"]}
        self.assertIn("policy_excluded", kinds)
        unresolved = [row["message"] for row in found["diagnostics"] if row["kind"] == "unresolved_module"]
        self.assertTrue(any("@app/helper" in message for message in unresolved), unresolved)

    def test_source_edit_after_search_with_unchanged_git_status_is_refused(self):
        source = self.root / "src" / "a.ts"
        source.write_text(FIXTURE["src/a.ts"] + "// first edit\n", encoding="utf-8")
        found = self.search("add")
        status = self.status()
        source.write_text(FIXTURE["src/a.ts"] + "// second edit\n", encoding="utf-8")
        self.assertEqual(self.status(), status)
        with self.assertRaises(code_navigation.NavigationError) as caught:
            self.inspect(found, "add", "src/a.ts")
        self.assertEqual(caught.exception.kind, "stale_snapshot")

    def test_source_edit_during_engine_run_is_refused(self):
        source = self.root / "src" / "c.ts"
        source.write_text(FIXTURE["src/c.ts"] + "// dirty before\n", encoding="utf-8")
        engine = self.engine()
        original = code_navigation._run_worker

        def run_then_edit(*args, **kwargs):
            reply = original(*args, **kwargs)
            source.write_text(FIXTURE["src/c.ts"] + "// edited during the run\n", encoding="utf-8")
            return reply

        with patch.object(code_navigation, "_run_worker", side_effect=run_then_edit):
            with self.assertRaises(code_navigation.NavigationError) as caught:
                code_navigation.search_symbols(self.root, "add", **engine)
        self.assertEqual(caught.exception.kind, "stale_snapshot")

    def test_malformed_unsafe_and_stale_selectors_are_refused(self):
        found = self.search("add")
        location = found["symbols"][0]["location"]
        snapshot = found["snapshot"]["id"]
        unsafe = [
            "src/a.ts",
            {**location, "file": "../src/a.ts"},
            {**location, "file": "/etc/passwd"},
            {**location, "file": "./src/a.ts"},
            {**location, "file": "src/secrets.ts"},
            {**location, "file": "src/link.ts"},
            {**location, "file": "src/c.ts"},
            {**location, "sha256": "0" * 64},
            {**location, "line": 99},
            {**location, "column": 999},
            {**location, "column": 0},
            {**location, "line": True},
            {key: value for key, value in location.items() if key != "endColumn"},
            {**location, "symbol": "add"},
        ]
        for selector in unsafe:
            with self.subTest(selector=selector), self.assertRaises(code_navigation.NavigationError):
                code_navigation.inspect_symbol(self.root, selector, expected_snapshot=snapshot, **self.engine())
        for expected, kind in (("f" * 64, "stale_snapshot"), ("not-a-snapshot", "invalid_request")):
            with self.subTest(expected=expected), self.assertRaises(code_navigation.NavigationError) as caught:
                code_navigation.inspect_symbol(self.root, location, expected_snapshot=expected, **self.engine())
            self.assertEqual(caught.exception.kind, kind)

    def test_cli_search_then_inspect_journey_has_no_project_side_effects(self):
        engine = self.engine()
        before = self.status(ignored=True)
        flags = ["--node", engine["node_executable"], "--typescript", engine["typescript_path"]]
        searched = self.cli("search", str(self.root), "run", *flags, "--max-results", "5")
        self.assertEqual(searched.returncode, 0, searched.stdout)
        found = json.loads(searched.stdout)
        location = next(row["location"] for row in found["symbols"] if row["name"] == "run")
        inspected = self.cli(
            "inspect", str(self.root), "--selector-json", json.dumps(location),
            "--expected-snapshot", found["snapshot"]["id"], *flags,
        )
        self.assertEqual(inspected.returncode, 0, inspected.stdout)
        detail = json.loads(inspected.stdout)
        self.assertEqual(detail["schema"], code_navigation.SCHEMA)
        self.assertIn(("add", "src/a.ts"), {(call["name"], call["location"]["file"]) for call in detail["outgoing"]})
        self.assertEqual(self.status(ignored=True), before)
        self.assertFalse((self.root / "src" / "executed.txt").exists())
        self.assertFalse((self.root / "installed.txt").exists())

    def test_additional_extensions_keep_existing_admission_policy(self):
        records = [
            ("100644", "0" * 40, "0", "src/util.mts"),
            ("100644", "0" * 40, "0", "src/typed.cts"),
            ("100644", "0" * 40, "0", "node_modules/pkg/index.mts"),
            ("100644", "0" * 40, "0", "dist/out.cts"),
            ("100644", "0" * 40, "0", "src/secrets.cts"),
            ("120000", "0" * 40, "0", "src/link.mts"),
        ]
        admitted, excluded = code_navigation._eligible(records)
        self.assertEqual(admitted, ["src/typed.cts", "src/util.mts"])
        self.assertEqual(excluded, 4)

    def test_requests_are_validated_before_engine_or_project_access(self):
        missing = {"node_executable": "/missing/node", "typescript_path": "/missing/typescript.js"}
        for value in (0, code_navigation.MAX_RESULTS + 1, True, "5"):
            with self.subTest(max_results=value), self.assertRaises(code_navigation.NavigationError):
                code_navigation.search_symbols(self.root, "add", max_results=value, **missing)
        for query in ("", "   ", "a\nb", "x" * (code_navigation.MAX_QUERY_CHARS + 1)):
            with self.subTest(query=query), self.assertRaises(code_navigation.NavigationError):
                code_navigation.search_symbols(self.root, query, **missing)
        refused = self.cli(
            "inspect", str(self.root), "--selector-json", "{", "--expected-snapshot", "x",
            "--node", missing["node_executable"], "--typescript", missing["typescript_path"],
        )
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(json.loads(refused.stdout)["error"]["kind"], "invalid_request")

    def test_missing_engine_is_actionable_and_installs_nothing(self):
        before = self.status(ignored=True)
        missing = Path(self.temp.name) / "missing" / "typescript.js"
        with self.assertRaises(code_navigation.NavigationError) as caught:
            code_navigation.search_symbols(self.root, "add", node_executable=sys.executable, typescript_path=missing)
        self.assertEqual(caught.exception.kind, "engine_unavailable")
        self.assertIn("Nothing was installed", str(caught.exception))
        with self.assertRaises(code_navigation.NavigationError) as caught:
            code_navigation.search_symbols(self.root, "add", node_executable="node", typescript_path=missing)
        self.assertEqual(caught.exception.kind, "engine_unavailable")
        self.assertFalse(missing.exists())
        self.assertEqual(self.status(ignored=True), before)

    def test_wrong_engine_malformed_reply_and_timeout_are_refused(self):
        node = self.node()

        def fake(name, source):
            path = Path(self.temp.name) / f"{name}.js"
            path.write_text(source, encoding="utf-8")
            return {"node_executable": node, "typescript_path": str(path)}

        cases = (
            ("old", 'module.exports = { version: "5.9.3" };\n', "engine_unsupported"),
            ("noisy", 'process.stdout.write("not json");\nmodule.exports = { version: "6.0.3" };\n', "engine_reply"),
        )
        for name, source, kind in cases:
            with self.subTest(engine=name), self.assertRaises(code_navigation.NavigationError) as caught:
                code_navigation.search_symbols(self.root, "add", **fake(name, source))
            self.assertEqual(caught.exception.kind, kind)
        with patch.object(code_navigation, "WORKER_TIMEOUT_SECONDS", 2):
            with self.assertRaises(code_navigation.NavigationError) as caught:
                code_navigation.search_symbols(self.root, "add", **fake("hang", "for (;;) {}\n"))
        self.assertEqual(caught.exception.kind, "engine_timeout")

    def test_worker_locations_outside_captured_text_are_rejected(self):
        # the worker is replaced only to feed hostile replies to the owner-side validation
        placeholder = Path(self.temp.name) / "typescript.js"
        placeholder.write_text("// not loaded\n", encoding="utf-8")
        engine = {"node_executable": sys.executable, "typescript_path": str(placeholder)}

        def reply(span, total=1):
            symbol = {"name": "add", "kind": "function", "container": "", "matchKind": "exact", "span": span}
            return {
                "ok": True, "protocol": 1, "engine": {"name": "typescript", "version": "6.0.3"},
                "diagnostics": [], "diagnosticTotal": 0, "result": {"symbols": [symbol], "total": total},
            }

        hostile = (
            reply({"file": "src/a.ts", "start": 10**6, "length": 3}),
            reply({"file": "src/a.ts", "start": -1, "length": 3}),
            reply({"file": "src/a.ts", "start": 1.5, "length": 3}),
            reply({"file": "../outside.ts", "start": 0, "length": 1}),
            reply({"file": "src/secrets.ts", "start": 0, "length": 1}),
            reply({"file": "src/a.ts", "start": 16, "length": 3}, total=0),
        )
        for value in hostile:
            with self.subTest(reply=value["result"]), patch.object(code_navigation, "_run_worker", return_value=value):
                with self.assertRaises(code_navigation.NavigationError) as caught:
                    code_navigation.search_symbols(self.root, "add", **engine)
                self.assertEqual(caught.exception.kind, "engine_reply")


if __name__ == "__main__":
    unittest.main()
