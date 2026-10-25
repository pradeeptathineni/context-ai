#!/usr/bin/env python3
"""Compiler-backed TS/JS symbol navigation over tracked repository source.

The installed TypeScript LanguageService resolves definitions, references and
one-hop call hierarchy. This module owns the snapshot: it reads tracked,
policy-eligible source through the no-follow reader in ``repo_map``, sends the
exact text to ``code_navigation.mjs`` on stdin, validates the reply against the
captured text, and rechecks Git metadata and source bytes before returning.
"""

import argparse
import bisect
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading

# Private helpers are reused narrowly and their errors normalized: repo_map owns
# the tracked-file policy and descriptor-relative reader, import_impact owns the
# bounded Git metadata commands and the before/after metadata comparison.
from scripts import import_impact, repo_map


SCHEMA = "context-ai/code-navigation/v1"
SCHEMA_VERSION = 1
PROTOCOL = 1
SOURCE_EXTENSIONS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
# repo_map's allowlist predates these; every other exclusion still comes from it
REPO_MAP_UNLISTED = (".mts", ".cts")
MAX_TRACKED_FILES = repo_map.MAX_FILES
MAX_TOTAL_BYTES = repo_map.MAX_TOTAL_BYTES
DEFAULT_SEARCH_RESULTS = 50
DEFAULT_INSPECT_RESULTS = 100
MAX_RESULTS = 200
MAX_SITES_PER_CALL = 20
MAX_PREPARED = 50
MAX_QUERY_CHARS = 200
MAX_NAME_CHARS = 256
MAX_KIND_CHARS = 64
MAX_DIAGNOSTICS = 20
MAX_WORKER_DIAGNOSTICS = 40
MAX_MESSAGE_CHARS = 200
MAX_EXCERPT_UNITS = 4096
MAX_SELECTOR_JSON = 16 * 1024
MAX_POSITION = 10_000_000
MAX_OFFSET = 2**31
MAX_ENGINE_BYTES = 64 * 1024 * 1024
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_REPLY_BYTES = 4 * 1024 * 1024
WORKER_TIMEOUT_SECONDS = 60
WORKER = Path(__file__).resolve().with_name("code_navigation.mjs")
# names the fixed options in code_navigation.mjs; part of the snapshot identity
COMPILER_POLICY = "noLib,allowJs,checkJs,jsx=preserve,module=esnext,moduleResolution=bundler,relative-imports-only"
SNAPSHOT_ID = re.compile(r"[0-9a-f]{64}")
VERSION = re.compile(r"6\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")
DIAGNOSTIC_KIND = re.compile(r"[a-z][a-z_]{0,39}")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
# LSP line convention; U+2028/U+2029 stay inside a line so editor columns agree
LINE_BREAK = re.compile(r"\r\n|\r|\n")
MATCH_RANK = {"exact": 0, "prefix": 1, "substring": 2, "camelCase": 3}
SELECTOR_KEYS = frozenset({"file", "line", "column", "sha256"})
SELECTOR_END_KEYS = frozenset({"endLine", "endColumn"})
REPLY_KEYS = frozenset({"ok", "protocol", "engine", "diagnostics", "diagnosticTotal", "result"})
WORKER_ERROR_KINDS = frozenset({"engine_unavailable", "engine_unsupported", "engine_failed"})
QUALIFICATIONS = (
    "Relationships come from the TypeScript LanguageService over captured tracked source; they are "
    "static and do not establish runtime calls, dynamic dispatch or a complete graph.",
    "No project tsconfig, plugins, packages, type libraries or standard library were loaded; only "
    "relative imports between admitted files resolve, so type-dependent results can be missing.",
    "Only tracked, policy-eligible TS/JS files were read; untracked, symlinked, secret-like, vendor "
    "and generated paths are absent.",
    "Capture is non-atomic; Git metadata and source bytes were rechecked after the engine run.",
)
SEARCH_QUALIFICATION = "Search uses TypeScript navigate-to fuzzy matching; exact name matches sort first."
INSPECT_QUALIFICATION = (
    "Calls are one hop. References include engine alias groups such as renamed imports; "
    "isDefinition is relative to each engine group."
)
NO_CALL_QUALIFICATION = (
    "No call hierarchy item exists at the selected position; empty incoming and outgoing lists "
    "do not mean the symbol is uncalled."
)


class NavigationError(ValueError):
    """Raised for an invalid request, unsafe or changed project, unavailable engine,
    timeout or invalid engine reply. ``kind`` is a stable machine category."""

    def __init__(self, message, kind="invalid_request"):
        super().__init__(message)
        self.kind = kind


class _Positions:
    """UTF-16 offsets and 1-based line/column positions for one decoded file."""

    def __init__(self, text):
        self.units = text.encode("utf-16-le")
        self.length = len(self.units) // 2
        self.starts, self.ends = [0], []
        offset = previous = 0
        for match in LINE_BREAK.finditer(text):
            offset += len(text[previous:match.start()].encode("utf-16-le")) // 2
            self.ends.append(offset)
            offset += match.end() - match.start()
            self.starts.append(offset)
            previous = match.end()
        self.ends.append(self.length)

    def on_boundary(self, offset):
        if not 0 <= offset <= self.length:
            return False
        if offset == self.length:
            return True
        unit = self.units[2 * offset] | (self.units[2 * offset + 1] << 8)
        return not 0xDC00 <= unit <= 0xDFFF

    def position(self, offset):
        if not self.on_boundary(offset):
            return None
        line = bisect.bisect_right(self.starts, offset) - 1
        if offset > self.ends[line]:
            return None
        return line + 1, offset - self.starts[line] + 1

    def offset(self, line, column):
        if not 1 <= line <= len(self.starts):
            return None
        offset = self.starts[line - 1] + column - 1
        if offset > self.ends[line - 1] or not self.on_boundary(offset):
            return None
        return offset


class _Source:
    __slots__ = ("path", "sha256", "text", "index", "_positions")

    def __init__(self, path, sha256, text, index):
        self.path = path
        self.sha256 = sha256
        self.text = text
        self.index = index
        self._positions = None

    def positions(self):
        if self._positions is None:
            self._positions = _Positions(self.text)
        return self._positions


class _Engine:
    __slots__ = ("node", "typescript", "sha256", "worker_sha256")

    def __init__(self, node, typescript, sha256, worker_sha256):
        self.node = node
        self.typescript = typescript
        self.sha256 = sha256
        self.worker_sha256 = worker_sha256


class _Snapshot:
    __slots__ = ("id", "head", "dirty", "sources", "policy_excluded", "invalid")

    def __init__(self, snapshot_id, head, dirty, sources, policy_excluded, invalid):
        self.id = snapshot_id
        self.head = head
        self.dirty = dirty
        self.sources = sources
        self.policy_excluded = policy_excluded
        self.invalid = invalid


class _Notes:
    """Python-side observations that become public diagnostics."""

    def __init__(self):
        self.clipped = 0
        self.sites_omitted = 0
        self.calls_capped = 0

    def name(self, value):
        _require(isinstance(value, str), "name field")
        if len(value) > MAX_NAME_CHARS:
            self.clipped += 1
            return value[:MAX_NAME_CHARS - 1] + "…"
        return value


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise NavigationError(message)


def _boundary(function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except OSError as exc:
            detail = exc.strerror or type(exc).__name__
            raise NavigationError(f"could not access the project or engine safely: {detail}", "project") from exc
    return wrapper


def _guard(function, *args):
    try:
        return function(*args)
    except import_impact.ImpactError as exc:
        raise NavigationError(str(exc), "project") from exc


def _require(condition, detail):
    if not condition:
        raise NavigationError(f"invalid TypeScript worker reply: {detail}", "engine_reply")


def _count(value, upper=MAX_OFFSET):
    return type(value) is int and 0 <= value <= upper


def _clip(value, limit=MAX_MESSAGE_CHARS):
    return value if len(value) <= limit else value[:limit - 1] + "…"


def _units(value):
    # UTF-16BE byte order equals JavaScript string order, so Python and the worker sort alike
    return value.encode("utf-16-be", "surrogatepass")


def _reject_constant(name):
    raise ValueError(f"non-finite number {name}")


def _safe_relative(path):
    if not isinstance(path, str) or not path or "\\" in path or "\x00" in path or path.startswith("/"):
        return False
    if any(part in ("", ".", "..") for part in path.split("/")):
        return False
    try:
        path.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _check_max_results(max_results):
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= MAX_RESULTS:
        raise NavigationError(f"max_results must be an integer from 1 to {MAX_RESULTS}")


def _check_query(query):
    if not isinstance(query, str) or not query.strip():
        raise NavigationError("query must be a non-empty string")
    query = query.strip()
    if len(query) > MAX_QUERY_CHARS or CONTROL.search(query):
        raise NavigationError(f"query must be at most {MAX_QUERY_CHARS} printable characters")
    return query


def _check_selector(selector):
    if not isinstance(selector, dict):
        raise NavigationError("selector must be an object with file, line, column and sha256")
    keys = set(selector)
    if (not SELECTOR_KEYS <= keys or keys - SELECTOR_KEYS - SELECTOR_END_KEYS
            or len(keys & SELECTOR_END_KEYS) == 1):
        raise NavigationError("selector must be {file,line,column,sha256} or a complete search location")
    if not _safe_relative(selector["file"]):
        raise NavigationError("selector file must be a normalized repository-relative path")
    if not isinstance(selector["sha256"], str) or not SNAPSHOT_ID.fullmatch(selector["sha256"]):
        raise NavigationError("selector sha256 must be 64 lowercase hexadecimal characters")
    for key in ("line", "column", *sorted(keys & SELECTOR_END_KEYS)):
        value = selector[key]
        if type(value) is not int or not 1 <= value <= MAX_POSITION:
            raise NavigationError(f"selector {key} must be a positive integer")


def _host_path(value, label):
    if not isinstance(value, (str, os.PathLike)) or not os.fspath(value):
        raise NavigationError(f"{label} must be a host-configured absolute path", "engine_unavailable")
    path = Path(os.fspath(value))
    if not path.is_absolute():
        raise NavigationError(f"{label} must be a host-configured absolute path", "engine_unavailable")
    return path


def _file_sha256(path, label):
    try:
        with open(path, "rb") as handle:
            if os.fstat(handle.fileno()).st_size > MAX_ENGINE_BYTES:
                raise NavigationError(f"{label} exceeds the {MAX_ENGINE_BYTES}-byte limit", "engine_unavailable")
            return hashlib.sha256(handle.read(MAX_ENGINE_BYTES + 1)).hexdigest()
    except OSError as exc:
        raise NavigationError(f"could not read {label}", "engine_unavailable") from exc


def _engine(node_executable, typescript_path):
    """Check host-configured engine paths; nothing is installed or downloaded."""
    node = _host_path(node_executable, "node_executable")
    typescript = _host_path(typescript_path, "typescript_path")
    if not node.is_file() or not os.access(node, os.X_OK):
        raise NavigationError(
            f"Node executable is not available at {node}; configure an installed Node. "
            "Nothing was installed or downloaded.", "engine_unavailable",
        )
    if not typescript.is_file():
        raise NavigationError(
            f"TypeScript is not available at {typescript}; configure an installed "
            "typescript/lib/typescript.js. Nothing was installed or downloaded.", "engine_unavailable",
        )
    if not WORKER.is_file():
        raise NavigationError("the code navigation worker is missing from this Context checkout", "engine_unavailable")
    return _Engine(node, typescript, _file_sha256(typescript, "typescript_path"), _file_sha256(WORKER, "worker"))


def _eligible(records):
    eligible, excluded = [], 0
    for mode, _, _, path in records:
        if not path.endswith(SOURCE_EXTENSIONS):
            continue
        reason = repo_map._skip_reason(path, mode)
        if reason == "unsupported file type" and path.endswith(REPO_MAP_UNLISTED):
            reason = None
        if reason or not _safe_relative(path):
            excluded += 1
            continue
        eligible.append(path)
    eligible.sort()
    return eligible, excluded


def _read_sources(root, paths):
    """Read complete admitted files or refuse; a partial index would misstate references."""
    try:
        repo_map._require_safe_open()
    except repo_map.MapError as exc:
        raise NavigationError(str(exc), "project") from exc
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        if repo_map._identity(os.fstat(root_fd)) != repo_map._identity(root.stat()):
            raise NavigationError("repository root changed while opening", "project")
        admitted, invalid, total = [], [], 0
        for path in paths:
            try:
                raw = repo_map._read_tracked(root_fd, path, MAX_TOTAL_BYTES - total, lambda amount: None)
            except (repo_map.MapError, OSError) as exc:
                kind = "limits" if isinstance(exc, repo_map.MapError) and "limit" in str(exc) else "project"
                raise NavigationError(
                    f"refusing a partial index; could not safely read tracked source {path}: {exc}", kind
                ) from exc
            total += len(raw)
            digest = hashlib.sha256(raw).hexdigest()
            try:
                text = None if b"\0" in raw else raw.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            if text is None:
                invalid.append((path, digest))
                continue
            admitted.append(_Source(path, digest, text, len(admitted)))
        return admitted, invalid
    finally:
        os.close(root_fd)


def _capture(root, engine):
    status = _guard(
        import_impact._git, root, "status", "--porcelain", "--untracked-files=normal", "--ignore-submodules=all"
    )
    before = {"head": _guard(import_impact._head, root), "index": _guard(import_impact._tracked, root), "status": status}
    paths, policy_excluded = _eligible(before["index"])
    admitted, invalid = _read_sources(root, paths)
    _guard(import_impact._assert_unchanged, root, before)
    identity = {
        "schema": SCHEMA,
        "policy": COMPILER_POLICY,
        "head": before["head"],
        "index": [list(record) for record in before["index"]],
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "files": [[source.path, source.sha256] for source in admitted],
        "invalid": [list(item) for item in invalid],
        "engine": {
            "node": str(engine.node),
            "typescript": str(engine.typescript),
            "typescript_sha256": engine.sha256,
            "worker_sha256": engine.worker_sha256,
        },
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("ascii")
    return _Snapshot(
        hashlib.sha256(encoded).hexdigest(), before["head"], bool(status),
        {source.path: source for source in admitted}, policy_excluded, invalid,
    )


def _prepare(project, node_executable, typescript_path):
    if not isinstance(project, (str, os.PathLike)):
        raise NavigationError("project must be a path to a Git repository root", "project")
    engine = _engine(node_executable, typescript_path)
    root = _guard(import_impact._project_root, project)
    return root, engine, _capture(root, engine)


def _confirm(root, engine, snapshot):
    """Recheck after the engine: the same porcelain status can hide edited bytes."""
    try:
        current = _capture(root, _engine(engine.node, engine.typescript))
    except NavigationError as exc:
        raise NavigationError("project or engine changed during navigation; retry", "stale_snapshot") from exc
    if current.id != snapshot.id:
        raise NavigationError("project source or engine changed during navigation; retry", "stale_snapshot")


def _kill(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run_worker(engine, payload):
    """Run one bounded worker request and return its parsed successful reply."""
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_PAYLOAD_BYTES:
        raise NavigationError("captured source exceeds the engine request limit", "limits")
    try:
        # minimal environment: NODE_OPTIONS and similar cannot inject code into the worker
        process = subprocess.Popen(
            [str(engine.node), str(WORKER), str(engine.typescript)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(WORKER.parent), env={"PATH": os.defpath}, start_new_session=True,
        )
    except OSError as exc:
        raise NavigationError("could not start the configured Node executable", "engine_unavailable") from exc
    stdout = bytearray()
    overflow = threading.Event()

    def feed():
        try:
            process.stdin.write(data)
        except OSError:
            pass
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass

    def collect(stream, keep):
        try:
            while True:
                chunk = stream.read1(65536)
                if not chunk:
                    return
                if keep and len(stdout) + len(chunk) > MAX_REPLY_BYTES:
                    overflow.set()
                    keep = False
                    _kill(process)
                elif keep:
                    stdout.extend(chunk)
        except (OSError, ValueError):
            return

    threads = [
        threading.Thread(target=feed, daemon=True),
        threading.Thread(target=collect, args=(process.stdout, True), daemon=True),
        threading.Thread(target=collect, args=(process.stderr, False), daemon=True),
    ]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        process.wait(timeout=WORKER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill(process)
        process.wait()
    for thread in threads:
        thread.join(timeout=5)
    for stream in (process.stdout, process.stderr):
        stream.close()

    if timed_out:
        raise NavigationError(
            f"TypeScript worker exceeded the {WORKER_TIMEOUT_SECONDS}-second limit", "engine_timeout"
        )
    if overflow.is_set():
        raise NavigationError("TypeScript worker reply exceeded the output limit", "engine_reply")
    try:
        reply = json.loads(bytes(stdout).decode("utf-8"), parse_constant=_reject_constant)
    except ValueError as exc:
        raise NavigationError(
            f"TypeScript worker returned malformed output (exit status {process.returncode})", "engine_reply"
        ) from exc
    if isinstance(reply, dict) and reply.get("ok") is False:
        error = reply.get("error") if isinstance(reply.get("error"), dict) else {}
        kind = error.get("kind") if error.get("kind") in WORKER_ERROR_KINDS else "engine_failed"
        message = error.get("message") if isinstance(error.get("message"), str) else "unspecified failure"
        raise NavigationError(f"TypeScript worker failed: {_clip(message)}", kind)
    _require(process.returncode == 0, f"worker exited with status {process.returncode}")
    return reply


def _payload(snapshot, operation, max_results, **fields):
    return {
        "protocol": PROTOCOL,
        "operation": operation,
        "maxResults": max_results,
        "maxSites": MAX_SITES_PER_CALL,
        "files": [{"path": source.path, "text": source.text} for source in snapshot.sources.values()],
        **fields,
    }


def _envelope(reply):
    _require(isinstance(reply, dict) and set(reply) == REPLY_KEYS, "reply fields")
    _require(reply["ok"] is True and type(reply["protocol"]) is int and reply["protocol"] == PROTOCOL, "protocol")
    engine = reply["engine"]
    _require(
        isinstance(engine, dict) and set(engine) == {"name", "version"} and engine["name"] == "typescript"
        and isinstance(engine["version"], str) and VERSION.fullmatch(engine["version"]),
        "engine identity must be TypeScript 6.x",
    )
    items, total = reply["diagnostics"], reply["diagnosticTotal"]
    _require(
        isinstance(items, list) and len(items) <= MAX_WORKER_DIAGNOSTICS and _count(total) and total >= len(items),
        "diagnostics",
    )
    rows = []
    for item in items:
        _require(
            isinstance(item, dict) and set(item) == {"kind", "message"} and isinstance(item["kind"], str)
            and DIAGNOSTIC_KIND.fullmatch(item["kind"]) and isinstance(item["message"], str),
            "diagnostic shape",
        )
        rows.append({"kind": item["kind"], "message": _clip(item["message"])})
    return engine["version"], rows, total, reply["result"]


def _bounded(value, cap, keys=("items", "total")):
    _require(isinstance(value, dict) and set(value) == set(keys), "list shape")
    items, total = value[keys[0]], value[keys[1]]
    _require(isinstance(items, list) and len(items) <= cap and _count(total) and total >= len(items), "list bounds")
    return items, total - len(items)


def _span(value, snapshot):
    """Return (source, start, end) for a worker span that lies inside captured text."""
    _require(isinstance(value, dict) and set(value) == {"file", "start", "length"}, "span shape")
    source = snapshot.sources.get(value["file"]) if isinstance(value["file"], str) else None
    _require(source is not None, "location outside the captured snapshot")
    start, length = value["start"], value["length"]
    _require(_count(start) and _count(length), "span offsets")
    positions = source.positions()
    end = start + length
    _require(positions.on_boundary(start) and positions.on_boundary(end), "span outside file text")
    return source, start, end


def _location(source, start, end):
    positions = source.positions()
    first, last = positions.position(start), positions.position(end)
    _require(first is not None and last is not None, "span inside a line break")
    return {
        "file": source.path,
        "sha256": source.sha256,
        "line": first[0],
        "column": first[1],
        "endLine": last[0],
        "endColumn": last[1],
    }


def _excerpt(source, offset):
    """Keep the selected point in an exact, bounded slice of the captured file."""
    positions = source.positions()
    line = bisect.bisect_right(positions.starts, offset) - 1
    start = positions.starts[max(0, line - 4)]
    end = positions.ends[min(len(positions.ends) - 1, line + 4)]
    if end - start > MAX_EXCERPT_UNITS:
        start = max(start, offset - MAX_EXCERPT_UNITS // 2)
        end = min(end, start + MAX_EXCERPT_UNITS)
    # a slice must not split a surrogate pair or the middle of a CRLF
    while positions.position(start) is None:
        start += 1
    while positions.position(end) is None:
        end -= 1
    return {
        "location": _location(source, start, end),
        "text": positions.units[start * 2:end * 2].decode("utf-16-le"),
        "truncatedBefore": start > 0,
        "truncatedAfter": end < positions.length,
    }


def _kind(value):
    _require(isinstance(value, str) and len(value) <= MAX_KIND_CHARS and not CONTROL.search(value), "kind field")
    return value


def _symbols(result, snapshot, max_results, notes):
    items, omitted = _bounded(result, max_results, ("symbols", "total"))
    rows = {}
    for item in items:
        _require(isinstance(item, dict) and set(item) == {"name", "kind", "container", "matchKind", "span"}, "symbol")
        _require(isinstance(item["matchKind"], str) and item["matchKind"] in MATCH_RANK, "match kind")
        source, start, end = _span(item["span"], snapshot)
        name, kind, container = notes.name(item["name"]), _kind(item["kind"]), notes.name(item["container"])
        key = (MATCH_RANK[item["matchKind"]], _units(name), source.index, start, end, _units(kind))
        rows.setdefault(key, {"name": name, "kind": kind, "container": container,
                              "location": _location(source, start, end)})
    return [rows[key] for key in sorted(rows)], omitted


def _calls(value, snapshot, max_results, notes, site_files):
    """Validate one-hop calls; incoming sites must be in the caller, outgoing in the selected item."""
    items, omitted = _bounded(value, max_results)
    rows = {}
    for item in items:
        _require(isinstance(item, dict) and set(item) == {"name", "kind", "span", "sites", "siteTotal"}, "call")
        source, start, end = _span(item["span"], snapshot)
        sites_raw, site_total = item["sites"], item["siteTotal"]
        _require(
            isinstance(sites_raw, list) and len(sites_raw) <= MAX_SITES_PER_CALL and _count(site_total)
            and site_total >= len(sites_raw), "call sites",
        )
        allowed = {source.path} if site_files is None else site_files
        sites = {}
        for site in sites_raw:
            site_source, site_start, site_end = _span(site, snapshot)
            _require(site_source.path in allowed, "callsite outside the calling file")
            sites.setdefault((site_source.index, site_start, site_end), _location(site_source, site_start, site_end))
        if site_total > len(sites_raw):
            notes.sites_omitted += site_total - len(sites_raw)
            notes.calls_capped += 1
        name, kind = notes.name(item["name"]), _kind(item["kind"])
        rows.setdefault((source.index, start, end, _units(name), _units(kind)), {
            "name": name,
            "kind": kind,
            "location": _location(source, start, end),
            "sites": [sites[key] for key in sorted(sites)],
        })
    return [rows[key] for key in sorted(rows)], omitted


def _inspection(result, snapshot, max_results, notes):
    _require(
        isinstance(result, dict) and set(result) == {"definitions", "references", "incoming", "outgoing", "prepared"},
        "inspect result shape",
    )
    prepared = result["prepared"]
    _require(isinstance(prepared, list) and len(prepared) <= MAX_PREPARED, "prepared call items")
    prepared_files = {_span(span, snapshot)[0].path for span in prepared}

    items, omitted_definitions = _bounded(result["definitions"], max_results)
    definitions = {}
    for item in items:
        _require(isinstance(item, dict) and set(item) == {"name", "kind", "span"}, "definition")
        source, start, end = _span(item["span"], snapshot)
        name, kind = notes.name(item["name"]), _kind(item["kind"])
        definitions.setdefault((source.index, start, end, _units(name), _units(kind)),
                               {"name": name, "kind": kind, "location": _location(source, start, end)})

    items, omitted_references = _bounded(result["references"], max_results)
    references = {}
    for item in items:
        _require(isinstance(item, dict) and set(item) == {"span", "isDefinition", "isWriteAccess"}, "reference")
        _require(type(item["isDefinition"]) is bool and type(item["isWriteAccess"]) is bool, "reference flags")
        source, start, end = _span(item["span"], snapshot)
        references.setdefault((source.index, start, end), {
            "location": _location(source, start, end),
            "isDefinition": item["isDefinition"],
            "isWriteAccess": item["isWriteAccess"],
        })

    incoming, omitted_incoming = _calls(result["incoming"], snapshot, max_results, notes, None)
    outgoing, omitted_outgoing = _calls(result["outgoing"], snapshot, max_results, notes, prepared_files)
    _require(not outgoing or prepared_files, "outgoing calls without a prepared call item")
    return {
        "definitions": [definitions[key] for key in sorted(definitions)],
        "references": [references[key] for key in sorted(references)],
        "incoming": incoming,
        "outgoing": outgoing,
        "omitted": {
            "definitions": omitted_definitions,
            "references": omitted_references,
            "incoming": omitted_incoming,
            "outgoing": omitted_outgoing,
        },
    }, bool(prepared)


def _diagnostics(snapshot, worker_rows, worker_total, notes):
    rows, total = [], 0

    def add(kind, message):
        nonlocal total
        total += 1
        if len(rows) < MAX_DIAGNOSTICS:
            rows.append({"kind": kind, "message": _clip(message)})

    if notes.sites_omitted:
        add("sites_capped", f"{notes.sites_omitted} callsite(s) omitted across {notes.calls_capped} call(s); "
                            f"at most {MAX_SITES_PER_CALL} are shown per call")
    if notes.clipped:
        add("name_clipped", f"{notes.clipped} name(s) shortened to {MAX_NAME_CHARS} characters")
    if snapshot.policy_excluded:
        add("policy_excluded", f"{snapshot.policy_excluded} tracked TS/JS path(s) excluded by symlink, secret, "
                               "vendor or generated-path policy")
    for path, _ in snapshot.invalid:
        add("invalid_source", f"{path}: not UTF-8 text or contains NUL; excluded")
    for row in worker_rows:
        add(row["kind"], row["message"])
    total += worker_total - len(worker_rows)
    if total > len(rows):
        rows.append({"kind": "diagnostics_omitted", "message": f"{total - len(rows)} further diagnostic(s) omitted"})
    return rows


def _common(snapshot, engine, version, max_results, diagnostics, qualifications):
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "engine": {"name": "typescript", "version": version, "sha256": engine.sha256},
        "snapshot": {
            "id": snapshot.id,
            "head": snapshot.head,
            "dirty": snapshot.dirty,
            "files": [{"path": source.path, "sha256": source.sha256} for source in snapshot.sources.values()],
        },
        "limits": {
            "max_results": max_results,
            "max_excerpt_utf16_units": MAX_EXCERPT_UNITS,
            "max_sites_per_call": MAX_SITES_PER_CALL,
            "max_tracked_files": MAX_TRACKED_FILES,
            "max_file_bytes": repo_map.MAX_FILE_BYTES,
            "max_total_bytes": MAX_TOTAL_BYTES,
            "max_diagnostics": MAX_DIAGNOSTICS,
            "timeout_seconds": WORKER_TIMEOUT_SECONDS,
        },
        "diagnostics": diagnostics,
        "qualifications": list(qualifications),
    }


@_boundary
def search_symbols(project, query, *, node_executable, typescript_path, max_results=DEFAULT_SEARCH_RESULTS):
    """Search TS/JS declarations by name with the installed TypeScript LanguageService.

    Returns schema ``context-ai/code-navigation/v1`` with ``query``, ``symbols``
    (``name``, ``kind``, ``container``, ``location``) and ``omitted.symbols``.
    Pass a symbol's ``location`` and the result's ``snapshot.id`` to
    :func:`inspect_symbol`. Raises :class:`NavigationError`.
    """
    _check_max_results(max_results)
    query = _check_query(query)
    root, engine, snapshot = _prepare(project, node_executable, typescript_path)
    reply = _run_worker(engine, _payload(snapshot, "search", max_results, query=query))
    version, worker_rows, worker_total, result = _envelope(reply)
    notes = _Notes()
    symbols, omitted = _symbols(result, snapshot, max_results, notes)
    _confirm(root, engine, snapshot)
    output = _common(snapshot, engine, version, max_results,
                     _diagnostics(snapshot, worker_rows, worker_total, notes),
                     (*QUALIFICATIONS, SEARCH_QUALIFICATION))
    output.update({"query": query, "symbols": symbols, "omitted": {"symbols": omitted}})
    return output


@_boundary
def inspect_symbol(project, selector, *, expected_snapshot, node_executable, typescript_path,
                   max_results=DEFAULT_INSPECT_RESULTS):
    """Return definitions, references and one-hop incoming/outgoing calls at a selector.

    ``selector`` is ``{file, line, column, sha256}`` or a complete search
    ``location``; positions are 1-based and columns count UTF-16 units.
    ``expected_snapshot`` must equal the current snapshot id, so any source,
    Git or engine change since search is refused. Raises :class:`NavigationError`.
    """
    _check_max_results(max_results)
    _check_selector(selector)
    if not isinstance(expected_snapshot, str) or not SNAPSHOT_ID.fullmatch(expected_snapshot):
        raise NavigationError("expected_snapshot must be the snapshot.id returned by search")
    root, engine, snapshot = _prepare(project, node_executable, typescript_path)
    if expected_snapshot != snapshot.id:
        raise NavigationError("snapshot changed since search; search again before inspecting", "stale_snapshot")
    source = snapshot.sources.get(selector["file"])
    if source is None:
        raise NavigationError("selector file is not an admitted tracked TS/JS source in this snapshot")
    if selector["sha256"] != source.sha256:
        raise NavigationError("selector sha256 does not match the captured file; search again", "stale_snapshot")
    positions = source.positions()
    start = positions.offset(selector["line"], selector["column"])
    end = start
    if "endLine" in selector:
        end = positions.offset(selector["endLine"], selector["endColumn"])
    if start is None or end is None or end < start:
        raise NavigationError("selector position is outside the captured file text")

    reply = _run_worker(engine, _payload(snapshot, "inspect", max_results,
                                         position={"file": source.path, "offset": start}))
    version, worker_rows, worker_total, result = _envelope(reply)
    notes = _Notes()
    detail, has_calls = _inspection(result, snapshot, max_results, notes)
    _confirm(root, engine, snapshot)
    qualifications = [*QUALIFICATIONS, INSPECT_QUALIFICATION]
    if not has_calls:
        qualifications.append(NO_CALL_QUALIFICATION)
    output = _common(snapshot, engine, version, max_results,
                     _diagnostics(snapshot, worker_rows, worker_total, notes), qualifications)
    output["selected"] = _location(source, start, end)
    output["excerpt"] = _excerpt(source, start)
    output.update(detail)
    return output


def _emit(value):
    json.dump(value, sys.stdout, ensure_ascii=True, sort_keys=True, indent=2)
    sys.stdout.write("\n")


def _selector_argument(raw):
    if len(raw) > MAX_SELECTOR_JSON:
        raise NavigationError("selector JSON is too large")
    try:
        return json.loads(raw, parse_constant=_reject_constant)
    except ValueError as exc:
        raise NavigationError("selector JSON is malformed") from exc


def main(argv=None):
    parser = _Parser(prog="python -m scripts.code_navigation",
                     description="Resolved TS/JS definitions, references and one-hop calls. Writes JSON to stdout.")
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="search declarations by name")
    search.add_argument("project", help="explicit Git repository root")
    search.add_argument("query")
    inspect = commands.add_parser("inspect", help="inspect a search location")
    inspect.add_argument("project", help="explicit Git repository root")
    inspect.add_argument("--selector-json", required=True, help="a search location or {file,line,column,sha256}")
    inspect.add_argument("--expected-snapshot", required=True, help="snapshot.id returned by search")
    for command in (search, inspect):
        command.add_argument("--node", required=True, help="host-configured absolute Node executable")
        command.add_argument("--typescript", required=True, help="absolute installed typescript/lib/typescript.js")
        command.add_argument("--max-results", type=int)
    try:
        args = parser.parse_args(argv)
        engine = {"node_executable": args.node, "typescript_path": args.typescript}
        if args.max_results is not None:
            engine["max_results"] = args.max_results
        if args.command == "search":
            result = search_symbols(args.project, args.query, **engine)
        else:
            selector = _selector_argument(args.selector_json)
            result = inspect_symbol(args.project, selector, expected_snapshot=args.expected_snapshot, **engine)
    except NavigationError as exc:
        _emit({"schema": SCHEMA, "schema_version": SCHEMA_VERSION,
               "error": {"kind": exc.kind, "message": str(exc)}})
        return 2
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
