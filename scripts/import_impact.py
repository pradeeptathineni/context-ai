#!/usr/bin/env python3
"""Bounded static Python import impact tracing for tracked repository files."""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

from scripts import repo_map


SCHEMA = "context-ai/import-impact/v1"
DEFAULT_DEPTH = 4
MAX_DEPTH = 8
DEFAULT_NODES = 100
MAX_NODES = 200
MAX_EDGES = 2000
MAX_DIAGNOSTICS = 12
MAX_DIAGNOSTIC_CHARS = 180
MAX_TRACKED_FILES = repo_map.MAX_FILES
MAX_TOTAL_BYTES = repo_map.MAX_TOTAL_BYTES
GIT_TIMEOUT_SECONDS = 10
MODULE_PART = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")


class ImpactError(ValueError):
    """Raised when a project or requested file cannot be read safely."""


def _git(root, *args):
    try:
        result = subprocess.run(
            [
                "git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                "-c", "core.hooksPath=/dev/null",
                "-C", str(root), *args,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ImpactError("Git metadata inspection exceeded its time limit") from exc
    if result.returncode:
        raise ImpactError("could not inspect the selected Git repository")
    return result.stdout


def _project_root(project):
    root = Path(project).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ImpactError("project must be an explicit existing directory")
    root = root.resolve(strict=True)
    top = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel")).strip())
    if top.resolve() != root:
        raise ImpactError("project must be the Git repository root")
    return root


def _head(root):
    value = os.fsdecode(_git(root, "rev-parse", "HEAD")).strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", value):
        raise ImpactError("could not identify repository HEAD")
    return value


def _tracked(root):
    raw = _git(root, "ls-files", "--stage", "-z")
    records = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        metadata, raw_path = item.split(b"\t", 1)
        mode, oid, stage = metadata.split(b" ", 2)
        records.append((
            mode.decode("ascii"), oid.decode("ascii"), stage.decode("ascii"), os.fsdecode(raw_path)
        ))
    if len(records) > MAX_TRACKED_FILES:
        raise ImpactError(f"repository exceeds the {MAX_TRACKED_FILES}-file limit")
    if any(stage != "0" for _, _, stage, _ in records):
        raise ImpactError("Git index has unresolved paths; resolve them before tracing")
    return records


def _eligible_records(records):
    eligible = []
    skipped = 0
    for mode, oid, stage, path in records:
        reason = repo_map._skip_reason(path, mode)
        if reason:
            if Path(path).suffix.casefold() == ".py":
                skipped += 1
            continue
        if Path(path).suffix.casefold() != ".py":
            continue
        pure = PurePosixPath(path)
        if pure.is_absolute() or "\\" in path or "\x00" in path:
            skipped += 1
            continue
        try:
            path.encode("utf-8", "strict")
        except UnicodeEncodeError:
            skipped += 1
            continue
        eligible.append((mode, oid, stage, path))
    eligible.sort(key=lambda row: row[3])
    return eligible, skipped


def _snapshot(root, records, status):
    return {
        "head": _head(root),
        "dirty": bool(status),
        "index": records,
        "status": status,
    }


def _assert_unchanged(root, before):
    after_head = _head(root)
    after_records = _tracked(root)
    after_status = _git(
        root, "status", "--porcelain", "--untracked-files=normal", "--ignore-submodules=all"
    )
    if (after_head != before["head"] or after_records != before["index"]
            or after_status != before["status"]):
        raise ImpactError("repository changed during inspection; retry")


def _snapshot_public(before):
    return {"head": before["head"], "dirty": before["dirty"]}


def _diagnostics():
    return {"counts": {}, "items": [], "omitted_items": 0}


def _note(diagnostics, category, detail):
    diagnostics["counts"][category] = diagnostics["counts"].get(category, 0) + 1
    if len(diagnostics["items"]) < MAX_DIAGNOSTICS:
        bounded = detail[:MAX_DIAGNOSTIC_CHARS]
        if len(detail) > MAX_DIAGNOSTIC_CHARS:
            bounded = bounded[:-1] + "…"
        diagnostics["items"].append({"kind": category, "detail": bounded})
    else:
        diagnostics["omitted_items"] += 1


def _module_for(path):
    parts = list(PurePosixPath(path).parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if not parts or (parts[-1] != "__init__.py" and not parts[-1].endswith(".py")):
        return None, False
    is_package = parts[-1] == "__init__.py"
    if is_package:
        parts.pop()
    else:
        parts[-1] = parts[-1][:-3]
    if not parts or any(not MODULE_PART.fullmatch(part) for part in parts):
        return None, is_package
    return ".".join(parts), is_package


def _package_for(path):
    module, is_package = _module_for(path)
    if module is None:
        return ()
    parts = tuple(module.split("."))
    return parts if is_package else parts[:-1]


def _module_indexes(paths):
    modules = {}
    packages = {}
    for path in paths:
        module, is_package = _module_for(path)
        if module is None:
            continue
        modules.setdefault(module, []).append(path)
        if is_package:
            packages.setdefault(module, []).append(path)
    prefixes = set()
    for module in modules:
        pieces = module.split(".")
        prefixes.update(".".join(pieces[:end]) for end in range(1, len(pieces)))
    for name in modules:
        modules[name].sort()
    for name in packages:
        packages[name].sort()
    return modules, packages, prefixes


def _resolve(name, modules, prefixes):
    candidates = modules.get(name, [])
    if len(candidates) == 1:
        return candidates, None
    if len(candidates) > 1:
        return [], "ambiguous_module"
    if name in prefixes:
        return [], "namespace_package_without_file"
    return [], "unresolved_import"


def _relative_base(node, path):
    package = _package_for(path)
    ascend = node.level - 1
    if ascend > len(package):
        return None
    base = package[:len(package) - ascend]
    if node.module:
        base += tuple(node.module.split("."))
    return ".".join(base)


def _import_targets(node, path, modules, packages, prefixes):
    """Return resolvable imported files and diagnostic categories."""
    targets, issues = set(), []
    if isinstance(node, ast.Import):
        for alias in node.names:
            leaf = alias.name
            resolved, issue = _resolve(leaf, modules, prefixes)
            if issue:
                issues.append((issue, leaf))
                continue
            targets.add(resolved[0])
            pieces = leaf.split(".")
            for end in range(1, len(pieces)):
                parent = ".".join(pieces[:end])
                package_paths = packages.get(parent, [])
                if len(package_paths) == 1:
                    targets.add(package_paths[0])
                elif len(package_paths) > 1:
                    issues.append(("ambiguous_module", parent))
                elif parent in modules:
                    category = "ambiguous_module" if len(modules[parent]) > 1 else "module_parent_not_package"
                    issues.append((category, parent))
    elif isinstance(node, ast.ImportFrom):
        if node.level:
            base = _relative_base(node, path)
            if base is None or not base:
                issues.append(("invalid_relative_import", node.module or "."))
                return targets, issues
        else:
            base = node.module or ""
        if not base:
            issues.append(("unresolved_import", node.module or "."))
            return targets, issues
        base_paths, issue = _resolve(base, modules, prefixes)
        if issue:
            issues.append((issue, base))
        else:
            targets.add(base_paths[0])
        for alias in node.names:
            if alias.name == "*":
                continue
            child = f"{base}.{alias.name}"
            child_paths, child_issue = _resolve(child, modules, prefixes)
            if child_issue is None:
                # A from-list name can be either a package attribute or submodule.
                # Include the local candidate but make that uncertainty visible.
                targets.add(child_paths[0])
                if base_paths:
                    issues.append(("fromlist_module_or_attribute", child))
            elif child_issue == "ambiguous_module":
                issues.append((child_issue, child))
    return targets, issues


def _dynamic_imports(tree):
    found = []
    module_aliases = {"importlib"}
    function_aliases = {"import_module"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib" or alias.name.startswith("importlib."):
                    module_aliases.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            for alias in node.names:
                if alias.name == "import_module":
                    function_aliases.add(alias.asname or alias.name)

    def importlib_call(function):
        if not isinstance(function, ast.Attribute):
            return False
        root = function.value
        while isinstance(root, ast.Attribute):
            root = root.value
        return (
            function.attr == "import_module"
            and isinstance(root, ast.Name)
            and root.id in module_aliases
        )

    class Calls(ast.NodeVisitor):
        def visit_Call(self, node):
            function = node.func
            is_dynamic = (
                isinstance(function, ast.Name)
                and (function.id == "__import__" or function.id in function_aliases)
            ) or importlib_call(function)
            if is_dynamic:
                found.append(node.lineno)
            self.generic_visit(node)

    Calls().visit(tree)
    return found


def _read_sources(root, eligible):
    repo_map._require_safe_open()
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        if repo_map._identity(os.fstat(root_fd)) != repo_map._identity(root.stat()):
            raise ImpactError("repository root changed while opening")
        sources, total = {}, 0
        for _, _, _, path in eligible:
            try:
                raw = repo_map._read_tracked(
                    root_fd,
                    path,
                    MAX_TOTAL_BYTES - total,
                    lambda amount: None,
                )
            except (repo_map.MapError, OSError) as exc:
                raise ImpactError(f"could not safely read tracked Python source: {path}") from exc
            total += len(raw)
            if total > MAX_TOTAL_BYTES:
                raise ImpactError(f"Python source exceeds the {MAX_TOTAL_BYTES}-byte total limit")
            try:
                source = raw.decode("utf-8")
            except UnicodeDecodeError:
                sources[path] = {
                    "source": None, "tree": None, "digest": hashlib.sha256(raw).hexdigest()
                }
                continue
            try:
                tree = ast.parse(source, filename=path)
            except (SyntaxError, RecursionError, MemoryError):
                tree = None
            sources[path] = {
                "source": source, "tree": tree, "digest": hashlib.sha256(raw).hexdigest()
            }
        return sources
    finally:
        os.close(root_fd)


def _source_digest(sources):
    digest = hashlib.sha256()
    for path in sorted(sources):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sources[path]["digest"]))
    return digest.hexdigest()


def _validate_limits(max_depth, max_nodes):
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or not 0 <= max_depth <= MAX_DEPTH:
        raise ImpactError(f"max_depth must be an integer from 0 to {MAX_DEPTH}")
    if isinstance(max_nodes, bool) or not isinstance(max_nodes, int) or not 1 <= max_nodes <= MAX_NODES:
        raise ImpactError(f"max_nodes must be an integer from 1 to {MAX_NODES}")


def _validate_seed(seed, eligible_paths):
    if not isinstance(seed, str) or not seed or "\\" in seed or "\x00" in seed:
        raise ImpactError("seed must be a tracked relative Python path")
    pure = PurePosixPath(seed)
    if pure.is_absolute() or str(pure) != seed or any(part in ("", ".", "..") for part in seed.split("/")):
        raise ImpactError("seed must be a normalized repository-relative path")
    if not seed.endswith(".py") or seed not in eligible_paths:
        raise ImpactError("seed must be an eligible tracked Python file under . or src")


def list_files(project: Path) -> dict:
    """List tracked Python files in the fixed source roots without reading content."""
    root = _project_root(project)
    status = _git(root, "status", "--porcelain", "--untracked-files=normal", "--ignore-submodules=all")
    before = _snapshot(root, _tracked(root), status)
    eligible, skipped = _eligible_records(before["index"])
    _assert_unchanged(root, before)
    diagnostics = {"skipped_by_policy": skipped}
    return {
        "schema": SCHEMA,
        "files": [row[3] for row in eligible],
        "snapshot": _snapshot_public(before),
        "diagnostics": diagnostics,
    }


def inspect_impact(
    project: Path,
    seed: str,
    *,
    max_depth: int = DEFAULT_DEPTH,
    max_nodes: int = DEFAULT_NODES,
) -> dict:
    """Trace tracked static importers of a Python seed using bounded AST reads."""
    _validate_limits(max_depth, max_nodes)
    root = _project_root(project)
    status = _git(root, "status", "--porcelain", "--untracked-files=normal", "--ignore-submodules=all")
    before = _snapshot(root, _tracked(root), status)
    eligible, skipped = _eligible_records(before["index"])
    paths = {row[3] for row in eligible}
    _validate_seed(seed, paths)
    sources = _read_sources(root, eligible)
    diagnostics = _diagnostics()
    if skipped:
        diagnostics["counts"]["skipped_by_policy"] = skipped
    modules, packages, prefixes = _module_indexes(paths)
    reverse = {}
    edge_rows = set()
    for path in sorted(paths):
        if _module_for(path)[0] is None:
            _note(diagnostics, "unmapped_module_path", path)
        parsed = sources[path]
        if parsed["source"] is None:
            _note(diagnostics, "invalid_utf8", path)
            continue
        tree = parsed["tree"]
        if tree is None:
            _note(diagnostics, "syntax_or_parse_limit", path)
            continue
        for line in _dynamic_imports(tree):
            _note(diagnostics, "dynamic_import", f"{path}:{line}")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            targets, issues = _import_targets(node, path, modules, packages, prefixes)
            for category, name in issues:
                _note(diagnostics, category, f"{path}:{node.lineno} {name}")
            for dependency in sorted(targets):
                if dependency == path:
                    edge_rows.add((path, dependency, node.lineno))
                    reverse.setdefault(dependency, set()).add(path)
                else:
                    edge_rows.add((path, dependency, node.lineno))
                    reverse.setdefault(dependency, set()).add(path)

    # Edges are reported only when they participate in the seed's reverse walk.
    nodes = {seed: {"path": seed, "depth": 0, "via": None}}
    frontier = [seed]
    truncated_depth = False
    truncated_nodes = False
    for depth in range(max_depth):
        next_candidates = {}
        for dependency in sorted(frontier):
            for importer in sorted(reverse.get(dependency, ())):
                if importer in nodes:
                    continue
                next_candidates.setdefault(importer, dependency)
        if not next_candidates:
            frontier = []
            break
        available = max_nodes - len(nodes)
        ordered = sorted(next_candidates)
        if len(ordered) > available:
            truncated_nodes = True
            ordered = ordered[:available]
        for importer in ordered:
            nodes[importer] = {"path": importer, "depth": depth + 1, "via": next_candidates[importer]}
        frontier = ordered
        if truncated_nodes:
            break
    if frontier:
        if any(importer not in nodes for reached in frontier for importer in reverse.get(reached, ())):
            truncated_depth = True

    _assert_unchanged(root, before)
    source_digest = _source_digest(sources)
    included = set(nodes)
    output_edges_all = [
        {"from": source, "to": target, "line": line}
        for source, target, line in sorted(edge_rows)
        if source in included and target in included
    ]
    output_edges = output_edges_all[:MAX_EDGES]
    if len(output_edges_all) > MAX_EDGES:
        _note(diagnostics, "max_edges_reached", f"edge output capped at {MAX_EDGES}")
    complete = not diagnostics["counts"] and not truncated_depth and not truncated_nodes
    if truncated_depth:
        _note(diagnostics, "max_depth_reached", f"traversal reached depth {max_depth}")
    if truncated_nodes:
        _note(diagnostics, "max_nodes_reached", f"traversal reached {max_nodes} nodes")
    return {
        "schema": SCHEMA,
        "seed": seed,
        "snapshot": {**_snapshot_public(before), "source_digest": source_digest},
        "nodes": sorted(nodes.values(), key=lambda item: (item["depth"], item["path"])),
        "edges": output_edges,
        "complete": complete,
        "diagnostics": diagnostics,
        "qualifications": [
            "AST import syntax is a static candidate, not proof of runtime loading.",
            "Only tracked Python files under . and src are considered.",
            "Unresolved, dynamic, ambiguous, skipped and capped paths are disclosed.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Trace bounded static Python import impact.")
    parser.add_argument("--project", required=True, type=Path, help="explicit Git repository root")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="list eligible tracked Python files")
    group.add_argument("--seed", help="eligible tracked relative Python path")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--max-nodes", type=int, default=DEFAULT_NODES)
    parser.add_argument("--format", choices=("json",), default="json")
    args = parser.parse_args(argv)
    try:
        result = list_files(args.project) if args.list else inspect_impact(
            args.project, args.seed, max_depth=args.max_depth, max_nodes=args.max_nodes
        )
    except (ImpactError, OSError) as exc:
        parser.exit(2, f"import-impact: {exc}\n")
    json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
