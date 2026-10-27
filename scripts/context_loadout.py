#!/usr/bin/env python3
"""Versioned, source-bound task loadouts built from frozen Context and owner inputs."""

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

import context_pack
import linked_context

SCHEMA_VERSION = 1
MAX_SPEC_BYTES = 512 * 1024
MAX_REDUCTION_PREVIEWS = 8
MAX_REDUCTION_BYTES = 512 * 1024
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _fail(code, message):
    raise context_pack.ContextPackError(code, message)


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _store(path):
    path = Path(path).expanduser()
    if path.exists() and (path.is_symlink() or not path.is_dir()):
        _fail("store_invalid", "loadout store must be a directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = path.resolve()
    path.chmod(0o700)
    return path


def _read_json_file(path, limit):
    path = Path(path)
    if path.is_symlink():
        _fail("invalid_request", "JSON input must be a regular non-symlink file")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                _fail("invalid_request", "JSON input must be a regular file")
            raw = os.read(fd, limit + 1)
        finally:
            os.close(fd)
    except OSError as exc:
        raise context_pack.ContextPackError("invalid_request", "JSON input could not be read") from exc
    if len(raw) > limit:
        _fail("invalid_request", "JSON input exceeds its size limit")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _fail("invalid_request", "duplicate JSON field")
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise context_pack.ContextPackError("invalid_request", "JSON input is invalid") from exc


def _identity(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        _fail("invalid_request", "loadout ID is invalid")
    return value


def _spec(value):
    if (not isinstance(value, dict) or set(value) not in ({
            "schemaVersion", "task", "contextPreviewId", "maxTokens", "ownerPacket"}, {
            "schemaVersion", "task", "contextPreviewId", "maxTokens", "ownerPacket", "reductionRequests"})
            or type(value.get("schemaVersion")) is not int or value["schemaVersion"] != SCHEMA_VERSION):
        _fail("invalid_request", "loadout spec must match context-loadout/v1")
    task = value["task"]
    if not isinstance(task, str) or not task.strip() or len(task) > context_pack.MAX_TASK_CHARS:
        _fail("invalid_request", "task must contain 1 to 2048 characters")
    if not isinstance(value["contextPreviewId"], str) or not re.fullmatch(r"[0-9a-f]{32}", value["contextPreviewId"]):
        _fail("invalid_request", "context preview ID is invalid")
    budget = value["maxTokens"]
    if type(budget) is not int or not 100 <= budget <= 8192:
        _fail("invalid_request", "maxTokens must be an integer from 100 to 8192")
    packet = value["ownerPacket"]
    owner_task, records, maestro_results = linked_context._validate(packet)
    if maestro_results:
        _fail("invalid_request", "Context loadouts accept only Research and Planning owner records")
    if owner_task != task:
        _fail("invalid_request", "owner packet task must match the loadout task")
    requests = value.get("reductionRequests", [])
    if not isinstance(requests, list) or len(requests) > MAX_REDUCTION_PREVIEWS:
        _fail("invalid_request", "reductionRequests must contain at most eight entries")
    reductions, seen = [], set()
    for request in requests:
        if (not isinstance(request, dict) or set(request) != {"itemId", "maxLines"}
                or not isinstance(request.get("itemId"), str) or not request["itemId"]
                or len(request["itemId"]) > 160 or request["itemId"] in seen
                or type(request.get("maxLines")) is not int
                or not context_pack.REDUCTION_MIN_MAX_LINES <= request["maxLines"]
                <= context_pack.REDUCTION_MAX_LINES):
            _fail("invalid_request", "reduction request identity or line cap is invalid")
        seen.add(request["itemId"])
        reductions.append({"itemId": request["itemId"], "maxLines": request["maxLines"]})
    normalized = {"schemaVersion": SCHEMA_VERSION, "task": task,
                  "contextPreviewId": value["contextPreviewId"], "maxTokens": budget,
                  "ownerPacket": {"task": owner_task, "records": records},
                  "reductionRequests": reductions}
    if len(context_pack._json(normalized).encode("utf-8")) > MAX_SPEC_BYTES:
        _fail("invalid_request", "loadout spec exceeds its size limit")
    return normalized


def _revision_digest(loadout_id, version, spec):
    body = {"schemaVersion": SCHEMA_VERSION, "loadoutId": loadout_id,
            "version": version, "spec": spec}
    return _sha(context_pack._json(body).encode("utf-8"))


def _revision_name(loadout_id, version):
    return f"loadout-{loadout_id}-v{version}.json"


def _read_revision(store, loadout_id, version):
    body = context_pack._load(store, _revision_name(loadout_id, version))
    if (not isinstance(body, dict) or set(body) != {
            "schema_version", "schemaVersion", "loadoutId", "version", "spec", "digest"}
            or body["schema_version"] != SCHEMA_VERSION
            or body["schemaVersion"] != SCHEMA_VERSION or body["loadoutId"] != loadout_id
            or body["version"] != version or body["spec"] != _spec(body["spec"])
            or body["digest"] != _revision_digest(loadout_id, version, body["spec"])):
        _fail("store_invalid", "loadout revision integrity check failed")
    return body


def _public_revision(body):
    return {"schemaVersion": body["schemaVersion"], "loadoutId": body["loadoutId"],
            "version": body["version"], "digest": body["digest"], "spec": body["spec"],
            "state": "referenced"}


def create(store, loadout_id, spec):
    """Create immutable revision 1 of a reusable task selection."""
    loadout_id, spec = _identity(loadout_id), _spec(spec)
    store = _store(store)
    body = {"schema_version": SCHEMA_VERSION, "schemaVersion": SCHEMA_VERSION, "loadoutId": loadout_id,
            "version": 1, "spec": spec,
            "digest": _revision_digest(loadout_id, 1, spec)}
    with context_pack._locked(store):
        if any(store.glob(f"loadout-{loadout_id}-v*.json")):
            _fail("loadout_exists", "loadout ID already exists")
        context_pack._write(store, _revision_name(loadout_id, 1), body)
    return _public_revision(body)


def revise(store, loadout_id, *, expected_version, expected_digest, spec):
    """Append a revision only when the caller names the current revision digest."""
    loadout_id, spec = _identity(loadout_id), _spec(spec)
    store = _store(store)
    with context_pack._locked(store):
        versions = []
        for path in store.glob(f"loadout-{loadout_id}-v*.json"):
            match = re.fullmatch(rf"loadout-{re.escape(loadout_id)}-v([1-9][0-9]*)\.json", path.name)
            if match:
                versions.append(int(match.group(1)))
        if not versions:
            _fail("unknown_selection", "loadout does not exist")
        current = _read_revision(store, loadout_id, max(versions))
        if (type(expected_version) is not int or expected_version != current["version"]
                or expected_digest != current["digest"]):
            _fail("revision_conflict", "loadout changed; inspect its current revision before revising")
        version = current["version"] + 1
        body = {"schema_version": SCHEMA_VERSION, "schemaVersion": SCHEMA_VERSION, "loadoutId": loadout_id,
                "version": version, "spec": spec,
                "digest": _revision_digest(loadout_id, version, spec)}
        context_pack._write(store, _revision_name(loadout_id, version), body)
    return _public_revision(body)


def _assert_disjoint(store, service):
    if store == service.project or store.is_relative_to(service.project) or service.project.is_relative_to(store):
        _fail("binding_mismatch", "loadout store and project source must be separate")
    if (store == service.context_root or store.is_relative_to(service.context_root)
            or service.context_root.is_relative_to(store)):
        _fail("binding_mismatch", "loadout store and Context source must be separate")
    if store == service.store or store.is_relative_to(service.store) or service.store.is_relative_to(store):
        _fail("binding_mismatch", "loadout store and Context pack store must be separate")


def _assemble(store, revision, service):
    _assert_disjoint(store, service)
    spec = revision["spec"]
    project_json = service.export(spec["contextPreviewId"], format="json")
    project_text = service.export(spec["contextPreviewId"], format="text")
    try:
        project_manifest = json.loads(project_json.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise context_pack.ContextPackError("store_invalid", "Context pack JSON is invalid") from exc
    linked_store = store / "owner-artifacts"
    linked = linked_context.assemble(linked_store, spec["ownerPacket"], max_tokens=spec["maxTokens"])
    linked_body = context_pack._load(linked_store, f"linked-{linked['artifactId']}.json")
    combined = (f"# Context loadout {revision['loadoutId']} v{revision['version']}\n\n"
                + project_text.decode("utf-8") + "\n\n" + linked["text"])
    raw = combined.encode("utf-8")
    if len(raw) > 4 * spec["maxTokens"]:
        _fail("budget_too_small", "combined Context and owner content exceeds the loadout budget")
    project_pack_id = project_manifest.get("pack_id")
    if not isinstance(project_pack_id, str) or not re.fullmatch(r"[0-9a-f]{64}", project_pack_id):
        _fail("store_invalid", "Context pack identity is invalid")
    manifest = project_manifest.get("items", [])
    omissions = project_manifest.get("omissions", [])
    reduction_previews = [context_pack.preview_pack_reduction(
        service, spec["contextPreviewId"], request["itemId"], max_lines=request["maxLines"])
        for request in spec["reductionRequests"]]
    if len(context_pack._json(reduction_previews).encode("utf-8")) > MAX_REDUCTION_BYTES:
        _fail("reduction_too_large", "combined reduction previews exceed their size limit")
    return {"schemaVersion": SCHEMA_VERSION, "loadout": _public_revision(revision),
            "assemblyState": "assembled", "deliveryState": "not_sent",
            "contextPack": {"previewId": spec["contextPreviewId"], "packId": project_pack_id,
                            "manifest": project_manifest, "text": project_text.decode("utf-8"),
                            "textSha256": _sha(project_text)},
            "ownerArtifact": linked_body,
            "reductionPreviews": reduction_previews,
            "inspection": {"includedContextItems": [x.get("item_id") for x in manifest if isinstance(x, dict)],
                           "omittedContextItems": omissions,
                           "includedOwnerRefs": linked["included"], "omittedOwnerRefs": linked["omissions"],
                           "combinedBytes": len(raw), "estimatedTokens": (len(raw) + 3) // 4,
                           "budgetTokens": spec["maxTokens"]},
            "text": combined, "textSha256": _sha(raw)}


def inspect(store, loadout_id, *, version, digest, service):
    """Inspect the exact source pack, owner refs, content, omissions and combined budget."""
    loadout_id = _identity(loadout_id)
    if (type(version) is not int or version < 1 or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        _fail("invalid_request", "loadout version or digest is invalid")
    store = _store(store)
    with context_pack._locked(store):
        revision = _read_revision(store, loadout_id, version)
        if revision["digest"] != digest:
            _fail("revision_conflict", "selected loadout digest does not match its version")
    return _assemble(store, revision, service)


def _snapshot_id(body):
    return _sha(context_pack._json({k: v for k, v in body.items() if k != "artifactId"}).encode("utf-8"))


def freeze(store, loadout_id, *, version, digest, service):
    """Freeze an exact inspected assembly as an immutable portable artifact."""
    assembled = inspect(store, loadout_id, version=version, digest=digest, service=service)
    store = _store(store)
    body = {"schema_version": SCHEMA_VERSION, **assembled, "artifactState": "frozen"}
    artifact_id = _snapshot_id(body)
    body["artifactId"] = artifact_id
    with context_pack._locked(store):
        name = f"snapshot-{artifact_id}.json"
        if (store / name).exists():
            existing = context_pack._load(store, name)
            if existing != body:
                _fail("store_invalid", "existing loadout artifact differs from its identity")
        else:
            context_pack._write(store, name, body)
    return read(store, artifact_id)


def read(store, artifact_id):
    """Cold-read a frozen artifact, validating both nested renders and the outer digest."""
    if not isinstance(artifact_id, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_id):
        _fail("unknown_selection", "artifact ID is invalid")
    store = _store(store)
    body = context_pack._load(store, f"snapshot-{artifact_id}.json")
    if (set(body) != {"schema_version", "schemaVersion", "loadout", "assemblyState", "deliveryState",
                      "contextPack", "ownerArtifact", "reductionPreviews", "inspection", "text", "textSha256",
                      "artifactState", "artifactId"}
            or body.get("artifactId") != artifact_id or body.get("schema_version") != SCHEMA_VERSION
            or body.get("schemaVersion") != SCHEMA_VERSION
            or body.get("assemblyState") != "assembled" or body.get("deliveryState") != "not_sent"
            or body.get("artifactState") != "frozen"
            or _snapshot_id(body) != artifact_id):
        _fail("store_invalid", "loadout artifact integrity check failed")
    project = body.get("contextPack", {})
    try:
        loadout = body["loadout"]
        if (not isinstance(loadout, dict) or loadout.get("state") != "referenced"
                or loadout.get("schemaVersion") != SCHEMA_VERSION
                or loadout.get("loadoutId") != _identity(loadout.get("loadoutId"))
                or type(loadout.get("version")) is not int or loadout["version"] < 1
                or loadout.get("spec") != _spec(loadout.get("spec"))
                or loadout.get("digest") != _revision_digest(
                    loadout.get("loadoutId"), loadout.get("version"), loadout["spec"])):
            _fail("store_invalid", "frozen loadout revision is invalid")
        manifest = project["manifest"]
        pack_id, wire, renders = context_pack._render_pack({k: v for k, v in manifest.items() if k != "pack_id"})
        project_text = project["text"].encode("utf-8")
        owner_body = body["ownerArtifact"]
        if (not isinstance(owner_body, dict) or set(owner_body) != {
                "schema_version", "render_sha256", "artifact", "artifact_id"}
                or owner_body["schema_version"] != SCHEMA_VERSION):
            _fail("store_invalid", "frozen owner artifact envelope is invalid")
        owner_artifact = owner_body["artifact"]
        owner_id = linked_context._artifact_id({k: v for k, v in owner_body.items() if k != "artifact_id"})
        owner_pack, owner_wire, owner_renders = context_pack._render_pack(
            {k: v for k, v in owner_artifact["manifest"].items() if k != "pack_id"})
        combined = body["text"].encode("utf-8")
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise context_pack.ContextPackError("store_invalid", "loadout artifact contents are invalid") from exc
    inspection = body["inspection"]
    expected_context_ids = [row.get("item_id") for row in manifest.get("items", []) if isinstance(row, dict)]
    if (pack_id != project.get("packId") or wire != manifest or renders["text"]["content"].encode() != project_text
            or _sha(project_text) != project.get("textSha256") or owner_id != owner_body.get("artifact_id")
            or owner_pack != owner_artifact.get("pack_id") or owner_wire != owner_artifact.get("manifest")
            or owner_renders["text"]["content"] != owner_artifact.get("text")
            or owner_body.get("render_sha256") != owner_artifact.get("render_sha256")
            or _sha(owner_artifact["text"].encode("utf-8")) != owner_body.get("render_sha256")
            or owner_renders["text"]["sha256"] != owner_artifact.get("render_sha256")
            or combined.decode("utf-8") != (
                f"# Context loadout {loadout['loadoutId']} v{loadout['version']}\n\n"
                + project_text.decode("utf-8") + "\n\n" + owner_artifact["text"])
            or _sha(combined) != body.get("textSha256")):
        _fail("store_invalid", "nested loadout content does not match its frozen identities")
    if (not isinstance(inspection, dict) or inspection.get("includedContextItems") != expected_context_ids
            or inspection.get("omittedContextItems") != manifest.get("omissions")
            or inspection.get("includedOwnerRefs") != owner_artifact["included"]
            or inspection.get("omittedOwnerRefs") != owner_artifact["omissions"]
            or inspection.get("budgetTokens") != loadout["spec"]["maxTokens"]
            or inspection.get("combinedBytes") != len(combined)
            or inspection.get("estimatedTokens") != (len(combined) + 3) // 4):
        _fail("store_invalid", "frozen loadout inspection does not match its content")
    if len(combined) > 4 * loadout["spec"]["maxTokens"]:
        _fail("store_invalid", "frozen loadout exceeds its declared budget")
    reductions = body["reductionPreviews"]
    if (not isinstance(reductions, list) or len(reductions) != len(loadout["spec"]["reductionRequests"])
            or len(context_pack._json(reductions).encode("utf-8")) > MAX_REDUCTION_BYTES):
        _fail("store_invalid", "frozen reduction previews are invalid or oversized")
    included_items = {item.get("item_id"): item for item in manifest.get("items", []) if isinstance(item, dict)}
    for reduction, request in zip(reductions, loadout["spec"]["reductionRequests"]):
        if not isinstance(reduction, dict):
            _fail("store_invalid", "frozen reduction preview is invalid")
        source_ref = reduction.get("source_ref")
        size = reduction.get("size")
        if not isinstance(source_ref, dict) or not isinstance(size, dict):
            _fail("store_invalid", "frozen reduction source binding is invalid")
        source = included_items.get(request["itemId"])
        segments = reduction.get("segments")
        rebuilt, projected, offset, valid_segments = [], [], 0, isinstance(segments, list)
        for row in segments if isinstance(segments, list) else []:
            text = row.get("text") if isinstance(row, dict) else None
            if (not isinstance(row, dict) or type(row.get("start")) is not int
                    or type(row.get("end")) is not int or row["start"] != offset
                    or not isinstance(text, str) or row["end"] != offset + len(text)
                    or row.get("disposition") not in {"kept", "omitted", "cap-dropped"}):
                valid_segments = False
                break
            rebuilt.append(text)
            if row["disposition"] == "kept":
                projected.append(text)
            offset = row["end"]
        if (not isinstance(reduction, dict) or reduction.get("schema") != context_pack.REDUCTION_SCHEMA
                or reduction.get("preview_id") != _sha(context_pack._json(
                    {k: v for k, v in reduction.items() if k != "preview_id"}).encode("utf-8"))
                or source_ref.get("preview_id") != project.get("previewId")
                or source_ref.get("pack_id") != project.get("packId")
                or source_ref.get("item_id") != request["itemId"]
                or request["maxLines"] != reduction.get("max_lines")
                or source is None or source.get("kind") != "source"
                or source_ref.get("source") != source.get("source") or not valid_segments
                or _sha("".join(rebuilt).encode("utf-8")) != source_ref.get("raw_sha256")
                or size.get("before_bytes") != len("".join(rebuilt).encode("utf-8"))
                or size.get("after_bytes") != len("".join(projected).encode("utf-8"))
                or "".join(projected) != reduction.get("projected_text")):
            _fail("store_invalid", "reduction preview is not bound to its frozen Context source")
    return body


def compare(store, loadout_id, artifact_id, *, version, digest, service):
    """Compare a frozen artifact with a named revision; never changes the loadout or artifact."""
    loadout_id = _identity(loadout_id)
    old = read(store, artifact_id)
    if old["loadout"]["loadoutId"] != loadout_id:
        _fail("binding_mismatch", "artifact belongs to another loadout")
    current = inspect(store, loadout_id, version=version, digest=digest, service=service)
    before = old["inspection"]
    after = current["inspection"]
    old_loadout = old["loadout"]
    same_spec = old_loadout["spec"] == current["loadout"]["spec"]
    project_changed = old["contextPack"]["packId"] != current["contextPack"]["packId"]
    owners_changed = old["ownerArtifact"]["artifact_id"] != current["ownerArtifact"]["artifact_id"]
    return {"schemaVersion": SCHEMA_VERSION, "artifactId": artifact_id,
            "comparedTo": {"loadoutId": current["loadout"]["loadoutId"],
                           "version": current["loadout"]["version"], "digest": current["loadout"]["digest"]},
            "changed": not same_spec or project_changed or owners_changed,
            "changes": {"spec": not same_spec, "projectPack": project_changed,
                        "ownerPacket": owners_changed,
                        "revision": old_loadout["version"] != current["loadout"]["version"]},
            "before": {"version": old_loadout["version"], "digest": old_loadout["digest"],
                       "packId": old["contextPack"]["packId"],
                       "textSha256": old["textSha256"], **before},
            "after": {"version": current["loadout"]["version"], "digest": current["loadout"]["digest"],
                      "packId": current["contextPack"]["packId"],
                      "textSha256": current["textSha256"], **after},
            "state": "comparison_only"}


def _cli():
    parser = argparse.ArgumentParser(description="Manage versioned, frozen Context task loadouts.")
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "revise"):
        item = subs.add_parser(command)
        item.add_argument("--store", required=True, type=Path)
        item.add_argument("--loadout-id", required=True)
        item.add_argument("--spec", required=True, type=Path)
        if command == "revise":
            item.add_argument("--expected-version", required=True, type=int)
            item.add_argument("--expected-digest", required=True)
    for command in ("inspect", "freeze", "compare"):
        item = subs.add_parser(command)
        item.add_argument("--store", required=True, type=Path)
        item.add_argument("--loadout-id", required=True)
        item.add_argument("--version", required=True, type=int)
        item.add_argument("--digest", required=True)
        item.add_argument("--project", required=True, type=Path)
        item.add_argument("--context-store", required=True, type=Path)
        item.add_argument("--context-root", type=Path, default=Path(__file__).resolve().parents[1])
        item.add_argument("--project-id", default="selected-project")
        if command == "compare":
            item.add_argument("--artifact-id", required=True)
    read_parser = subs.add_parser("read")
    read_parser.add_argument("--store", required=True, type=Path)
    read_parser.add_argument("--artifact-id", required=True)
    args = parser.parse_args()
    try:
        if args.command in ("create", "revise"):
            spec = _read_json_file(args.spec, MAX_SPEC_BYTES)
            result = (create(args.store, args.loadout_id, spec) if args.command == "create" else
                      revise(args.store, args.loadout_id, expected_version=args.expected_version,
                             expected_digest=args.expected_digest, spec=spec))
        elif args.command == "read":
            result = read(args.store, args.artifact_id)
        else:
            service = context_pack.ContextPackService(args.project, store=args.context_store,
                                                       context_root=args.context_root, project_id=args.project_id)
            if args.command == "inspect":
                result = inspect(args.store, args.loadout_id, version=args.version,
                                 digest=args.digest, service=service)
            elif args.command == "freeze":
                result = freeze(args.store, args.loadout_id, version=args.version,
                                digest=args.digest, service=service)
            else:
                result = compare(args.store, args.loadout_id, args.artifact_id,
                                 version=args.version, digest=args.digest, service=service)
        sys.stdout.write(context_pack._json(result) + "\n")
    except (context_pack.ContextPackError, json.JSONDecodeError, OSError, UnicodeError) as exc:
        sys.stderr.write(context_pack._json({"error": getattr(exc, "code", "invalid_request"),
                                             "message": getattr(exc, "message", "input is invalid")}) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
