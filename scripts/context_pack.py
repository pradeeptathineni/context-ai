#!/usr/bin/env python3
"""scripts/context_pack.py - Select, freeze and export source-bound task packs."""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import sys
import tempfile

import repo_map

SCHEMA_VERSION = 1
MAX_TASK_CHARS = 2048
MAX_ITEMS = 64
MAX_STORE_OBJECT = 2 * 1024 * 1024
MAX_STORE_BYTES = 64 * 1024 * 1024
MAX_STORE_OBJECTS = 4096
MAX_GUIDANCE = 65536


class ContextPackError(ValueError):
    """A bounded API failure with a stable machine-readable code."""
    def __init__(self, code, message):
        self.code = code
        self.message = message[:240]
        super().__init__(self.message)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise ContextPackError("invalid_project", "Git observation failed")
    return result.stdout


def _observation(root, project_id):
    head = _git(root, "rev-parse", "HEAD").decode("ascii", "strict").strip()
    index_entries = _git(root, "ls-files", "--stage", "-z")
    status = _git(root, "status", "--porcelain", "--untracked-files=normal")
    return {"project_id": project_id, "head": head, "dirty": bool(status),
            "index_sha256": _sha(index_entries), "status_sha256": _sha(status),
            "observation_changed": False, "consistency": "non-atomic"}


def _safe_root(path, code):
    p = Path(path).expanduser()
    if p.is_symlink() or not p.is_dir():
        raise ContextPackError(code, "configured source root must be an existing directory")
    p = p.resolve(strict=True)
    if not (p / ".git").exists() and not (subprocess.run(
            ["git", "-C", str(p), "rev-parse", "--show-toplevel"], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL).returncode == 0):
        raise ContextPackError(code, "configured root is not a Git checkout")
    top = Path(_git(p, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if top != p:
        raise ContextPackError(code, "configured root must be a Git repository root")
    return p


def _tracked_records(root):
    return {path: (mode, stage) for mode, _, stage, path in repo_map._tracked(root)
            if stage == "0"}


def _context_observation(root, counter=None):
    observed = _observation(root, "context-source")
    records = _tracked_records(root)
    inputs = ["resources.yaml", "sources.lock.json", "capabilities.yaml"]
    inputs.extend(sorted(path for path in records if path.startswith("loadouts/") and path.endswith(".yaml")))
    digests = {}
    read_counter = counter if counter is not None else [0]
    for relative in dict.fromkeys(inputs):
        if relative not in records:
            continue
        data = _read(root, relative, repo_map.MAX_TOTAL_BYTES - read_counter[0], read_counter)
        digests[relative] = _sha(data)
    observed["input_digests"] = digests
    return observed


def _read(root, relative, budget, counter=None):
    repo_map._require_safe_open()
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or any(x in (".", "..") for x in path.parts):
        raise ContextPackError("source_drift", "bound source path is invalid")
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    count = [0]
    try:
        st = os.stat(root)
        if repo_map._identity(os.fstat(root_fd)) != repo_map._identity(st):
            raise ContextPackError("source_drift", "source root changed")
        def charge(amount):
            count[0] += amount
            if counter is not None:
                counter[0] += amount
        return repo_map._read_tracked(root_fd, path.as_posix(), budget, charge)
    except (OSError, repo_map.MapError) as e:
        raise ContextPackError("source_drift", "bound source could not be safely reread") from e
    finally:
        os.close(root_fd)


def _lines_window(text, start, limit=40):
    lines = text.splitlines(keepends=True)
    if not lines:
        return 1, 0, ""
    start = max(1, min(start, len(lines)))
    end = min(len(lines), start + limit - 1)
    return start, end, "".join(lines[start - 1:end])


def _fence(content):
    """Adapt Repomix's longest-backtick-run delimiter rule (MIT; see provenance)."""
    runs = re.findall(r"`+", content)
    return "`" * max(3, max((len(run) for run in runs), default=0) + 1)


@contextmanager
def _locked(store):
    fd = os.open(store / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _write(store, name, value):
    data = _json(value).encode("utf-8")
    if len(data) > MAX_STORE_OBJECT:
        raise ContextPackError("store_full", "stored object exceeds the size limit")
    target = store / name
    if target.exists() or target.is_symlink():
        raise ContextPackError("store_invalid", "immutable object already exists")
    existing = [entry for entry in store.iterdir() if entry.name != ".lock"]
    if len(existing) >= MAX_STORE_OBJECTS or sum(entry.stat().st_size for entry in existing) + len(data) > MAX_STORE_BYTES:
        raise ContextPackError("store_full", "private store reached its configured bound")
    fd, temp = tempfile.mkstemp(prefix=".tmp-", dir=store)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, target, follow_symlinks=False)
    except OSError as e:
        raise ContextPackError("store_invalid", "could not persist immutable object") from e
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def _load(store, name):
    path = store / name
    if path.is_symlink():
        raise ContextPackError("store_invalid", "stored object is missing or oversized")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > MAX_STORE_OBJECT:
                raise ContextPackError("store_invalid", "stored object is missing, unsafe or oversized")
            chunks, left = [], info.st_size
            while left:
                block = os.read(fd, min(left, 64 * 1024))
                if not block:
                    raise ContextPackError("store_invalid", "stored object ended during read")
                chunks.append(block)
                left -= len(block)
            value = json.loads(b"".join(chunks).decode("utf-8"))
        finally:
            os.close(fd)
    except (OSError, ValueError, UnicodeError) as e:
        raise ContextPackError("store_invalid", "stored object is invalid") from e
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ContextPackError("store_invalid", "stored object version is unsupported")
    if name == "binding.json" and set(value) != {"schema_version", "binding"}:
        raise ContextPackError("store_invalid", "stored binding has unknown fields")
    if name.startswith("candidates-") and set(value) != {
            "schema_version", "candidate_set_id", "task", "project", "context", "items", "omissions", "limits"}:
        raise ContextPackError("store_invalid", "stored candidate set has unknown fields")
    if name.startswith("preview-") and set(value) != {
            "schema_version", "preview_id", "candidate_set_id", "pack_id", "requested_ids", "included_ids",
            "omissions", "project", "context", "limits", "renders", "_manifest"}:
        raise ContextPackError("store_invalid", "stored preview has unknown fields")
    return value


class ContextPackService:
    """Create ranked candidates and immutable, source-verified exports."""
    def __init__(self, project, *, store, context_root=None, project_id="selected-project"):
        self.project = _safe_root(project, "invalid_project")
        self.context_root = _safe_root(context_root or Path(__file__).resolve().parent.parent,
                                       "invalid_request")
        self.store = Path(store).expanduser()
        if self.store.exists() and (self.store.is_symlink() or not self.store.is_dir()):
            raise ContextPackError("binding_mismatch", "store must be a private directory")
        self.store.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.store, 0o700)
        self.store = self.store.resolve()
        if self.store.is_relative_to(self.project) or self.store.is_relative_to(self.context_root):
            raise ContextPackError("binding_mismatch", "store must be outside source trees")
        if not isinstance(project_id, str) or not project_id or len(project_id) > 120:
            raise ContextPackError("invalid_request", "project_id must be a short non-empty string")
        self.project_id = project_id
        binding = {"project": str(self.project), "context_root": str(self.context_root),
                   "project_id": project_id}
        with _locked(self.store):
            path = self.store / "binding.json"
            if path.exists():
                existing = _load(self.store, "binding.json")
                if existing.get("binding") != binding:
                    raise ContextPackError("binding_mismatch", "store belongs to another configured source")
            else:
                _write(self.store, "binding.json", {"schema_version": 1, "binding": binding})

    def candidates(self, task, *, focus=(), guidance_ids=()):
        if not isinstance(task, str) or not task.strip() or len(task) > MAX_TASK_CHARS:
            raise ContextPackError("invalid_request", "task must contain 1 to 2048 characters")
        if len(set(guidance_ids)) != len(tuple(guidance_ids)):
            raise ContextPackError("invalid_request", "duplicate guidance ID")
        project_obs = _observation(self.project, self.project_id)
        map_result = repo_map.build_map(self.project, task, focus=focus, max_tokens=8192,
                                        include_candidates=True)
        items, omissions = [], []
        ranked = map_result.get("_candidates", [])
        for candidate in ranked:
            source = candidate["source"]
            line = candidate["symbols"][0]["line"] if candidate["symbols"] else 1
            first, last, excerpt = _lines_window(source, line)
            raw = excerpt.encode("utf-8")
            if len(raw) > 4096:
                omissions.append({"path": candidate["path"], "reason": "window exceeds 4096 bytes"})
                continue
            item = {"item_id": secrets.token_hex(12), "kind": "source", "title": candidate["path"],
                    "rank": len(items) + 1, "reason": candidate["reason"],
                    "source": {"owner": "project", "path": candidate["path"],
                               "revision": project_obs["head"], "file_sha256": candidate["file_sha256"],
                               "line_start": first, "line_end": last, "excerpt_sha256": _sha(raw)},
                    "content": excerpt, "required_by": [], "selectable": True}
            items.append(item)
            if len(items) >= MAX_ITEMS:
                break
        for warning in map_result.get("diagnostics", {}).get("warnings", []):
            omissions.append({"reason": warning[:160]})
        context_reads = [map_result.get("diagnostics", {}).get("read_bytes", 0)]
        context_obs = _context_observation(self.context_root, context_reads)
        groups = []
        if guidance_ids:
            sys.path.insert(0, str(self.context_root / "scripts"))
            try:
                import context_ai
                allowed = {p for p in context_ai.active_files() if p.endswith(".md")}
                # The resource resolver is the authority for active dependency closure.
                for gid in guidance_ids:
                    if not isinstance(gid, str) or not gid.startswith("guidance:"):
                        raise ContextPackError("unknown_guidance", "guidance IDs must use guidance:<resource>")
                    root = gid[len("guidance:"):]
                    if root not in allowed:
                        raise ContextPackError("unknown_guidance", "guidance resource is not active")
                    closure = context_ai.resources([root])
                    notices = context_ai.source_notices(closure)
                    lock_raw = _read(self.context_root, "sources.lock.json",
                                     repo_map.MAX_TOTAL_BYTES - context_reads[0], context_reads)
                    pinned = {path: digest for source in json.loads(lock_raw.decode("utf-8"))["sources"]
                              for path, digest in source["files"].items()}
                    group_id = "guidance:" + root
                    group = []
                    for path, body in list(closure.items()) + list(notices.items()):
                        rel = path
                        data = _read(self.context_root, rel,
                                     repo_map.MAX_TOTAL_BYTES - context_reads[0], context_reads)
                        if rel.startswith("sourced/") and pinned.get(rel) != _sha(data):
                            raise ContextPackError("unknown_guidance", "registered source bytes differ from their pin")
                        text = data.decode("utf-8")
                        kind = "guidance" if path == root else ("support" if not path.endswith(".md") else "guidance")
                        if path in notices:
                            kind = "notice"
                        if len(data) > MAX_GUIDANCE and kind != "notice":
                            raise ContextPackError("unknown_guidance", "required guidance group exceeds 64 KiB")
                        rows = text.splitlines(keepends=True)
                        body = text
                        item_id = secrets.token_hex(12)
                        group.append({"item_id": item_id, "kind": kind, "title": path,
                                      "rank": len(items) + len(group) + 1,
                                      "reason": "explicit guidance selection" if path == root else "required dependency or notice",
                                      "source": {"owner": "context", "path": rel,
                                                 "revision": context_obs["head"], "file_sha256": _sha(data),
                                                 "line_start": 1, "line_end": len(rows),
                                                 "excerpt_sha256": _sha(data)},
                                      "content": body, "required_by": [] if path == root else [group_id],
                                      "selectable": path == root})
                    rootrow = next(x for x in group if x["title"] == root)
                    root_item_id = rootrow["item_id"]
                    rootrow["required_by"] = []
                    for child in group:
                        if child is not rootrow:
                            child["required_by"] = [root_item_id]
                    groups.append(group)
            except ContextPackError:
                raise
            except Exception as e:
                raise ContextPackError("unknown_guidance", "guidance resolution failed") from e
            finally:
                if sys.path[0] == str(self.context_root / "scripts"):
                    sys.path.pop(0)
        bounded_items = []
        for group in groups + [[item] for item in items]:
            if len(bounded_items) + len(group) <= MAX_ITEMS:
                bounded_items.extend(group)
            else:
                omissions.append({"reason": "candidate pool limit", "count": len(group)})
        items = bounded_items
        for rank, item in enumerate(items, 1):
            item["rank"] = rank
        # Keep each root's dependencies/notices atomic during later selection.
        candidate_id = secrets.token_hex(16)
        project_after = _observation(self.project, self.project_id)
        context_after = _context_observation(self.context_root, context_reads)
        if project_after != project_obs or context_after != context_obs:
            raise ContextPackError("source_drift", "source observation changed during candidate scan")
        result = {"schema_version": 1, "candidate_set_id": candidate_id, "task": task,
                  "project": project_obs, "context": context_obs, "items": items,
                  "omissions": {"count": len(omissions), "items": omissions[:8]},
                  "limits": {"max_items": MAX_ITEMS, "source_window_lines": 40,
                             "source_window_bytes": 4096, "scan_read_bytes": context_reads[0]}}
        while len(_json(result).encode("utf-8")) > 512 * 1024 and items:
            last = items[-1]
            if last["selectable"] and last["kind"] == "guidance":
                removed = {last["item_id"]} | {x["item_id"] for x in items
                                               if last["item_id"] in x["required_by"]}
            else:
                removed = {last["item_id"]}
            items[:] = [x for x in items if x["item_id"] not in removed]
            omissions.append({"reason": "candidate response size limit", "count": len(removed)})
            result["omissions"] = {"count": len(omissions), "items": omissions[:8]}
        with _locked(self.store):
            _write(self.store, "candidates-" + candidate_id + ".json", result)
        return result

    def _verify(self, source_items, project_obs, context_obs):
        total_reads = [0]
        if _observation(self.project, self.project_id) != project_obs or \
                _context_observation(self.context_root, total_reads) != context_obs:
            raise ContextPackError("source_drift", "HEAD, index, or status observation changed")
        for item in source_items:
            src = item["source"]
            root = self.project if src["owner"] == "project" else self.context_root
            records = _tracked_records(root)
            if src["path"] not in records or records[src["path"]][0] not in ("100644", "100755"):
                raise ContextPackError("source_drift", "bound source is no longer a tracked regular file")
            data = _read(root, src["path"], repo_map.MAX_TOTAL_BYTES - total_reads[0], total_reads)
            if _sha(data) != src["file_sha256"]:
                raise ContextPackError("source_drift", "a bound source file changed")
            try:
                whole = data.decode("utf-8")
            except UnicodeDecodeError as e:
                raise ContextPackError("source_drift", "bound source is no longer valid UTF-8") from e
            if src["owner"] == "project":
                lines = whole.splitlines(keepends=True)
                exact = "".join(lines[src["line_start"] - 1:src["line_end"]])
            else:
                exact = whole
            if exact != item.get("content") or _sha(exact.encode("utf-8")) != src["excerpt_sha256"]:
                raise ContextPackError("source_drift", "bound excerpt differs from current source bytes")
        if _observation(self.project, self.project_id) != project_obs or \
                _context_observation(self.context_root, total_reads) != context_obs:
            raise ContextPackError("source_drift", "source observation changed during verification")
        return total_reads[0]

    def preview(self, candidate_set_id, *, include_ids=None, exclude_ids=(), max_tokens=2000):
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= 8192:
            raise ContextPackError("invalid_request", "max_tokens must be an integer from 1 to 8192")
        if include_ids is not None and len(set(include_ids)) != len(tuple(include_ids)):
            raise ContextPackError("invalid_request", "duplicate include ID")
        if len(set(exclude_ids)) != len(tuple(exclude_ids)):
            raise ContextPackError("invalid_request", "duplicate exclude ID")
        with _locked(self.store):
            if not isinstance(candidate_set_id, str) or not re.fullmatch(r"[0-9a-f]{32}", candidate_set_id):
                raise ContextPackError("unknown_selection", "candidate set ID is invalid")
            candidates = _load(self.store, "candidates-" + candidate_set_id + ".json")
            if candidates.get("candidate_set_id") != candidate_set_id:
                raise ContextPackError("store_invalid", "candidate set identity mismatch")
            items = candidates["items"]
            ids = {item["item_id"] for item in items}
            requested = list(include_ids) if include_ids is not None else [x["item_id"] for x in items if x["selectable"]]
            if any(item not in ids for item in requested + list(exclude_ids)):
                raise ContextPackError("unknown_selection", "selection contains an unknown item ID")
            if len(set(requested)) != len(requested):
                raise ContextPackError("invalid_request", "duplicate selection ID")
            if set(requested) & set(exclude_ids):
                raise ContextPackError("invalid_request", "an item cannot be included and excluded")
            if any(not next(x for x in items if x["item_id"] == item_id)["selectable"]
                   for item_id in requested):
                raise ContextPackError("required_dependency", "required group items are selected through their root")
            chosen = set(requested) - set(exclude_ids)
            for item in items:
                if (not item["selectable"] and item["item_id"] in exclude_ids
                        and not set(item["required_by"]) & set(exclude_ids)):
                    raise ContextPackError("required_dependency", "cannot exclude a required dependency directly")
            for item in items:
                if item["selectable"] and item["kind"] == "guidance" and item["item_id"] in chosen:
                    chosen.update(x["item_id"] for x in items if item["item_id"] in x["required_by"])
            chosen = {item_id for item_id in chosen if item_id not in set(exclude_ids)}
            item_by_id = {item["item_id"]: item for item in items}
            selected_guidance = [item_by_id[item_id] for item_id in requested
                                 if item_id in chosen and item_by_id[item_id]["kind"] == "guidance"
                                 and item_by_id[item_id]["selectable"]]
            requested_items = []
            for root in selected_guidance:
                requested_items.append(root)
                requested_items.extend(item for item in items
                                       if root["item_id"] in item["required_by"] and item["item_id"] in chosen)
            requested_items.extend(sorted((item for item in items
                                            if item["kind"] == "source" and item["item_id"] in chosen),
                                           key=lambda item: (item["rank"], item["title"])))
            if not requested_items:
                raise ContextPackError("empty_selection", "no source or guidance items selected")
            verified_bytes = self._verify(requested_items, candidates["project"], candidates["context"])
            omissions = [{"item_id": x["item_id"], "reason": "excluded"}
                         for x in items if x["item_id"] not in chosen]
            task = candidates["task"]
            preview_id = secrets.token_hex(16)
            limits = {"max_tokens": max_tokens, "max_bytes_per_format": 4 * max_tokens,
                      "token_estimate": "ceil(UTF-8 bytes / 4)",
                      "preview_verification_read_bytes": verified_bytes}
            eligible = [x for x in requested_items if x["item_id"] in chosen]
            groups = []
            seen = set()
            for item in eligible:
                if item["item_id"] in seen:
                    continue
                if item["kind"] == "guidance" and item["selectable"]:
                    group = [item] + [x for x in eligible if item["item_id"] in x["required_by"]]
                else:
                    group = [item]
                groups.append(group)
                seen.update(x["item_id"] for x in group)
            selected, budget_omissions = [], []

            def make_renders(rows, omitted):
                base = {"schema_version": 1, "preview_id": preview_id, "task": task,
                        "project": candidates["project"], "context": candidates["context"],
                        "included_ids": [x["item_id"] for x in rows], "items": rows,
                        "omissions": omitted, "limits": limits,
                        "qualification": "Exact selected bytes; advisory context. User and project instructions take precedence."}
                ident = _sha(_json(base).encode())
                wire = dict(base, pack_id=ident)
                parts = [f"# Context pack {ident}", f"Preview: {preview_id}", f"Task: {task}",
                         f"Project observation: {_json(candidates['project'])}",
                         f"Context observation: {_json(candidates['context'])}",
                         f"Included IDs: {_json([x['item_id'] for x in rows])}",
                         f"Limits: {_json(limits)}",
                         "Selected exact excerpts and guidance follow. Advisory only; user and project instructions win."]
                for row in rows:
                    fence = _fence(row["content"])
                    metadata = {key: value for key, value in row.items() if key != "content"}
                    parts.extend([f"\n## {row['kind']}: {row['title']} ({row['item_id']})",
                                  f"Metadata: {_json(metadata)}",
                                  fence, row["content"], fence])
                parts.append("\nOmissions: " + (_json(omitted) if omitted else "none"))
                text_value = "\n".join(parts).rstrip("\n") + "\n"
                json_value = _json(wire) + "\n"
                result = {}
                for fmt, content in (("text", text_value), ("json", json_value)):
                    raw = content.encode("utf-8")
                    result[fmt] = {"content": content, "bytes": len(raw), "sha256": _sha(raw),
                                   "estimated_tokens": (len(raw) + 3) // 4}
                return ident, wire, result

            for group in groups:
                tentative = selected + group
                ident, wire, renders = make_renders(tentative, omissions + budget_omissions)
                if max(value["bytes"] for value in renders.values()) <= limits["max_bytes_per_format"]:
                    selected = tentative
                else:
                    budget_omissions.extend({"item_id": x["item_id"], "reason": "budget"} for x in group)
            if not selected:
                _, _, empty_renders = make_renders([], omissions + budget_omissions)
                if max(value["bytes"] for value in empty_renders.values()) > limits["max_bytes_per_format"]:
                    raise ContextPackError("budget_too_small", "fixed pack metadata exceeds the wire budget")
                raise ContextPackError("empty_selection", "no selected items fit the wire budget")
            omissions.extend(budget_omissions)
            pack_id, wire_base, renders = make_renders(selected, omissions)
            preview = {"schema_version": 1, "preview_id": preview_id, "candidate_set_id": candidate_set_id,
                       "pack_id": pack_id,
                       "requested_ids": requested, "included_ids": wire_base["included_ids"],
                       "omissions": omissions, "project": candidates["project"],
                       "context": candidates["context"], "limits": limits, "renders": renders,
                       "_manifest": wire_base}
            _write(self.store, "preview-" + preview_id + ".json", preview)
            return preview

    def export(self, preview_id, *, format="text"):
        if format not in ("text", "json"):
            raise ContextPackError("invalid_request", "format must be text or json")
        if not isinstance(preview_id, str) or not re.fullmatch(r"[0-9a-f]{32}", preview_id):
            raise ContextPackError("unknown_selection", "preview ID is invalid")
        with _locked(self.store):
            preview = _load(self.store, "preview-" + preview_id + ".json")
            if preview.get("preview_id") != preview_id:
                raise ContextPackError("store_invalid", "preview identity mismatch")
            manifest = preview.get("_manifest")
            if not isinstance(manifest, dict) or _sha(_json({k: v for k, v in manifest.items() if k != "pack_id"}).encode()) != preview.get("pack_id"):
                raise ContextPackError("store_invalid", "preview manifest integrity check failed")
            candidates = _load(self.store, "candidates-" + preview["candidate_set_id"] + ".json")
            source_items = {item["item_id"]: item for item in candidates.get("items", [])}
            if any(source_items.get(item.get("item_id")) != item for item in manifest.get("items", [])):
                raise ContextPackError("store_invalid", "preview items differ from their saved candidate set")
            render = preview.get("renders", {}).get(format)
            if not isinstance(render, dict):
                raise ContextPackError("store_invalid", "preview render is missing")
            raw = render.get("content", "").encode("utf-8")
            if len(raw) != render.get("bytes") or _sha(raw) != render.get("sha256"):
                raise ContextPackError("store_invalid", "preview render integrity check failed")
            self._verify(manifest.get("items", []), preview["project"], preview["context"])
            return raw


def _cli():
    parser = argparse.ArgumentParser(description="Create and export frozen, source-bound Context packs.")
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("candidates", "preview", "export"):
        p = subs.add_parser(name)
        p.add_argument("--project", required=True, type=Path)
        p.add_argument("--store", required=True, type=Path)
        p.add_argument("--project-id", default="selected-project")
        p.add_argument("--context-root", type=Path, default=Path(__file__).resolve().parent.parent)
        if name == "candidates":
            p.add_argument("--task", required=True)
            p.add_argument("--focus", action="append", default=[])
            p.add_argument("--guidance", action="append", default=[])
        elif name == "preview":
            p.add_argument("--candidates", required=True)
            p.add_argument("--include", action="append")
            p.add_argument("--exclude", action="append", default=[])
            p.add_argument("--max-tokens", type=int, default=2000)
            p.add_argument("--format", choices=("text", "json"), default="text")
        else:
            p.add_argument("--preview", required=True)
            p.add_argument("--format", choices=("text", "json"), default="text")
            p.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        service = ContextPackService(args.project, store=args.store, context_root=args.context_root,
                                     project_id=args.project_id)
        if args.command == "candidates":
            result = service.candidates(args.task, focus=args.focus, guidance_ids=args.guidance)
            raw = (_json(result) + "\n").encode()
        elif args.command == "preview":
            result = service.preview(args.candidates, include_ids=args.include,
                                     exclude_ids=args.exclude, max_tokens=args.max_tokens)
            raw = result["renders"][args.format]["content"].encode()
        else:
            raw = service.export(args.preview, format=args.format)
            if args.output:
                target = args.output
                parent = target.parent.absolute()
                cursor = Path(parent.anchor)
                unsafe_parent = False
                for part in parent.parts[1:]:
                    cursor = cursor / part
                    if cursor.is_symlink() or (cursor.exists() and not cursor.is_dir()):
                        unsafe_parent = True
                        break
                resolved_parent = parent.resolve(strict=True) if parent.exists() else parent
                if (unsafe_parent or target.exists() or target.is_symlink() or not parent.is_dir()
                        or resolved_parent.is_relative_to(service.project)
                        or resolved_parent.is_relative_to(service.context_root)):
                    raise ContextPackError("unsafe_output", "output must be a new file outside source trees")
                fd, temp = tempfile.mkstemp(prefix=".context-pack-", dir=resolved_parent)
                try:
                    os.fchmod(fd, 0o600)
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.link(temp, target, follow_symlinks=False)
                except FileExistsError as e:
                    raise ContextPackError("unsafe_output", "output already exists") from e
                finally:
                    try:
                        os.unlink(temp)
                    except FileNotFoundError:
                        pass
                return 0
        sys.stdout.buffer.write(raw)
        return 0
    except ContextPackError as exc:
        sys.stderr.write(_json({"error": {"code": exc.code, "message": exc.message}}) + "\n")
        return 2
    except (OSError, repo_map.MapError) as exc:
        sys.stderr.write(_json({"error": {"code": "invalid_request", "message": str(exc)[:200]}}) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
