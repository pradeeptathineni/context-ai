#!/usr/bin/env python3
"""Read-only, task-focused map of tracked files and symbols."""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


MAX_FILES = 5000
MAX_FILE_BYTES = 256_000
MAX_TOTAL_BYTES = 8_000_000
MAX_TASK_CHARS = 2048
MAX_WARNING_SAMPLES = 8
MAX_WARNING_CHARS = 64
MAX_OUTPUT_TOKENS = 8192
MIN_OUTPUT_BYTES = 4096
HAS_DESCRIPTOR_OPEN = os.open in os.supports_dir_fd
HAS_DESCRIPTOR_STAT = os.stat in os.supports_dir_fd
HAS_NOFOLLOW_STAT = os.stat in os.supports_follow_symlinks
CODE_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".swift", ".c", ".h", ".cc",
    ".cpp", ".hpp", ".cs", ".rb", ".php", ".sh", ".bash", ".zsh",
    ".sql", ".vue", ".svelte", ".md", ".rst", ".toml", ".yaml",
    ".yml", ".json", ".xml", ".html", ".css", ".scss", ".tf",
}
SKIP_PARTS = {
    ".git", ".venv", "venv", "node_modules", "vendor", "dist", "build",
    "target", "coverage", "__pycache__", "generated", "third_party",
}
SECRET_PARTS = {"secret", "secrets", "credential", "credentials"}
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "Gemfile.lock"}
SECRET_NAME = re.compile(r"(^|[._-])(\.env|secrets?|credentials?)([._-]|$)|\.pem$|\.key$", re.I)
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
DECLARATION = re.compile(
    r"^[ \t]*(?:export[ \t]+)?(?:async[ \t]+)?(?:function|class|interface|type|enum|struct|trait|fn|def|func|const|let|var)[ \t]+([A-Za-z_$][\w$]*)",
    re.M,
)


class MapError(ValueError):
    """Raised when the requested repository scope cannot be read safely."""


def _git(root, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise MapError(detail or "git command failed")
    return result


def _tracked(root):
    result = _git(root, "ls-files", "--stage", "-z")
    records = []
    for item in result.stdout.split(b"\0"):
        if not item:
            continue
        metadata, raw_path = item.split(b"\t", 1)
        mode, oid, stage = metadata.split(b" ", 2)
        records.append((mode.decode("ascii"), oid.decode("ascii"), stage.decode("ascii"), os.fsdecode(raw_path)))
    return records


def _status(root):
    return _git(root, "status", "--porcelain", "--untracked-files=normal").stdout


def _warn(warnings, message):
    message = _bounded(message, MAX_WARNING_CHARS)
    warnings["count"] += 1
    if len(warnings["items"]) < MAX_WARNING_SAMPLES:
        warnings["items"].append(message)


def _bounded(value, max_chars):
    if len(value) <= max_chars:
        return value
    return value[:max_chars - 1] + "…"


def _identity(stat):
    return stat.st_dev, stat.st_ino, stat.st_mode, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _read_tracked(root_fd, relative, remaining, on_bytes):
    """Read one regular file through held directory descriptors without following links."""
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    directory_flags = flags | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = flags | os.O_NOFOLLOW | os.O_NONBLOCK
    opened_dirs = []
    parent_fd = root_fd
    try:
        parts = PurePosixPath(relative).parts
        for component in parts[:-1]:
            approved = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
            if not stat_is_directory(approved.st_mode):
                raise MapError("directory component changed or is not a directory")
            next_fd = os.open(component, directory_flags, dir_fd=parent_fd)
            opened_dirs.append(next_fd)
            opened = os.fstat(next_fd)
            if _identity(approved) != _identity(opened):
                raise MapError("directory component changed while opening")
            parent_fd = next_fd

        name = parts[-1]
        approved = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat_is_regular(approved.st_mode):
            raise MapError("tracked path is not a regular file")
        if approved.st_size > MAX_FILE_BYTES:
            raise MapError(f"exceeds {MAX_FILE_BYTES} byte file limit")
        if approved.st_size > remaining:
            raise MapError("total read limit reached")

        file_fd = os.open(name, file_flags, dir_fd=parent_fd)
        try:
            opened = os.fstat(file_fd)
            if not stat_is_regular(opened.st_mode) or _identity(approved) != _identity(opened):
                raise MapError("file changed before it could be read")
            chunks = []
            read_bytes = 0
            while True:
                allowance = min(MAX_FILE_BYTES - read_bytes, remaining - read_bytes, 64 * 1024)
                if allowance <= 0:
                    break
                chunk = os.read(file_fd, allowance)
                if not chunk:
                    break
                chunks.append(chunk)
                read_bytes += len(chunk)
                on_bytes(len(chunk))
            after = os.fstat(file_fd)
            path_after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if _identity(opened) != _identity(after) or _identity(after) != _identity(path_after):
                raise MapError("file changed while being read")
            if after.st_size > read_bytes:
                raise MapError("file exceeds available read allowance")
            return b"".join(chunks)
        finally:
            os.close(file_fd)
    finally:
        for descriptor in reversed(opened_dirs):
            os.close(descriptor)


def stat_is_directory(mode):
    return (mode & 0o170000) == 0o040000


def stat_is_regular(mode):
    return (mode & 0o170000) == 0o100000


def _require_safe_open():
    required_flags = ("O_DIRECTORY", "O_NOFOLLOW")
    if any(not hasattr(os, flag) for flag in required_flags):
        raise MapError("this platform lacks no-follow directory opens required for safe mapping")
    if not HAS_DESCRIPTOR_OPEN or not HAS_DESCRIPTOR_STAT:
        raise MapError("this platform lacks descriptor-relative file operations required for safe mapping")
    if not HAS_NOFOLLOW_STAT:
        raise MapError("this platform cannot inspect tracked paths without following symlinks")


def _focus_paths(root, focus):
    validated = []
    for raw in focus:
        if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
            raise MapError(f"invalid focus path: {raw!r}")
        path = PurePosixPath(raw)
        if path.is_absolute() or any(part in ("", ".", "..") for part in raw.split("/")):
            raise MapError(f"focus path must stay inside the repository: {raw}")
        target = root.joinpath(*path.parts)
        cursor = root
        for part in path.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise MapError(f"focus path contains a symlink: {raw}")
        if not target.exists():
            raise MapError(f"focus path does not exist: {raw}")
        if not (target.is_file() or target.is_dir()):
            raise MapError(f"focus path is not a file or directory: {raw}")
        validated.append(path.as_posix().rstrip("/"))
    return validated


def _in_focus(path, focus):
    return not focus or any(path == item or path.startswith(item + "/") for item in focus)


def _tokens(value):
    parts = []
    for identifier in IDENTIFIER.findall(value):
        split = re.sub(r"([a-z])([A-Z])", r"\1 \2", identifier)
        for part in re.split(r"[_\W]+", split.casefold()):
            if len(part) > 1:
                if part.endswith("ing") and len(part) > 5:
                    part = part[:-3] + ("e" if part[:-3].endswith("c") else "")
                elif part.endswith("s") and len(part) > 4:
                    part = part[:-1]
                parts.append(part)
    return set(parts)


def _python_symbols(source):
    tree = ast.parse(source)
    definitions, references = [], set()

    class Visit(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            definitions.append({"name": node.name, "kind": "function", "line": node.lineno})
            self.generic_visit(node)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            definitions.append({"name": node.name, "kind": "class", "line": node.lineno})
            self.generic_visit(node)

        def visit_Name(self, node):
            references.add(node.id)

        def visit_Attribute(self, node):
            references.add(node.attr)
            self.generic_visit(node)

    Visit().visit(tree)
    return definitions, references


def _symbols(path, source):
    if path.endswith((".py", ".pyi")):
        definitions, refs = _python_symbols(source)
        return definitions, refs
    definitions = [
        {"name": match.group(1), "kind": "declaration", "line": source.count("\n", 0, match.start(1)) + 1}
        for match in DECLARATION.finditer(source)
    ]
    return definitions, set(IDENTIFIER.findall(source))


def _skip_reason(path, mode):
    parts = PurePosixPath(path).parts
    name = parts[-1]
    if mode not in ("100644", "100755"):
        return "symlink or submodule"
    if any(part in SKIP_PARTS for part in parts) or name in SKIP_NAMES:
        return "generated, vendor, cache, or lockfile policy"
    if any(part.casefold() in SECRET_PARTS for part in parts[:-1]):
        return "secret-style directory policy"
    if SECRET_NAME.search(name):
        return "secret-like filename policy"
    if Path(name).suffix.casefold() not in CODE_EXTENSIONS:
        return "unsupported file type"
    return None


def _render_entry(entry):
    symbols = ", ".join(f"{item['name']}@{item['line']}" for item in entry["symbols"])
    suffix = f" — {symbols}" if symbols else ""
    return f"- {entry['path']} [{entry['language']}] — {entry['reason']}{suffix}"


def render_text(result):
    """Render the bounded map and label total versus entry-only estimates."""
    lines = [
        f"repo-map/{result['schema'].rsplit('/', 1)[-1]} HEAD={result['head']} {'dirty' if result['dirty'] else 'clean'} non-atomic",
        f"task: {result['task']}",
    ]
    if result.get("task_truncated", False):
        lines.append(f"task shortened from {result['task_original_chars']} chars")
    lines.extend(_render_entry(entry) for entry in result["entries"])
    if not result["entries"]:
        lines.append("- no files selected")
    lines.append(
        f"tokens≈{result['estimated_tokens']} total, {result['estimated_entry_tokens']} entries; "
        f"limit={result['max_tokens']} (UTF-8 byte estimate, not provider-tokenized)"
    )
    lines.append(
        f"omitted={result['diagnostics'].get('omitted_files', 0)} "
        f"unmatched={result['diagnostics'].get('unmatched_files', 0)} "
        f"outside-focus={result['diagnostics'].get('outside_focus_files', 0)} "
        f"skipped={result['diagnostics'].get('skipped_files', 0)} "
        f"warnings={result['diagnostics'].get('warning_count', 0)} "
        f"shown={len(result['diagnostics'].get('warnings', []))} "
        f"warning-details-omitted={result['diagnostics'].get('warnings_omitted', 0)} "
        f"reads={result['diagnostics']['read_bytes']}B"
    )
    lines.append(f"observation={'changed' if result.get('observation_changed', False) else 'stable checks'}, non-atomic; untracked files not read")
    lines.extend(f"! {warning}" for warning in result["diagnostics"].get("warnings", []))
    if not result["budget_satisfied"]:
        lines.append("! metadata alone exceeds budget; entries omitted")
    return "\n".join(lines)


def render_json(result):
    """Render the bounded wire view; omitted zero-count diagnostics mean zero."""
    view = {
        "schema": result["schema"],
        "head": result["head"],
        "dirty": result["dirty"],
        "task": result["task"],
        "entries": [
            {
                "path": entry["path"],
                "language": entry["language"],
                "symbols": entry["symbols"],
                "reason": entry["reason"],
                "sha256": entry["file_sha256"],
            }
            for entry in result["entries"]
        ],
        "total_tokens": result["estimated_tokens"],
        "entry_tokens": result["estimated_entry_tokens"],
        "limit": result["max_tokens"],
        "budget_ok": result["budget_satisfied"],
        "consistency": result["consistency"],
        "read_bytes": result["diagnostics"]["read_bytes"],
        "omissions": {
            key: result["diagnostics"][source]
            for key, source in (
                ("budget", "omitted_files"),
                ("unmatched", "unmatched_files"),
                ("outside_focus", "outside_focus_files"),
                ("skipped", "skipped_files"),
            )
            if result["diagnostics"].get(source, 0)
        },
    }
    if result.get("observation_changed"):
        view["observation_changed"] = True
    if result.get("task_truncated"):
        view["task_truncated_chars"] = result["task_original_chars"] - len(result["task"])
    if result["diagnostics"].get("warning_count", 0):
        view["warning_count"] = result["diagnostics"]["warning_count"]
        view["warnings"] = result["diagnostics"]["warnings"]
        view["warnings_omitted"] = result["diagnostics"]["warnings_omitted"]
    return json.dumps(view, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _output_bytes(result):
    return max(len(render_text(result).encode("utf-8")), len(render_json(result).encode("utf-8"))) + 1


def _total_tokens(result):
    return (_output_bytes(result) + 3) // 4


def _fit_final_output(result, output_limit_bytes):
    """Enforce the wire-size cap after JSON escaping and all metadata are final."""
    diagnostics = result["diagnostics"]
    warning_count = diagnostics.get("warning_count", 0)
    while _output_bytes(result) > output_limit_bytes and diagnostics.get("warnings"):
        diagnostics["warnings"].pop()
        diagnostics["warnings_omitted"] = warning_count - len(diagnostics["warnings"])

    if _output_bytes(result) > output_limit_bytes and result.get("task"):
        displayed_task_length = len(result["task"])
        result["task"] = ""
        result["task_truncated"] = True
        result.setdefault("task_original_chars", displayed_task_length)

    while _output_bytes(result) > output_limit_bytes and result["entries"]:
        result["entries"].pop()
        diagnostics["omitted_files"] += 1

    result["estimated_entry_tokens"] = sum(
        max(1, (len(_render_entry(entry).encode("utf-8")) + 3) // 4)
        for entry in result["entries"]
    )
    result["estimated_tokens"] = _total_tokens(result)
    result["budget_satisfied"] = result["estimated_tokens"] <= result["max_tokens"]
    if _output_bytes(result) > output_limit_bytes:
        raise MapError("rendered repository map exceeds output limit")


def build_map(project: Path, task: str, *, focus=(), max_tokens=2000, include_candidates=False) -> dict:
    """Build a bounded map from tracked repository files without writing to it."""
    if not isinstance(task, str) or not task.strip():
        raise MapError("task must be a non-empty string")
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= MAX_OUTPUT_TOKENS:
        raise MapError(f"max_tokens must be between 1 and {MAX_OUTPUT_TOKENS}")
    _require_safe_open()
    task_for_map = _bounded(task, MAX_TASK_CHARS)
    task_for_output = _bounded(task_for_map, 120)
    task_truncated = len(task_for_map) != len(task) or len(task_for_output) != len(task_for_map)
    root = Path(project).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise MapError("project must be an explicit existing directory")
    root = root.resolve(strict=True)
    top = _git(root, "rev-parse", "--show-toplevel").stdout.decode().strip()
    if Path(top).resolve() != root:
        raise MapError("project must be the Git repository root")
    head = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", head):
        raise MapError("could not identify repository HEAD")
    focus = _focus_paths(root, tuple(focus))
    records = _tracked(root)
    if len(records) > MAX_FILES:
        raise MapError(f"repository has more than {MAX_FILES} tracked files; narrow the checkout")
    if any(stage != "0" for _, _, stage, _ in records):
        raise MapError("Git index has unresolved paths; resolve them before mapping")
    status_before = _status(root)
    dirty = bool(status_before)
    task_terms = _tokens(task_for_map)
    candidates, skipped, bytes_read = [], 0, 0
    warnings = {"count": 0, "items": []}
    focused_records = [(mode, oid, path) for mode, oid, _, path in records if _in_focus(path, focus)]
    if focus and not any(_in_focus(path, focus) for _, _, _, path in records):
        raise MapError("focus path contains no tracked files")
    if len(focused_records) > MAX_FILES:
        raise MapError(f"focus includes more than {MAX_FILES} tracked files")

    parsed = []
    bytes_counter = [0]
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        root_stat = root.stat()
        if _identity(os.fstat(root_fd)) != _identity(root_stat):
            raise MapError("repository root changed while opening")
        for mode, oid, relative in focused_records:
            reason = _skip_reason(relative, mode)
            if reason:
                skipped += 1
                continue
            try:
                data = _read_tracked(
                    root_fd,
                    relative,
                    MAX_TOTAL_BYTES - bytes_counter[0],
                    lambda amount: bytes_counter.__setitem__(0, bytes_counter[0] + amount),
                )
                bytes_read = bytes_counter[0]
                if b"\0" in data:
                    skipped += 1
                    _warn(warnings, f"{relative}: binary content")
                    continue
                try:
                    source = data.decode("utf-8")
                except UnicodeDecodeError:
                    skipped += 1
                    _warn(warnings, f"{relative}: not UTF-8 text")
                    continue
                digest = hashlib.sha256(data).hexdigest()
                try:
                    definitions, references = _symbols(relative, source)
                except SyntaxError as exc:
                    skipped += 1
                    _warn(warnings, f"{relative}: malformed Python at line {exc.lineno or '?'}")
                    continue
                except RecursionError:
                    skipped += 1
                    _warn(warnings, f"{relative}: parser/visitor depth limit reached")
                    continue
                parsed.append((relative, oid, digest, definitions, references, source))
            except (MapError, OSError) as exc:
                bytes_read = bytes_counter[0]
                skipped += 1
                _warn(warnings, f"{relative}: {exc}")
    finally:
        os.close(root_fd)

    head_after = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
    records_after = _tracked(root)
    if head_after != head or records_after != records:
        raise MapError("repository HEAD or index changed during map; retry")
    status_after = _status(root)
    dirty_after = bool(status_after)
    observation_changed = status_after != status_before
    dirty = dirty_after

    relevant_names = {
        symbol["name"]
        for _, _, _, definitions, _, _ in parsed
        for symbol in definitions
        if _tokens(symbol["name"]) & task_terms
    }
    unmatched = 0
    for relative, oid, digest, definitions, references, source in parsed:
        path_terms = _tokens(relative)
        symbol_terms = set().union(*(_tokens(item["name"]) for item in definitions)) if definitions else set()
        matched = sorted(task_terms & (path_terms | symbol_terms))
        focused = bool(focus)
        referenced = sorted(references & relevant_names)
        score = 4 * len(matched) + 6 * len(referenced) + (100 if focused else 0)
        if not score:
            unmatched += 1
            continue
        reasons = []
        if focused:
            reasons.append("explicitly focused path")
        if matched:
            reasons.append("task terms: " + ", ".join(matched))
        if referenced:
            reasons.append("references relevant symbols: " + ", ".join(referenced))
        relevant_symbols = [
            item for item in definitions
            if _tokens(item["name"]) & task_terms or item["name"] in referenced
        ]
        for name in sorted(references & relevant_names):
            if not any(item["name"] == name for item in relevant_symbols):
                relevant_symbols.append({"name": name, "kind": "reference", "line": source_line(source, name)})
        candidates.append({
            "path": relative,
            "_source": source,
            "language": Path(relative).suffix.lower().lstrip(".") or "text",
            "symbols": sorted(relevant_symbols, key=lambda item: (item["line"], item["name"])),
            "reason": "; ".join(reasons),
            "file_sha256": digest,
            "_index_oid": oid,
            "_score": score,
        })
    candidates.sort(key=lambda item: (-item["_score"], item["path"]))
    if include_candidates:
        result_candidates = []
        for item in candidates:
            row = {key: value for key, value in item.items() if not key.startswith("_")}
            row["source"] = item["_source"]
            result_candidates.append(row)
    else:
        result_candidates = None
    selected = []
    entry_tokens = 0
    output_limit_bytes = max(MIN_OUTPUT_BYTES, max_tokens * 4)
    diagnostics = {
        "omitted_files": len(candidates),
        "read_bytes": bytes_read,
        "warnings": warnings["items"],
    }
    for key, count in (
        ("unmatched_files", unmatched),
        ("outside_focus_files", len(records) - len(focused_records)),
        ("skipped_files", skipped),
    ):
        if count:
            diagnostics[key] = count
    if warnings["count"]:
        diagnostics.update({
            "warning_count": warnings["count"],
            "warnings_omitted": warnings["count"] - len(warnings["items"]),
        })
    result = {
        "schema": "context-ai/repo-map/v1",
        "head": head,
        "dirty": dirty,
        "consistency": "non-atomic",
        "task": task_for_output,
        "entries": selected,
        "estimated_tokens": 0,
        "estimated_entry_tokens": 0,
        "max_tokens": max_tokens,
        "output_limit_bytes": output_limit_bytes,
        "budget_satisfied": False,
        "diagnostics": diagnostics,
    }
    if task_truncated:
        result["task_truncated"] = True
        result["task_original_chars"] = len(task)
    if observation_changed:
        result["observation_changed"] = True
    result["estimated_tokens"] = _total_tokens(result)
    for candidate in candidates:
        candidate.pop("_score")
        candidate.pop("_index_oid")
        line = _render_entry(candidate)
        cost = max(1, (len(line.encode("utf-8")) + 3) // 4)
        selected.append(candidate)
        result["diagnostics"]["omitted_files"] -= 1
        result["estimated_entry_tokens"] = entry_tokens + cost
        result["estimated_tokens"] = _total_tokens(result)
        result["budget_satisfied"] = result["estimated_tokens"] <= max_tokens
        if not result["budget_satisfied"] or _output_bytes(result) > output_limit_bytes:
            selected.pop()
            result["diagnostics"]["omitted_files"] += 1
            result["estimated_entry_tokens"] = entry_tokens
            result["estimated_tokens"] = _total_tokens(result)
            result["budget_satisfied"] = result["estimated_tokens"] <= max_tokens
            continue
        entry_tokens += cost
    result["estimated_tokens"] = _total_tokens(result)
    result["budget_satisfied"] = result["estimated_tokens"] <= max_tokens
    _fit_final_output(result, output_limit_bytes)
    if include_candidates:
        result["_candidates"] = result_candidates
    return result


def source_line(source, name):
    match = re.search(rf"\b{re.escape(name)}\b", source)
    return source.count("\n", 0, match.start()) + 1 if match else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a bounded, read-only repository map.")
    parser.add_argument("--project", required=True, type=Path, help="explicit Git repository root")
    parser.add_argument("--task", required=True, help="task to map")
    parser.add_argument("--focus", action="append", default=[], metavar="RELATIVE_PATH")
    parser.add_argument("--max-tokens", type=int, default=2000)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        result = build_map(args.project, args.task, focus=args.focus, max_tokens=args.max_tokens)
    except (MapError, OSError) as exc:
        parser.error(str(exc))
    if args.format == "json":
        print(render_json(result))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
