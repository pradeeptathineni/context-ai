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
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "Gemfile.lock"}
SECRET_NAME = re.compile(r"(^|[._-])(\.env|secrets?|credentials?)([._-]|$)|\.pem$|\.key$", re.I)
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
DECLARATION = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|enum|struct|trait|fn|def|func|const|let|var)\s+([A-Za-z_$][\w$]*)",
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
        mode = metadata.split(b" ", 1)[0].decode("ascii")
        records.append((mode, os.fsdecode(raw_path)))
    return records


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
        {"name": match.group(1), "kind": "declaration", "line": source.count("\n", 0, match.start()) + 1}
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
    """Render a compact map; the budget estimate covers entry lines only."""
    lines = [
        f"Repository map (schema {result['schema']})",
        f"HEAD {result['head']} · working tree {'dirty' if result['dirty'] else 'clean'}",
        f"Task: {result['task']}",
    ]
    lines.extend(_render_entry(entry) for entry in result["entries"])
    if not result["entries"]:
        lines.append("- No matching files selected")
    omitted = result["diagnostics"]["omitted_files"]
    skipped = result["diagnostics"]["skipped_files"]
    lines.append(
        f"Estimate: {result['estimated_tokens']} tokens for entries; requested limit {result['max_tokens']} (character heuristic, not a provider tokenizer)."
    )
    lines.append(
        f"Omissions: {omitted} ranked files outside the budget; "
        f"{result['diagnostics']['unmatched_files']} unmatched; "
        f"{result['diagnostics']['outside_focus_files']} outside focus; "
        f"{skipped} skipped by type or safety policy. Untracked files are not read."
    )
    if result["diagnostics"]["warnings"]:
        lines.extend(f"Note: {warning}" for warning in result["diagnostics"]["warnings"])
    return "\n".join(lines)


def build_map(project: Path, task: str, *, focus=(), max_tokens=2000) -> dict:
    """Build a bounded map from tracked repository files without writing to it."""
    if not isinstance(task, str) or not task.strip():
        raise MapError("task must be a non-empty string")
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
        raise MapError("max_tokens must be a positive integer")
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
    dirty = bool(_git(root, "status", "--porcelain", "--untracked-files=normal").stdout)
    task_terms = _tokens(task)
    candidates, skipped, bytes_read, warnings = [], 0, 0, []
    focused_records = [(mode, path) for mode, path in records if _in_focus(path, focus)]
    if focus and not any(_in_focus(path, focus) for _, path in records):
        raise MapError("focus path contains no tracked files")
    if len(focused_records) > MAX_FILES:
        raise MapError(f"focus includes more than {MAX_FILES} tracked files")

    parsed = []
    for mode, relative in focused_records:
        reason = _skip_reason(relative, mode)
        if reason:
            skipped += 1
            continue
        file_path = root / relative
        try:
            cursor = root
            unsafe_path = False
            for part in PurePosixPath(relative).parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    unsafe_path = True
                    break
            if unsafe_path:
                skipped += 1
                warnings.append(f"{relative}: symlink in tracked path")
                continue
            if file_path.is_symlink() or not file_path.is_file():
                skipped += 1
                warnings.append(f"{relative}: tracked path is no longer a regular file")
                continue
            before = file_path.stat()
            if before.st_size > MAX_FILE_BYTES:
                skipped += 1
                warnings.append(f"{relative}: exceeds {MAX_FILE_BYTES} byte file limit")
                continue
            if bytes_read + before.st_size > MAX_TOTAL_BYTES:
                skipped += 1
                warnings.append(f"{relative}: total read limit reached")
                continue
            with file_path.open("rb") as handle:
                opened = os.fstat(handle.fileno())
                data = handle.read(MAX_FILE_BYTES + 1)
                after = os.fstat(handle.fileno())
            final_stat = file_path.stat()
            if (opened.st_ino, opened.st_size, opened.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns) or (after.st_ino, after.st_size, after.st_mtime_ns) != (final_stat.st_ino, final_stat.st_size, final_stat.st_mtime_ns):
                skipped += 1
                warnings.append(f"{relative}: changed while being read; omitted")
                continue
            bytes_read += len(data)
            if len(data) > MAX_FILE_BYTES or b"\0" in data:
                skipped += 1
                warnings.append(f"{relative}: oversized or binary content")
                continue
            try:
                source = data.decode("utf-8")
            except UnicodeDecodeError:
                skipped += 1
                warnings.append(f"{relative}: not UTF-8 text")
                continue
            digest = hashlib.sha256(data).hexdigest()
            try:
                definitions, references = _symbols(relative, source)
            except SyntaxError as exc:
                skipped += 1
                warnings.append(f"{relative}: malformed Python at line {exc.lineno or '?'}")
                continue
            parsed.append((relative, digest, definitions, references, task_terms, source))
        except OSError as exc:
            skipped += 1
            warnings.append(f"{relative}: read failed ({exc.strerror or 'I/O error'})")

    relevant_names = {
        symbol["name"]
        for _, _, definitions, _, _, _ in parsed
        for symbol in definitions
        if _tokens(symbol["name"]) & task_terms
    }
    unmatched = 0
    for relative, digest, definitions, references, _, source in parsed:
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
            "language": Path(relative).suffix.lower().lstrip(".") or "text",
            "symbols": sorted(relevant_symbols, key=lambda item: (item["line"], item["name"])),
            "reason": "; ".join(reasons),
            "file_sha256": digest,
            "_score": score,
        })
    candidates.sort(key=lambda item: (-item["_score"], item["path"]))
    selected, used = [], 0
    for candidate in candidates:
        candidate.pop("_score")
        line = _render_entry(candidate)
        cost = max(1, (len(line) + 3) // 4)
        if used + cost > max_tokens:
            continue
        selected.append(candidate)
        used += cost
    return {
        "schema": "context-ai/repo-map/v1",
        "head": head,
        "dirty": dirty,
        "task": task,
        "entries": selected,
        "estimated_tokens": used,
        "max_tokens": max_tokens,
        "diagnostics": {
            "omitted_files": len(candidates) - len(selected),
            "unmatched_files": unmatched,
            "outside_focus_files": len(records) - len(focused_records),
            "skipped_files": skipped,
            "warnings": warnings,
            "read_bytes": bytes_read,
            "read_file_limit": MAX_FILES,
        },
    }


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
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
