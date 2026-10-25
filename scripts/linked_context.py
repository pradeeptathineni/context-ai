#!/usr/bin/env python3
"""Assemble caller-validated Research and Planning packets into a frozen Context export.

This additive API preserves the packet owners' claims as metadata. It does not
verify owner state or imply that the content is authoritative instructions.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import context_pack

SCHEMA_VERSION = 1
KINDS = ("research_answer", "planning_intent")
MAX_PACKET_BYTES = 512 * 1024
RECORD_FIELDS = {"kind", "owner", "record_id", "revision", "digest", "title", "text", "qualification"}


def _error(code, message):
    raise context_pack.ContextPackError(code, message)


def _identity(value, label, limit=200):
    if (not isinstance(value, str) or not value or len(value) > limit
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        _error("invalid_request", f"{label} must be non-empty text without control characters")
    return value


def _validate(packet):
    if not isinstance(packet, dict) or set(packet) != {"task", "records"}:
        _error("invalid_request", "packet must contain exactly task and records")
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
    return task, normalized


def _render(task, records, max_tokens):
    limits = {"max_tokens": max_tokens, "max_bytes_per_format": 4 * max_tokens,
              "token_estimate": "ceil(UTF-8 bytes / 4)"}
    refs = [{key: row[key] for key in ("kind", "owner", "record_id", "revision", "digest", "qualification")}
            for row in records]

    def make(rows, omitted):
        items = [{"kind": row["kind"], "item_id": row["record_id"], "title": row["title"],
                  "content": row["text"], "authority": "caller_validated_data",
                  "source_ref": {key: row[key] for key in
                                 ("owner", "record_id", "revision", "digest", "qualification")}}
                 for row in rows]
        omissions = ([{"item_id": records[0]["record_id"], "reason": "budget"}] if omitted else [])
        base = {"schema_version": context_pack.SCHEMA_VERSION,
                "preview_id": "linked-owner-packets", "task": task,
                "project": {"authority": "caller_validated_data"},
                "context": {"authority": "caller_validated_data"},
                "included_ids": [row["record_id"] for row in rows], "items": items,
                "omissions": omissions, "limits": limits}
        return context_pack._render_pack(base)

    pack_id, wire, renders = make(records, False)
    if max(render["bytes"] for render in renders.values()) <= limits["max_bytes_per_format"]:
        included, omissions = records, []
    else:
        # Planning is the required intent for this handoff; only Research may be omitted.
        pack_id, wire, renders = make(records[1:], True)
        if max(render["bytes"] for render in renders.values()) > limits["max_bytes_per_format"]:
            _error("budget_too_small", "Planning intent does not fit the requested Context budget")
        included = records[1:]
        omissions = [{"record_id": records[0]["record_id"], "reason": "budget"}]
    text_render = renders["text"]
    return {"schema_version": SCHEMA_VERSION, "pack_id": pack_id,
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


def assemble(store, packet, *, max_tokens=8192):
    """Freeze two owner packets. `packet` is data supplied by the caller."""
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 100 <= max_tokens <= 8192:
        _error("invalid_request", "max_tokens must be an integer from 100 to 8192")
    task, records = _validate(packet)
    store = Path(store).expanduser()
    if store.exists() and (store.is_symlink() or not store.is_dir()):
        _error("store_invalid", "store must be a directory")
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    store = store.resolve()
    generated = _render(task, records, max_tokens)
    body = {"schema_version": SCHEMA_VERSION, "render_sha256": generated["render_sha256"],
            "artifact": generated}
    artifact_id = _artifact_id(body)
    body["artifact_id"] = artifact_id
    with context_pack._locked(store):
        name = f"linked-{artifact_id}.json"
        if (store / name).exists():
            saved = context_pack._load(store, name)
            if saved != body:
                _error("store_invalid", "existing linked artifact differs from its identity")
        else:
            context_pack._write(store, name, body)
    return _public(artifact_id, generated)


def _public(artifact_id, artifact):
    return {"schemaVersion": SCHEMA_VERSION, "artifactId": artifact_id,
            "packId": artifact["pack_id"], "included": artifact["included"],
            "omissions": artifact["omissions"], "renderSha256": artifact["render_sha256"],
            "estimatedTokens": artifact["estimated_tokens"],
            "sourceRefs": artifact["source_refs"], "text": artifact["text"]}


def read(store, artifact_id):
    """Read and validate an immutable artifact without consulting packet owners."""
    if not isinstance(artifact_id, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_id):
        _error("unknown_selection", "artifact ID is invalid")
    store = Path(store).expanduser()
    if store.is_symlink() or not store.is_dir():
        _error("unknown_selection", "artifact store is unavailable")
    with context_pack._locked(store):
        body = context_pack._load(store, f"linked-{artifact_id}.json")
    if (set(body) != {"schema_version", "render_sha256", "artifact", "artifact_id"}
            or body.get("schema_version") != SCHEMA_VERSION
            or body.get("artifact_id") != artifact_id
            or _artifact_id(body) != artifact_id):
        _error("store_invalid", "linked artifact manifest integrity check failed")
    artifact = body.get("artifact")
    if not isinstance(artifact, dict) or set(artifact) != {
            "schema_version", "pack_id", "included", "omissions", "source_refs",
            "render_sha256", "estimated_tokens", "text", "manifest"}:
        _error("store_invalid", "linked artifact shape is invalid")
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


def _cli():
    parser = argparse.ArgumentParser(description="Freeze caller-validated Research and Planning Context packets.")
    subs = parser.add_subparsers(dest="command", required=True)
    create = subs.add_parser("assemble")
    create.add_argument("--store", required=True, type=Path)
    create.add_argument("--max-tokens", type=int, default=8192)
    load = subs.add_parser("read")
    load.add_argument("--store", required=True, type=Path)
    load.add_argument("--artifact-id", required=True)
    args = parser.parse_args()
    try:
        if args.command == "assemble":
            raw = sys.stdin.buffer.read(MAX_PACKET_BYTES + 1)
            if len(raw) > MAX_PACKET_BYTES:
                _error("invalid_request", "input packet exceeds the size limit")
            packet = json.loads(raw.decode("utf-8"))
            result = assemble(args.store, packet, max_tokens=args.max_tokens)
        else:
            result = read(args.store, args.artifact_id)
        sys.stdout.write(context_pack._json(result) + "\n")
    except (context_pack.ContextPackError, json.JSONDecodeError, UnicodeError) as exc:
        code = getattr(exc, "code", "invalid_request")
        message = getattr(exc, "message", "input JSON is invalid")
        sys.stderr.write(context_pack._json({"error": code, "message": message}) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
