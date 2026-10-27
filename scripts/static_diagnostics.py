#!/usr/bin/env python3
"""Read-only, bounded TS/JS and Python syntax diagnostics for a tracked checkout.

TS/JS parsing runs through the existing in-memory TypeScript LanguageService
worker. Python syntax parsing reuses import_impact's bounded, no-follow source
reader and AST parser. No project configuration or source code is executed.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import unicodedata

from scripts import code_navigation, import_impact, repo_map


SCHEMA = "context.static-diagnostics.v1"
SCHEMA_VERSION = 1
POLICY = "tracked-policy-eligible-syntax-only-ts6-python-ast-v1"
MAX_DIAGNOSTICS = 500
MAX_MESSAGE_CHARS = 200
MAX_FILE_BYTES = repo_map.MAX_FILE_BYTES
MAX_TOTAL_BYTES = repo_map.MAX_TOTAL_BYTES
MAX_TRACKED_FILES = repo_map.MAX_FILES
TS_EXTENSIONS = code_navigation.SOURCE_EXTENSIONS
PY_EXTENSIONS = (".py", ".pyi")
SUPPORTED_EXTENSIONS = frozenset((*TS_EXTENSIONS, *PY_EXTENSIONS))
SOURCE_EXTENSIONS = frozenset({
    *TS_EXTENSIONS, *PY_EXTENSIONS, ".go", ".rs", ".java", ".kt", ".swift",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".sh",
    ".bash", ".zsh", ".sql", ".vue", ".svelte", ".tf",
})
LANGUAGES = {
    ".py": "python", ".pyi": "python",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".go": "go", ".rs": "rust", ".java": "java", ".kt": "kotlin", ".swift": "swift",
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp",
    ".rb": "ruby", ".php": "php", ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".sql": "sql", ".vue": "vue", ".svelte": "svelte", ".tf": "terraform",
}
QUALIFICATIONS = (
    "Diagnostics cover syntax only; they do not establish type correctness, runtime behavior, security, or whole-project correctness.",
    "TypeScript uses the installed TypeScript 6.x LanguageService over captured source with fixed options; project tsconfig, plugins, packages, external dependencies and standard-library types are not loaded.",
    "Python uses ast.parse only. No project code, build command, plugin, test, or package is executed.",
    "Dynamic dispatch, reflection, generated code, conditional imports and environment-dependent behavior remain unknown.",
    "Untracked files, non-source files, secret-like paths, generated/vendor/cache paths and unsupported languages are outside the analyzed source set.",
    "Capture is non-atomic. stable=true means the checked Git/source/engine identities matched before and after analysis; an edit reverted between captures may not be observed.",
    "Ranges use 1-based lines and 1-based UTF-16 code-unit columns, with an exclusive end; Python code-point offsets are converted to UTF-16.",
)


class StaticDiagnosticsError(ValueError):
    def __init__(self, message, kind="invalid_request"):
        super().__init__(message)
        self.kind = kind


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _path_key(path):
    return path.encode("utf-8", "strict")


def _source_digest(files):
    digest = hashlib.sha256()
    for row in sorted((row for row in files if row.get("sha256")), key=lambda row: _path_key(row["path"])):
        digest.update(_path_key(row["path"]))
        digest.update(b"\0")
        digest.update(bytes.fromhex(row["sha256"]))
    return digest.hexdigest()


def _diagnostic_id(path, file_sha256, code, severity, location):
    # Message wording is intentionally excluded; exact file bytes, rule and range identify the finding.
    identity = {"path": path, "fileSha256": file_sha256, "code": code,
                "severity": severity, "range": location}
    return hashlib.sha256(_json_bytes(identity)).hexdigest()


def _message(value):
    text = unicodedata.normalize("NFC", str(value)).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = " ".join(text.split())
    return text if len(text) <= MAX_MESSAGE_CHARS else text[:MAX_MESSAGE_CHARS - 1] + "…"


def _vcs_state(root):
    status = import_impact._git(
        root, "status", "--porcelain", "--untracked-files=normal", "--ignore-submodules=all"
    )
    return {"head": import_impact._head(root), "index": import_impact._tracked(root),
            "status": status, "dirty": bool(status)}


def _same_vcs(left, right):
    return left["head"] == right["head"] and left["index"] == right["index"] and left["status"] == right["status"]


def _python_records(records):
    eligible, skipped = import_impact._eligible_records(records)
    paths = {row[3] for row in eligible}
    skipped += sum(
        1 for mode, _, _, path in records
        if path.endswith(".pyi") and repo_map._skip_reason(
            str(PurePosixPath(path).with_suffix(".py")), mode
        ) is not None
    )
    for record in records:
        path = record[3]
        if path.endswith(".pyi") and repo_map._skip_reason(
            str(PurePosixPath(path).with_suffix(".py")), record[0]
        ) is None:
            paths.add(path)
    by_path = {row[3]: row for row in records}
    return [by_path[path] for path in sorted(paths, key=_path_key)], skipped


def _python_point(source, line, column):
    if type(line) is not int or type(column) is not int or line < 1 or column < 1:
        return None
    lines = code_navigation.LINE_BREAK.split(source)
    if line > len(lines):
        return None
    prefix = lines[line - 1][:column - 1]
    if len(prefix) != column - 1:
        return None
    return {"line": line, "column": len(prefix.encode("utf-16-le")) // 2 + 1}


def _typescript_range(source, start, length):
    if type(start) is not int or type(length) is not int or start < 0 or length < 0:
        return None
    positions = source.positions()
    begin = positions.position(start)
    end = positions.position(start + length)
    if begin is None or end is None:
        return None
    return {"start": {"line": begin[0], "column": begin[1]},
            "end": {"line": end[0], "column": end[1]}}


def _python_range(source, error):
    start = _python_point(source, error.get("line"), error.get("offset"))
    end_line = error.get("end_line") or error.get("line")
    end_column = error.get("end_offset") or error.get("offset")
    end = _python_point(source, end_line, end_column)
    if start is None or end is None:
        return None
    return {"start": start, "end": end}


def _file_row(path, language, status, sha256=None, reason=None):
    return {"path": path, "language": language, "status": status, "sha256": sha256,
            "reason": reason, "diagnostic_total": 0, "diagnostics": [], "unknown_reasons": []}


def _add_diagnostic(row, code, severity, message, location):
    if location is None:
        row["unknown_reasons"].append("A parser diagnostic did not include a valid source range; it is not selectable.")
        return
    diagnostic = {
        "diagnosticId": _diagnostic_id(row["path"], row["sha256"], code, severity, location),
        "code": code, "message": _message(message), "severity": severity,
        "path": row["path"], "fileSha256": row["sha256"], "range": location,
    }
    row["diagnostics"].append(diagnostic)


def _read_analyzer_identity(engine):
    paths = (Path(__file__).resolve(), Path(code_navigation.__file__).resolve(),
             Path(import_impact.__file__).resolve(), Path(repo_map.__file__).resolve(),
             code_navigation.WORKER.resolve())
    rows = []
    for path in paths:
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise StaticDiagnosticsError("a configured Context analysis component could not be read", "engine_unavailable") from exc
        rows.append({"path": str(path), "sha256": digest})
    try:
        result = subprocess.run([str(engine.node), "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=False, timeout=10, env={"PATH": str(engine.node.parent)})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StaticDiagnosticsError("configured Node runtime did not report its version", "engine_unavailable") from exc
    version = result.stdout.decode("utf-8", "replace").strip()
    if result.returncode or not version.startswith("v") or len(version) > 80:
        raise StaticDiagnosticsError("configured Node runtime did not report a supported version", "engine_unavailable")
    return rows, version


def _check_worker_result(reply, snapshot):
    version, worker_notes, _, result = code_navigation._envelope(reply)
    if not isinstance(result, dict) or set(result) != {"files", "diagnosticTotal", "omittedDiagnostics"}:
        raise StaticDiagnosticsError("TypeScript worker returned an invalid diagnostics result", "engine_reply")
    rows = result["files"]
    if not isinstance(rows, list) or len(rows) != len(snapshot.sources):
        raise StaticDiagnosticsError("TypeScript worker omitted a captured source file", "engine_reply")
    seen = set()
    output = {}
    total = 0
    for item in rows:
        if not isinstance(item, dict) or set(item) != {"path", "total", "diagnostics", "loaded"}:
            raise StaticDiagnosticsError("TypeScript worker returned an invalid file record", "engine_reply")
        path = item["path"]
        source = snapshot.sources.get(path)
        if source is None or path in seen or type(item["total"]) is not int or item["total"] < 0 or type(item["loaded"]) is not bool or not isinstance(item["diagnostics"], list):
            raise StaticDiagnosticsError("TypeScript worker returned an unbound file record", "engine_reply")
        seen.add(path)
        total += item["total"]
        row = _file_row(path, "typescript" if path.endswith((".ts", ".tsx", ".mts", ".cts")) else "javascript",
                        "analyzed" if item["loaded"] else "omitted", source.sha256,
                        None if item["loaded"] else "TypeScript did not load this captured source.")
        row["diagnostic_total"] = item["total"]
        if not item["loaded"]:
            row["unknown_reasons"].append("The TypeScript LanguageService did not load this file.")
        for diagnostic in item["diagnostics"]:
            if not isinstance(diagnostic, dict) or set(diagnostic) != {"code", "severity", "message", "start", "length"}:
                raise StaticDiagnosticsError("TypeScript worker returned an invalid syntax diagnostic", "engine_reply")
            code, severity = diagnostic["code"], diagnostic["severity"]
            if not isinstance(code, str) or not code.startswith("TS") or not code[2:].isdigit() or severity not in {"error", "warning", "suggestion", "info"} or not isinstance(diagnostic["message"], str):
                raise StaticDiagnosticsError("TypeScript worker returned invalid diagnostic fields", "engine_reply")
            location = _typescript_range(source, diagnostic["start"], diagnostic["length"])
            _add_diagnostic(row, code, severity, diagnostic["message"], location)
        output[path] = row
    if total != result["diagnosticTotal"] or result["omittedDiagnostics"] != max(0, total - 500):
        raise StaticDiagnosticsError("TypeScript worker diagnostic totals do not match", "engine_reply")
    return version, output, total, worker_notes


def analyze_project(project, *, node_executable, typescript_path):
    """Return deterministic, source-bound syntax diagnostics for one Git root."""
    try:
        root = import_impact._project_root(project)
        before = _vcs_state(root)
        engine = code_navigation._engine(node_executable, typescript_path)
        ts_snapshot = code_navigation._capture(root, engine)
        after_ts_capture = _vcs_state(root)
        if not _same_vcs(before, after_ts_capture) or ts_snapshot.head != before["head"] or ts_snapshot.dirty != before["dirty"]:
            raise StaticDiagnosticsError("project changed while source capture was starting; retry", "stale_snapshot")

        py_records, skipped_python = _python_records(before["index"])
        python_sources = import_impact._read_sources(root, py_records)
        captured_bytes = sum(len(source.text.encode("utf-8")) for source in ts_snapshot.sources.values())
        captured_bytes += sum(len(row["source"].encode("utf-8")) for row in python_sources.values() if row["source"] is not None)
        if captured_bytes > MAX_TOTAL_BYTES:
            raise StaticDiagnosticsError(f"combined TypeScript and Python source exceeds the {MAX_TOTAL_BYTES}-byte analysis limit", "limits")

        reply = code_navigation._run_worker(engine, code_navigation._payload(ts_snapshot, "diagnostics", code_navigation.DEFAULT_INSPECT_RESULTS))
        typescript_version, ts_rows, ts_total, worker_notes = _check_worker_result(reply, ts_snapshot)

        files = {**ts_rows}
        for path, digest in ts_snapshot.invalid:
            row = _file_row(path, "typescript" if path.endswith((".ts", ".tsx", ".mts", ".cts")) else "javascript",
                            "omitted", digest, "Source is not valid UTF-8 text or contains NUL.")
            row["unknown_reasons"].append("TypeScript did not parse invalid or binary source bytes.")
            files[path] = row
        python_total = 0
        for path, parsed in python_sources.items():
            digest = parsed["digest"]
            if parsed["source"] is None:
                files[path] = _file_row(path, "python", "omitted", digest, "Source is not valid UTF-8 text.")
                files[path]["unknown_reasons"].append("Python source is invalid UTF-8 and could not be parsed.")
                continue
            parse_error = parsed.get("parse_error")
            if parse_error and parse_error.get("kind") == "analysis_limit":
                files[path] = _file_row(path, "python", "omitted", digest, parse_error["message"])
                files[path]["unknown_reasons"].append(parse_error["message"])
                continue
            row = _file_row(path, "python", "analyzed", digest)
            if parse_error and parse_error.get("kind") == "syntax":
                python_total += 1
                row["diagnostic_total"] = 1
                _add_diagnostic(row, "PY-SYNTAX", "error", parse_error["message"], _python_range(parsed["source"], parse_error))
            if parsed["tree"] is not None:
                dynamic_lines = import_impact._dynamic_imports(parsed["tree"])
                if dynamic_lines:
                    row["unknown_reasons"].append(f"{len(dynamic_lines)} dynamic import site(s) are unresolved by static syntax analysis.")
            files[path] = row

        candidate_rows, policy_exclusions, hidden_exclusions = _candidate_rows(before["index"])
        for row in candidate_rows:
            if row["path"] not in files:
                files[row["path"]] = row

        all_files = sorted(files.values(), key=lambda row: _path_key(row["path"]))
        for row in all_files:
            row["diagnostics"].sort(key=lambda item: (
                item["range"]["start"]["line"], item["range"]["start"]["column"], item["code"], item["diagnosticId"]
            ))
        all_diagnostics = [diagnostic for row in all_files for diagnostic in row["diagnostics"]]
        all_diagnostics.sort(key=lambda item: (
            _path_key(item["path"]), item["range"]["start"]["line"], item["range"]["start"]["column"],
            item["code"], item["diagnosticId"],
        ))
        shown = set(item["diagnosticId"] for item in all_diagnostics[:MAX_DIAGNOSTICS])
        for row in all_files:
            row["diagnostics"] = [item for item in row["diagnostics"] if item["diagnosticId"] in shown]
        diagnostic_total = sum(row["diagnostic_total"] for row in all_files)
        diagnostics_omitted = max(0, diagnostic_total - len(shown))

        source_digest = _source_digest(all_files)
        analyzer_before, node_version = _read_analyzer_identity(engine)
        code_navigation._confirm(root, engine, ts_snapshot)
        python_sources_after = import_impact._read_sources(root, py_records)
        if {path: row["digest"] for path, row in python_sources.items()} != {path: row["digest"] for path, row in python_sources_after.items()}:
            raise StaticDiagnosticsError("Python source changed during analysis; retry", "stale_snapshot")
        import_impact._assert_unchanged(root, before)
        after = _vcs_state(root)
        if not _same_vcs(before, after):
            raise StaticDiagnosticsError("project Git state changed during analysis; retry", "stale_snapshot")
        analyzer_after, node_version_after = _read_analyzer_identity(engine)
        if analyzer_before != analyzer_after or node_version != node_version_after:
            raise StaticDiagnosticsError("Context analyzer or runtime changed during analysis; retry", "stale_snapshot")

        snapshot_identity = {
            "schema": SCHEMA, "policy": POLICY, "head": before["head"],
            "index": [list(record) for record in before["index"]],
            "statusSha256": hashlib.sha256(before["status"]).hexdigest(),
            "sourceDigest": source_digest, "codeNavigationSnapshot": ts_snapshot.id,
            "runtime": {"python": sys.version, "pythonPath": str(Path(sys.executable).resolve()),
                        "node": str(engine.node), "nodeVersion": node_version,
                        "typescript": str(engine.typescript), "typescriptSha256": engine.sha256,
                        "typescriptVersion": typescript_version},
            "analyzer": analyzer_before,
        }
        snapshot_id = hashlib.sha256(_json_bytes(snapshot_identity)).hexdigest()

        unknown_reasons = [
            "unsupported source language files are not parsed",
            "dynamic/runtime behavior is outside this syntax-only profile",
            "project configuration and external dependencies are not loaded",
        ]
        if policy_exclusions:
            unknown_reasons.append(f"{policy_exclusions} source path(s) were omitted by tracked-path safety policy")
        if skipped_python:
            unknown_reasons.append(f"{skipped_python} Python source path(s) were excluded by tracked-path safety policy")
        if diagnostics_omitted:
            unknown_reasons.append(f"{diagnostics_omitted} syntax diagnostic(s) were not returned due to response bounds or invalid locations")
        unknown_reasons.extend(reason for row in all_files for reason in row["unknown_reasons"])
        unknown_reasons = sorted(set(unknown_reasons), key=_path_key)
        omitted_count = sum(row["status"] == "omitted" for row in all_files) + hidden_exclusions
        unsupported_count = sum(row["status"] == "unsupported" for row in all_files)
        partial = bool(omitted_count or unsupported_count or diagnostics_omitted or
                       any(row["status"] != "analyzed" or row["unknown_reasons"] for row in all_files))
        status = "partial" if partial else "complete"
        captured_files = [{"path": row["path"], "sha256": row["sha256"]} for row in all_files if row["sha256"]]
        return {
            "schema": SCHEMA, "schema_version": SCHEMA_VERSION, "status": status, "stable": True,
            "source_digest": source_digest,
            "snapshot": {"id": snapshot_id, "head": before["head"], "dirty": before["dirty"],
                         "stable": True, "files": captured_files},
            "engine": {"python": {"path": str(Path(sys.executable).resolve()), "version": sys.version.split()[0]},
                       "node": {"path": str(engine.node), "version": node_version},
                       "typescript": {"path": str(engine.typescript), "version": typescript_version, "sha256": engine.sha256},
                       "worker": {"path": str(code_navigation.WORKER), "sha256": code_navigation._file_sha256(code_navigation.WORKER, "worker")}},
            "limits": {"max_tracked_files": MAX_TRACKED_FILES, "max_file_bytes": MAX_FILE_BYTES,
                       "max_total_bytes": MAX_TOTAL_BYTES, "max_diagnostics": MAX_DIAGNOSTICS,
                       "typescript_worker_timeout_seconds": code_navigation.WORKER_TIMEOUT_SECONDS,
                       "typescript_compiler_policy": code_navigation.COMPILER_POLICY},
            "coverage": {"tracked_source_candidates": len(all_files) + hidden_exclusions,
                         "analyzed_files": sum(row["status"] == "analyzed" for row in all_files),
                         "unsupported_files": unsupported_count, "omitted_files": omitted_count,
                         "diagnostics": {"total": diagnostic_total, "returned": len(shown), "omitted": diagnostics_omitted},
                         "unknown_reasons": unknown_reasons,
                         "column_units": "UTF-16 code units; 1-based, end-exclusive"},
            "files": all_files, "qualifications": list(QUALIFICATIONS),
        }
    except code_navigation.NavigationError as exc:
        raise StaticDiagnosticsError(str(exc), exc.kind) from exc
    except import_impact.ImpactError as exc:
        kind = "limits" if "limit" in str(exc).casefold() or "exceed" in str(exc).casefold() else "project"
        raise StaticDiagnosticsError(str(exc), kind) from exc
    except repo_map.MapError as exc:
        raise StaticDiagnosticsError(str(exc), "project") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, StaticDiagnosticsError):
            raise
        raise StaticDiagnosticsError("static diagnostics could not complete safely", "project") from exc


def _candidate_rows(records):
    rows, policy_count, hidden_count = [], 0, 0
    ts_paths = set(code_navigation.SOURCE_EXTENSIONS)
    py_paths = set(PY_EXTENSIONS)
    for mode, _, _, path in records:
        suffix = PurePosixPath(path).suffix.casefold()
        if suffix not in SOURCE_EXTENSIONS:
            continue
        reason = repo_map._skip_reason(path, mode)
        if reason == "unsupported file type":
            parent = PurePosixPath(path).parent
            checked = str(parent / (PurePosixPath(path).stem + ".py"))
            reason = repo_map._skip_reason(checked, mode)
        if reason or not code_navigation._safe_relative(path):
            policy_count += 1
            try:
                path.encode("utf-8", "strict")
            except UnicodeEncodeError:
                hidden_count += 1
                continue
            if reason and "secret" in reason:
                hidden_count += 1
                continue
            language = LANGUAGES.get(suffix, suffix.lstrip("."))
            rows.append(_file_row(path, language, "omitted", reason=reason or "unsafe relative path"))
            continue
        if suffix in ts_paths or suffix in py_paths:
            continue
        rows.append(_file_row(path, LANGUAGES.get(suffix, suffix.lstrip(".")), "unsupported",
                              reason="No parser is configured for this language; coverage is unknown."))
    return rows, policy_count, hidden_count


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python scripts/static_diagnostics.py",
        description="Read-only bounded TS/JS and Python syntax diagnostics; prints JSON only.",
    )
    parser.add_argument("--project", required=True, help="exact Git repository root selected by the trusted host")
    parser.add_argument("--node", required=True, help="absolute host-configured Node executable")
    parser.add_argument("--typescript", required=True, help="absolute installed TypeScript 6.x module file")
    args = parser.parse_args(argv)
    try:
        result = analyze_project(args.project, node_executable=args.node, typescript_path=args.typescript)
    except StaticDiagnosticsError as exc:
        json.dump({"schema": SCHEMA, "schema_version": SCHEMA_VERSION,
                   "error": {"kind": exc.kind, "message": _message(exc)}}, sys.stdout, ensure_ascii=True, sort_keys=True)
        sys.stdout.write("\n")
        return 2
    json.dump(result, sys.stdout, ensure_ascii=True, sort_keys=True, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
