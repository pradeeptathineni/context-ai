#!/usr/bin/env python3
"""Assemble caller-validated Research and Planning packets into a frozen Context export.

This additive API preserves the packet owners' claims as metadata. It does not
verify owner state or imply that the content is authoritative instructions.
"""

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path

import context_pack

SCHEMA_VERSION = 1
RESULT_SCHEMA_VERSION = 2
KINDS = ("research_answer", "planning_intent")
RESULT_KIND = "maestro_result"
MAX_RESULTS = 8
MAX_PACKET_BYTES = 512 * 1024
MAX_MISSION_TEXT_BYTES = 128_000
MAX_MISSION_TEXT_UTF16 = 32_000
RECORD_FIELDS = {"kind", "owner", "record_id", "revision", "digest", "title", "text", "qualification"}


def _error(code, message):
    raise context_pack.ContextPackError(code, message)


def _identity(value, label, limit=200):
    if (not isinstance(value, str) or not value or len(value) > limit
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        _error("invalid_request", f"{label} must be non-empty text without control characters")
    return value


def _validate(packet):
    if not isinstance(packet, dict) or set(packet) not in ({"task", "records"}, {"task", "records", "maestro_results"}):
        _error("invalid_request", "packet must contain task and records, with optional maestro_results")
    if len(context_pack._json(packet).encode("utf-8")) > MAX_PACKET_BYTES:
        _error("invalid_request", "input packet exceeds the size limit")
    task = packet["task"]
    if not isinstance(task, str) or not task.strip() or len(task) > context_pack.MAX_TASK_CHARS:
        _error("invalid_request", "task must contain 1 to 2048 characters")
    records = packet["records"]
    if not isinstance(records, list) or len(records) != 2:
        _error("invalid_request", "exactly Research answer and Planning intent records are required")
    normalized, identifiers = [], set()
    for record, expected_kind, expected_owner in zip(records, KINDS, ("research", "planning")):
        if not isinstance(record, dict) or set(record) != RECORD_FIELDS:
            _error("invalid_request", "record shape is invalid")
        if record["kind"] != expected_kind or record["owner"] != expected_owner:
            _error("invalid_request", "records must be Research answer then Planning intent")
        record_id = _identity(record["record_id"], "record ID")
        if record_id in identifiers:
            _error("invalid_request", "record IDs must be unique")
        identifiers.add(record_id)
        revision = _identity(record["revision"], "revision")
        title = _identity(record["title"], "title", 500)
        digest = record["digest"]
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            _error("invalid_request", "record digest must use sha256:<64 lowercase hex>")
        text = record["text"]
        qualification = record["qualification"]
        if not isinstance(text, str) or not isinstance(qualification, str):
            _error("invalid_request", "record text and qualification must be strings")
        if len(text.encode("utf-8")) > MAX_PACKET_BYTES or len(qualification.encode("utf-8")) > 4096:
            _error("invalid_request", "record text or qualification exceeds its size limit")
        normalized.append({"kind": expected_kind, "owner": expected_owner,
                           "record_id": record_id, "revision": revision,
                           "digest": digest, "title": title, "text": text,
                           "qualification": qualification})
    results = packet.get("maestro_results", [])
    if not isinstance(results, list) or len(results) > MAX_RESULTS:
        _error("invalid_request", "maestro_results must contain at most eight records")
    normalized_results = []
    for record in results:
        if not isinstance(record, dict) or set(record) != RECORD_FIELDS:
            _error("invalid_request", "Maestro result record shape is invalid")
        if record["kind"] != RESULT_KIND or record["owner"] != "maestro":
            _error("invalid_request", "Maestro results must use kind maestro_result and owner maestro")
        record_id = _identity(record["record_id"], "Maestro source ID")
        if record_id in identifiers:
            _error("invalid_request", "record IDs must be unique")
        identifiers.add(record_id)
        revision = _identity(record["revision"], "Maestro source revision")
        title = _identity(record["title"], "title", 500)
        digest = record["digest"]
        text = record["text"]
        qualification = record["qualification"]
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            _error("invalid_request", "Maestro result digest must use sha256:<64 lowercase hex>")
        if not isinstance(text, str) or not isinstance(qualification, str):
            _error("invalid_request", "Maestro result text and qualification must be strings")
        text_bytes = text.encode("utf-8")
        if len(text_bytes) > MAX_PACKET_BYTES or len(qualification.encode("utf-8")) > 4096:
            _error("invalid_request", "Maestro result text or qualification exceeds its size limit")
        if digest != "sha256:" + context_pack._sha(text_bytes):
            _error("invalid_request", "Maestro result digest does not match its exact UTF-8 text")
        normalized_results.append({"kind": RESULT_KIND, "owner": "maestro",
                                   "record_id": record_id, "revision": revision,
                                   "digest": digest, "title": title, "text": text,
                                   "qualification": qualification})
    return task, normalized, normalized_results


def _render(task, records, results, max_tokens):
    limits = {"max_tokens": max_tokens, "max_bytes_per_format": 4 * max_tokens,
              "token_estimate": "ceil(UTF-8 bytes / 4)"}
    all_records = records + results
    refs = [{key: row[key] for key in ("kind", "owner", "record_id", "revision", "digest", "qualification")}
            for row in all_records]

    def make(rows, omitted):
        items = [{"kind": row["kind"], "item_id": row["record_id"], "title": row["title"],
                  "content": row["text"], "authority": "caller_validated_data",
                  "source_ref": {key: row[key] for key in
                                 ("owner", "record_id", "revision", "digest", "qualification")}}
                 for row in rows]
        omissions = ([{"item_id": row["record_id"], "reason": "budget"} for row in omitted])
        base = {"schema_version": context_pack.SCHEMA_VERSION,
                "preview_id": "linked-owner-packets", "task": task,
                "project": {"authority": "caller_validated_data"},
                "context": {"authority": "caller_validated_data"},
                "included_ids": [row["record_id"] for row in rows], "items": items,
                "omissions": omissions, "limits": limits}
        return context_pack._render_pack(base)

    if not results:
        # Preserve the published v1 two-record artifact and rendering exactly.
        pack_id, wire, renders = make(records, [])
        if max(render["bytes"] for render in renders.values()) <= limits["max_bytes_per_format"]:
            included, omissions = records, []
        else:
            pack_id, wire, renders = make(records[1:], [records[0]])
            if max(render["bytes"] for render in renders.values()) > limits["max_bytes_per_format"]:
                _error("budget_too_small", "Planning intent does not fit the requested Context budget")
            included = records[1:]
            omissions = [{"record_id": records[0]["record_id"], "reason": "budget"}]
        version = SCHEMA_VERSION
    else:
        version = RESULT_SCHEMA_VERSION
        required = [records[1]]
        optional = [records[0], *results]
        included = list(required)
        # Research and selected results are considered in caller order. A result
        # that does not fit is recorded as omitted rather than silently clipped.
        omissions = []
        for row in optional:
            tentative = included + [row]
            tentative = [candidate for candidate in all_records if candidate in tentative]
            omitted_rows = [candidate for candidate in optional if candidate not in tentative]
            pack_id, wire, renders = make(tentative, omitted_rows)
            if max(render["bytes"] for render in renders.values()) <= limits["max_bytes_per_format"]:
                included = tentative
            else:
                omissions.append({"kind": row["kind"], "owner": row["owner"],
                                  "record_id": row["record_id"], "reason": "budget"})
        omitted_rows = [row for row in optional if row["record_id"] not in
                        {item["record_id"] for item in included}]
        included = [row for row in all_records if row in included]
        pack_id, wire, renders = make(included, omitted_rows)
        if max(render["bytes"] for render in renders.values()) > limits["max_bytes_per_format"]:
            _error("budget_too_small", "Planning intent does not fit the requested Context budget")
        # Keep only the v2 omission contract, including Research if budget-bound.
    text_render = renders["text"]
    return {"schema_version": version, "pack_id": pack_id,
            "included": [{key: row[key] for key in
                          ("kind", "owner", "record_id", "revision", "digest", "qualification")}
                         for row in included],
            "omissions": omissions, "source_refs": refs,
            "render_sha256": text_render["sha256"],
            "estimated_tokens": text_render["estimated_tokens"],
            "text": text_render["content"], "manifest": wire}


def _artifact_id(body):
    unsigned = {key: value for key, value in body.items() if key != "artifact_id"}
    return context_pack._sha(context_pack._json(unsigned).encode("utf-8"))


def _load_artifact(store, name):
    """Load a linked artifact using Context's private-store file protections."""
    path = store / name
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_size > context_pack.MAX_STORE_OBJECT):
                _error("store_invalid", "stored linked artifact is missing, unsafe or oversized")
            chunks, left = [], info.st_size
            while left:
                block = os.read(fd, min(left, 64 * 1024))
                if not block:
                    _error("store_invalid", "stored linked artifact ended during read")
                chunks.append(block)
                left -= len(block)
            value = json.loads(b"".join(chunks).decode("utf-8"))
        finally:
            os.close(fd)
    except (OSError, ValueError, UnicodeError) as exc:
        raise context_pack.ContextPackError("store_invalid", "stored linked artifact is invalid") from exc
    if not isinstance(value, dict):
        _error("store_invalid", "stored linked artifact is invalid")
    return value


def assemble(store, packet, *, max_tokens=8192):
    """Freeze caller-validated Research, Planning, and optional Maestro packets."""
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 100 <= max_tokens <= 8192:
        _error("invalid_request", "max_tokens must be an integer from 100 to 8192")
    task, records, results = _validate(packet)
    store = Path(store).expanduser()
    if store.exists() and (store.is_symlink() or not store.is_dir()):
        _error("store_invalid", "store must be a directory")
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    store = store.resolve()
    generated = _render(task, records, results, max_tokens)
    body = {"schema_version": generated["schema_version"], "render_sha256": generated["render_sha256"],
            "artifact": generated}
    artifact_id = _artifact_id(body)
    body["artifact_id"] = artifact_id
    with context_pack._locked(store):
        name = f"linked-{artifact_id}.json"
        if (store / name).exists():
            saved = _load_artifact(store, name)
            if saved != body:
                _error("store_invalid", "existing linked artifact differs from its identity")
        else:
            context_pack._write(store, name, body)
    return _public(artifact_id, generated)


def _public(artifact_id, artifact):
    return {"schemaVersion": artifact["schema_version"], "artifactId": artifact_id,
            "packId": artifact["pack_id"], "included": artifact["included"],
            "omissions": artifact["omissions"], "renderSha256": artifact["render_sha256"],
            "estimatedTokens": artifact["estimated_tokens"],
            "sourceRefs": artifact["source_refs"], "text": artifact["text"]}


def read(store, artifact_id):
    """Read and validate immutable v1 or v2 artifacts without consulting owners."""
    if not isinstance(artifact_id, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_id):
        _error("unknown_selection", "artifact ID is invalid")
    store = Path(store).expanduser()
    if store.is_symlink() or not store.is_dir():
        _error("unknown_selection", "artifact store is unavailable")
    with context_pack._locked(store):
        body = _load_artifact(store, f"linked-{artifact_id}.json")
    if (set(body) != {"schema_version", "render_sha256", "artifact", "artifact_id"}
            or body.get("schema_version") not in (SCHEMA_VERSION, RESULT_SCHEMA_VERSION)
            or body.get("artifact_id") != artifact_id
            or _artifact_id(body) != artifact_id):
        _error("store_invalid", "linked artifact manifest integrity check failed")
    artifact = body.get("artifact")
    if not isinstance(artifact, dict) or set(artifact) != {
            "schema_version", "pack_id", "included", "omissions", "source_refs",
            "render_sha256", "estimated_tokens", "text", "manifest"}:
        _error("store_invalid", "linked artifact shape is invalid")
    if artifact.get("schema_version") != body["schema_version"]:
        _error("store_invalid", "linked artifact schema version differs from its envelope")
    text = artifact.get("text")
    if (not isinstance(text, str) or context_pack._sha(text.encode("utf-8")) != artifact.get("render_sha256")
            or artifact.get("render_sha256") != body["render_sha256"]):
        _error("store_invalid", "linked artifact render integrity check failed")
    manifest = artifact.get("manifest")
    if not isinstance(manifest, dict) or context_pack._sha(
            context_pack._json({key: value for key, value in manifest.items() if key != "pack_id"}).encode("utf-8")) != artifact.get("pack_id"):
        _error("store_invalid", "linked artifact pack integrity check failed")
    try:
        expected_id, expected_wire, renders = context_pack._render_pack(
            {key: value for key, value in manifest.items() if key != "pack_id"})
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise context_pack.ContextPackError("store_invalid", "linked artifact render is invalid") from exc
    if (expected_id != artifact.get("pack_id") or expected_wire != manifest
            or renders["text"]["content"] != text
            or renders["text"]["sha256"] != artifact.get("render_sha256")
            or renders["text"]["estimated_tokens"] != artifact.get("estimated_tokens")):
        _error("store_invalid", "linked artifact render differs from its frozen manifest")
    return _public(artifact_id, artifact)


def _owner_qualification(artifact):
    """Describe only properties retained in the immutable Context artifact."""
    kinds = ",".join(row["kind"] for row in artifact["included"])
    reasons = ",".join(row["reason"] for row in artifact["omissions"]) or "none"
    source_count = len(artifact["sourceRefs"])
    return (f"Context immutable artifact; included={kinds}; omitted={reasons}; "
            f"source_refs={source_count}")


def resolve_for_mission(store, context_ref):
    """Resolve exact Context text and identity; does not revalidate source owners."""
    if not isinstance(context_ref, dict) or set(context_ref) != {
            "owner", "id", "artifactSha256", "qualification"}:
        _error("invalid_request", "context_ref must contain owner, id, artifactSha256 and qualification")
    if context_ref["owner"] != "context-ai":
        _error("unknown_selection", "Context owner does not match")
    artifact_id = context_ref["id"]
    render_sha = context_ref["artifactSha256"]
    qualification = context_ref["qualification"]
    if not isinstance(artifact_id, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_id):
        _error("unknown_selection", "Context artifact ID is invalid")
    if not isinstance(render_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", render_sha):
        _error("unknown_selection", "Context artifact digest is invalid")
    try:
        qualification_bytes = qualification.encode("utf-8") if isinstance(qualification, str) else b""
    except UnicodeEncodeError as exc:
        raise context_pack.ContextPackError("invalid_request", "Context qualification must be valid UTF-8") from exc
    if (not isinstance(qualification, str) or not qualification.strip()
            or len(qualification_bytes) > 512
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in qualification)):
        _error("invalid_request", "Context qualification must be bounded printable text")

    artifact = read(store, artifact_id)
    if artifact["renderSha256"] != render_sha:
        _error("unknown_selection", "Context artifact digest does not match its exact render")
    text = artifact["text"]
    encoded = text.encode("utf-8")
    if (len(encoded) > MAX_MISSION_TEXT_BYTES
            or len(text.encode("utf-16-le")) // 2 > MAX_MISSION_TEXT_UTF16):
        _error("store_invalid", "Context artifact text exceeds the Mission input limit")

    identity = {"owner": "context-ai", "id": artifact_id,
                "artifactSha256": render_sha, "qualification": qualification}
    return {
        "preparedInput": {
            "text": text,
            "context": {"artifactId": artifact_id, "renderDigest": render_sha,
                        "qualification": qualification},
        },
        "contextRef": identity,
        "publicReceipt": {
            "schemaVersion": 1,
            "owner": "context-ai",
            "artifactId": artifact_id,
            "artifactSha256": render_sha,
            "textSha256": context_pack._sha(encoded),
            "callerQualificationUnverified": qualification,
            "ownerQualification": _owner_qualification(artifact),
            "sourceFreshness": "not_verified_by_context_owner_api",
            "missionTaskBinding": None,
        },
    }


def _cli():
    parser = argparse.ArgumentParser(description="Freeze caller-validated owner packets as Context artifacts.")
    subs = parser.add_subparsers(dest="command", required=True)
    create = subs.add_parser("assemble")
    create.add_argument("--store", required=True, type=Path)
    create.add_argument("--max-tokens", type=int, default=8192)
    load = subs.add_parser("read")
    load.add_argument("--store", required=True, type=Path)
    load.add_argument("--artifact-id", required=True)
    resolve = subs.add_parser("resolve-for-mission")
    resolve.add_argument("--store", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "assemble":
            raw = sys.stdin.buffer.read(MAX_PACKET_BYTES + 1)
            if len(raw) > MAX_PACKET_BYTES:
                _error("invalid_request", "input packet exceeds the size limit")
            packet = json.loads(raw.decode("utf-8"))
            result = assemble(args.store, packet, max_tokens=args.max_tokens)
        elif args.command == "read":
            result = read(args.store, args.artifact_id)
        else:
            raw = sys.stdin.buffer.read(2049)
            if len(raw) > 2048:
                _error("invalid_request", "Context reference exceeds the size limit")
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict) or set(request) != {"contextRef"}:
                _error("invalid_request", "request must contain contextRef")
            result = resolve_for_mission(args.store, request["contextRef"])
        sys.stdout.write(context_pack._json(result) + "\n")
    except (context_pack.ContextPackError, json.JSONDecodeError, UnicodeError) as exc:
        code = getattr(exc, "code", "invalid_request")
        message = getattr(exc, "message", "input JSON is invalid")
        sys.stderr.write(context_pack._json({"error": code, "message": message}) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
