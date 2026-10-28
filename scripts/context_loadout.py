#!/usr/bin/env python3
"""Versioned, source-bound task loadouts built from frozen Context and owner inputs."""

import argparse
import datetime as dt
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
SOURCE_ONLY_SCHEMA_VERSION = 2
CUSTOM_CONTEXT_PACKET_SCHEMA_VERSION = 3
RESEARCH_CITATION_SCHEMA_VERSION = 4
MAX_SPEC_BYTES = 512 * 1024
MAX_REDUCTION_PREVIEWS = 8
MAX_REDUCTION_BYTES = 512 * 1024
PREFERENCE_PROFILE_SCHEMA = "custom.preference-profile-export.v1"
PREFERENCE_PROFILE_QUALIFICATION = (
    "Custom preference data only. Current system, developer, user and project instructions, "
    "and access policy, remain higher priority; this is not a native setting."
)
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


def _preference_profile(value, *, require_active=True):
    fields = {"schema", "ownerId", "ownerRevision", "kitId", "kitVersion", "kitDigest",
              "profileId", "profileRevision", "scope", "projectId", "sessionId", "lineage",
              "expiresAt", "preferences", "conflicts", "previewDigest", "textSha256", "text", "qualification", "exportReceipt"}
    if not isinstance(value, dict) or set(value) != fields or value.get("schema") != PREFERENCE_PROFILE_SCHEMA:
        _fail("invalid_request", "preference profile record must match custom.preference-profile-export.v1")
    if (value["ownerId"] != "custom-ai" or not isinstance(value["ownerRevision"], str)
            or not re.fullmatch(r"[0-9a-f]{40,64}", value["ownerRevision"])
            or not isinstance(value["kitId"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", value["kitId"])
            or type(value["kitVersion"]) is not int or value["kitVersion"] < 1
            or not isinstance(value["kitDigest"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["kitDigest"])
            or not isinstance(value["profileId"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", value["profileId"])
            or type(value["profileRevision"]) is not int or value["profileRevision"] < 1
            or value["scope"] not in {"personal", "project", "session"}
            or not isinstance(value["previewDigest"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["previewDigest"])
            or not isinstance(value["textSha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["textSha256"])
            or not isinstance(value["text"], str) or len(value["text"].encode("utf-8")) > 200_000
            or _sha(value["text"].encode("utf-8")) != value["textSha256"]
            or value["qualification"] != PREFERENCE_PROFILE_QUALIFICATION):
        _fail("invalid_request", "preference profile identity, text digest or qualification is invalid")
    receipt = value["exportReceipt"]
    if (not isinstance(receipt, dict) or set(receipt) != {"schema", "requestId", "inputDigest", "exported", "previewDigest", "textSha256"}
            or receipt.get("schema") != "custom.preference-profile-export-receipt.v1"
            or not isinstance(receipt.get("requestId"), str)
            or not re.fullmatch(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", receipt["requestId"])
            or not isinstance(receipt.get("inputDigest"), str) or not re.fullmatch(r"[0-9a-f]{64}", receipt["inputDigest"])
            or not isinstance(receipt.get("exported"), str)
            or not re.fullmatch(r"exports/profile-[a-z0-9][a-z0-9-]{0,62}-r[1-9][0-9]*-[a-f0-9]{12}\.md", receipt["exported"])
            or receipt.get("previewDigest") != value["previewDigest"] or receipt.get("textSha256") != value["textSha256"]):
        _fail("invalid_request", "preference profile export receipt is invalid")
    if (value["projectId"] is not None and not isinstance(value["projectId"], str)
            or value["sessionId"] is not None and not isinstance(value["sessionId"], str)):
        _fail("invalid_request", "preference profile scope details are invalid")
    expiry = value["expiresAt"]
    if expiry is not None:
        if not isinstance(expiry, str):
            _fail("invalid_request", "preference profile expiry is invalid")
        try:
            parsed = dt.datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        except ValueError:
            _fail("invalid_request", "preference profile expiry is invalid")
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            _fail("invalid_request", "preference profile expiry has no timezone")
        if require_active and parsed.astimezone(dt.timezone.utc) <= dt.datetime.now(dt.timezone.utc):
            _fail("profile_expired", "preference profile is expired")
    lineage = value["lineage"]
    if not isinstance(lineage, list) or not 1 <= len(lineage) <= 8:
        _fail("invalid_request", "preference profile lineage is invalid")
    lineage_fields = {"id", "label", "scope", "project_id", "session_id", "revision", "expires_at", "state"}
    for row in lineage:
        if (not isinstance(row, dict) or set(row) != lineage_fields
                or not isinstance(row.get("id"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", row["id"])
                or not isinstance(row.get("label"), str) or not row["label"].strip() or len(row["label"]) > 80
                or row.get("scope") not in {"personal", "project", "session"}
                or type(row.get("revision")) is not int or row["revision"] < 1
                or row.get("state") != "active"):
            _fail("invalid_request", "preference profile lineage record is invalid")
    last = lineage[-1]
    if (last["id"] != value["profileId"] or last["scope"] != value["scope"]
            or last["revision"] != value["profileRevision"] or last["expires_at"] != value["expiresAt"]):
        _fail("invalid_request", "preference profile lineage does not match its selected revision")
    preferences = value["preferences"]
    if not isinstance(preferences, list) or len(preferences) > 64:
        _fail("invalid_request", "preference profile values are invalid")
    preference_fields = {"id", "text", "swap", "exceptions", "source", "provenance", "override_of"}
    for row in preferences:
        if (not isinstance(row, dict) or set(row) != preference_fields
                or not isinstance(row.get("id"), str) or not row["id"] or len(row["id"]) > 63
                or not isinstance(row.get("text"), str) or len(row["text"]) > 2000
                or not isinstance(row.get("swap"), dict) or len(row["swap"]) > 100
                or not isinstance(row.get("exceptions"), list) or len(row["exceptions"]) > 100
                or not isinstance(row.get("source"), dict) or not isinstance(row.get("provenance"), dict)):
            _fail("invalid_request", "preference profile value is invalid")
    conflicts = value["conflicts"]
    conflict_fields = {"preference", "overridden_by", "winner", "reason"}
    if not isinstance(conflicts, list) or len(conflicts) > 64:
        _fail("invalid_request", "preference profile conflict list is invalid")
    for conflict in conflicts:
        if (not isinstance(conflict, dict) or set(conflict) != conflict_fields
                or not isinstance(conflict.get("preference"), str)
                or not isinstance(conflict.get("reason"), str)
                or not isinstance(conflict.get("overridden_by"), dict)
                or not isinstance(conflict.get("winner"), dict)):
            _fail("invalid_request", "preference profile conflict record is invalid")
    if value["scope"] == "session" and (not value["sessionId"] or not expiry):
        _fail("invalid_request", "session preference profiles require a session and expiry")
    if value["scope"] == "project" and not value["projectId"]:
        _fail("invalid_request", "project preference profiles require a project identity")
    return value


def _custom_context_packet_reference(value):
    fields = {"schema", "owner", "selection", "packetDigest", "contextSha256",
              "kitDigest", "profileDigest", "continuityDigest", "exported"}
    if not isinstance(value, dict) or set(value) != fields or value.get("schema") != "custom.scoped-context-packet-reference.v1":
        _fail("invalid_request", "Custom Context packet reference is invalid")
    owner = value.get("owner")
    if (not isinstance(owner, dict) or set(owner) != {"id", "revision"} or owner.get("id") != "custom-ai"
            or not isinstance(owner.get("revision"), str) or not re.fullmatch(r"[0-9a-f]{40,64}", owner["revision"])):
        _fail("invalid_request", "Custom Context packet owner identity is invalid")
    selection = value.get("selection")
    if (not isinstance(selection, dict) or set(selection) - {"kitId", "profile_id", "continuityStoreId", "project_id", "resource"}
            or not {"kitId", "profile_id", "continuityStoreId", "project_id"} <= set(selection)):
        _fail("invalid_request", "Custom Context packet selection is invalid")
    for key in ("kitId", "profile_id", "continuityStoreId"):
        if not isinstance(selection.get(key), str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", selection[key]):
            _fail("invalid_request", "Custom Context packet selection is invalid")
    project_id = selection.get("project_id")
    if project_id is not None and (not isinstance(project_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", project_id)):
        _fail("invalid_request", "Custom Context packet project identity is invalid")
    if "resource" in selection:
        resource = selection["resource"]
        if (not isinstance(resource, dict) or set(resource) - {"observationIds", "maxAgeSeconds"}
                or not isinstance(resource.get("observationIds"), list) or not 1 <= len(resource["observationIds"]) <= 32
                or any(not isinstance(item, str) or not re.fullmatch(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", item)
                       for item in resource["observationIds"])
                or len(set(resource["observationIds"])) != len(resource["observationIds"])
                or ("maxAgeSeconds" in resource and (type(resource["maxAgeSeconds"]) is not int
                    or not 0 <= resource["maxAgeSeconds"] <= 31_536_000))):
            _fail("invalid_request", "Custom Context packet resource selection is invalid")
    for key in ("packetDigest", "contextSha256", "kitDigest", "profileDigest", "continuityDigest"):
        if not isinstance(value.get(key), str) or not re.fullmatch(r"[a-f0-9]{64}", value[key]):
            _fail("invalid_request", "Custom Context packet digest is invalid")
    if (not isinstance(value.get("exported"), str)
            or not re.fullmatch(r"exports/context-[a-z0-9][a-z0-9-]{0,62}-[a-f0-9]{12}-[a-f0-9]{16}\.md", value["exported"])):
        _fail("invalid_request", "Custom Context packet export identity is invalid")
    return value


def _research_citation(value):
    reference_fields = {"schema", "study", "question", "citation"}
    if not isinstance(value, dict) or set(value) != {"reference", "peek"}:
        _fail("invalid_request", "Research citation source must contain its exact binding and owner read")
    reference = value["reference"]
    if not isinstance(reference, dict) or set(reference) != reference_fields or reference.get("schema") != "deep.research-study-citation-binding.v1":
        _fail("invalid_request", "Research citation binding schema is invalid")
    study = reference.get("study")
    question = reference.get("question")
    binding_citation = reference.get("citation")
    if (not isinstance(study, dict) or set(study) != {"id", "sha256", "revision"}
            or not isinstance(study.get("id"), str) or not re.fullmatch(r"study:[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", study["id"])
            or not isinstance(study.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", study["sha256"])
            or type(study.get("revision")) is not int or study["revision"] < 1
            or not isinstance(question, dict) or set(question) != {"id", "sha256"}
            or not isinstance(question.get("id"), str) or not re.fullmatch(r"study-question:[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", question["id"])
            or not isinstance(question.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", question["sha256"])):
        _fail("invalid_request", "Research Study or question binding is invalid")
    if (not isinstance(binding_citation, dict) or set(binding_citation) != {"id", "sourceDigest", "recordId", "version"}
            or not isinstance(binding_citation.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", binding_citation["id"])
            or not isinstance(binding_citation.get("sourceDigest"), str) or not re.fullmatch(r"[a-f0-9]{64}", binding_citation["sourceDigest"])
            or not isinstance(binding_citation.get("recordId"), str) or not binding_citation["recordId"].strip()
            or len(binding_citation["recordId"]) > 256
            or not (binding_citation.get("version") is None or
                    (isinstance(binding_citation.get("version"), str) and len(binding_citation["version"]) <= 128) or
                    (type(binding_citation.get("version")) is int and abs(binding_citation["version"]) <= 2**53 - 1))):
        _fail("invalid_request", "Research citation source binding is invalid")

    peek = value["peek"]
    peek_fields = {"schema", "owner", "studyId", "studySha256", "studyRevision", "questionId", "questionSha256",
                   "resultStatus", "coverage", "paragraphRefs", "citation", "position", "qualifications", "sourceBinding"}
    if not isinstance(peek, dict) or set(peek) != peek_fields or peek.get("schema") != "deep.research-study-citation-peek.v1":
        _fail("invalid_request", "Research citation owner read schema is invalid")
    owner = peek.get("owner")
    if (not isinstance(owner, dict) or set(owner) != {"id", "revision"} or owner.get("id") != "research-ai"
            or not isinstance(owner.get("revision"), str) or not re.fullmatch(r"[a-f0-9]{40,64}", owner["revision"])):
        _fail("invalid_request", "Research citation owner identity is invalid")
    if (peek.get("studyId") != study["id"] or peek.get("studySha256") != study["sha256"]
            or peek.get("studyRevision") != study["revision"] or peek.get("questionId") != question["id"]
            or peek.get("questionSha256") != question["sha256"] or peek.get("sourceBinding") != reference):
        _fail("invalid_request", "Research citation owner read does not match its exact source binding")
    if (not isinstance(peek.get("resultStatus"), str) or not peek["resultStatus"] or len(peek["resultStatus"]) > 128
            or not isinstance(peek.get("coverage"), str) or not peek["coverage"] or len(peek["coverage"]) > 256):
        _fail("invalid_request", "Research citation answer status or coverage is invalid")
    citation = peek.get("citation")
    citation_fields = {"id", "page", "start", "end", "quote", "quoteTruncated", "notebookId", "recordId", "version", "sourceDigest", "sourceTitle"}
    if (not isinstance(citation, dict) or set(citation) != citation_fields
            or citation.get("id") != binding_citation["id"] or citation.get("sourceDigest") != binding_citation["sourceDigest"]
            or citation.get("recordId") != binding_citation["recordId"] or citation.get("version") != binding_citation["version"]
            or type(citation.get("page")) is not int or citation["page"] < 1
            or type(citation.get("start")) is not int or citation["start"] < 0
            or type(citation.get("end")) is not int or citation["end"] < citation["start"]
            or not isinstance(citation.get("quote"), str) or not citation["quote"].strip() or len(citation["quote"].encode("utf-8")) > 32_000
            or type(citation.get("quoteTruncated")) is not bool
            or not isinstance(citation.get("notebookId"), str) or not citation["notebookId"] or len(citation["notebookId"]) > 256
            or not isinstance(citation.get("sourceTitle"), str) or not citation["sourceTitle"].strip() or len(citation["sourceTitle"]) > 512):
        _fail("invalid_request", "Research citation projection is invalid")
    position = peek.get("position")
    expected_position = {"page": citation["page"], "start": citation["start"], "end": citation["end"],
                         "sourceDigest": citation["sourceDigest"], "recordId": citation["recordId"],
                         "version": citation["version"]}
    if not isinstance(position, dict) or set(position) != set(expected_position) or position != expected_position:
        _fail("invalid_request", "Research citation coordinates do not match the retained source")
    paragraphs = peek.get("paragraphRefs")
    if (not isinstance(paragraphs, list) or len(paragraphs) > 64
            or any(not isinstance(row, dict) or set(row) != {"text", "evidenceId"}
                   or row.get("evidenceId") != citation["id"] or not isinstance(row.get("text"), str)
                   or not row["text"].strip() or len(row["text"].encode("utf-8")) > 32_000 for row in paragraphs)):
        _fail("invalid_request", "Research citation answer paragraphs are invalid")
    qualifications = peek.get("qualifications")
    if (not isinstance(qualifications, list) or not 1 <= len(qualifications) <= 16
            or any(not isinstance(item, str) or not item.strip() or len(item) > 1000 for item in qualifications)):
        _fail("invalid_request", "Research citation qualifications are invalid")
    return {"reference": reference, "peek": peek}


def _spec(value, *, require_active=True):
    if (isinstance(value, dict) and type(value.get("schemaVersion")) is int
            and value.get("schemaVersion") == RESEARCH_CITATION_SCHEMA_VERSION):
        allowed = {"schemaVersion", "variant", "task", "contextPreviewId", "maxTokens",
                   "reductionRequests", "researchCitation"}
        if set(value) - allowed or value.get("variant") != "research-citation":
            _fail("invalid_request", "loadout spec must match context-loadout/v4 research-citation")
        task = value.get("task")
        if not isinstance(task, str) or not task.strip() or len(task) > context_pack.MAX_TASK_CHARS:
            _fail("invalid_request", "task must contain 1 to 2048 characters")
        if not isinstance(value.get("contextPreviewId"), str) or not re.fullmatch(r"[0-9a-f]{32}", value["contextPreviewId"]):
            _fail("invalid_request", "Context preview ID is invalid")
        budget = value.get("maxTokens")
        if type(budget) is not int or not 100 <= budget <= 8192:
            _fail("invalid_request", "maxTokens must be an integer from 100 to 8192")
        requests = value.get("reductionRequests", [])
        if requests != []:
            _fail("invalid_request", "Research citation loadouts preserve the selected citation without unrelated reduction requests")
        citation = _research_citation(value.get("researchCitation"))
        normalized = {"schemaVersion": RESEARCH_CITATION_SCHEMA_VERSION, "variant": "research-citation",
                      "task": task, "contextPreviewId": value["contextPreviewId"], "maxTokens": budget,
                      "reductionRequests": [], "researchCitation": citation}
        if len(context_pack._json(normalized).encode("utf-8")) > MAX_SPEC_BYTES:
            _fail("invalid_request", "loadout spec exceeds its size limit")
        return normalized
    if (isinstance(value, dict) and type(value.get("schemaVersion")) is int
            and value.get("schemaVersion") == CUSTOM_CONTEXT_PACKET_SCHEMA_VERSION):
        allowed = {"schemaVersion", "variant", "task", "contextPreviewId", "maxTokens",
                   "reductionRequests", "customContextPacket", "customContextPacketText"}
        if set(value) - allowed or value.get("variant") != "custom-context-packet":
            _fail("invalid_request", "loadout spec must match context-loadout/v3 custom-context-packet")
        task = value.get("task")
        if not isinstance(task, str) or not task.strip() or len(task) > context_pack.MAX_TASK_CHARS:
            _fail("invalid_request", "task must contain 1 to 2048 characters")
        if not isinstance(value.get("contextPreviewId"), str) or not re.fullmatch(r"[0-9a-f]{32}", value["contextPreviewId"]):
            _fail("invalid_request", "Context preview ID is invalid")
        budget = value.get("maxTokens")
        if type(budget) is not int or not 100 <= budget <= 8192:
            _fail("invalid_request", "maxTokens must be an integer from 100 to 8192")
        reference = _custom_context_packet_reference(value.get("customContextPacket"))
        text = value.get("customContextPacketText")
        if not isinstance(text, str) or len(text.encode("utf-8")) > 200_000 or _sha(text.encode("utf-8")) != reference["contextSha256"]:
            _fail("invalid_request", "Custom Context packet bytes do not match their exact source reference")
        requests = value.get("reductionRequests", [])
        if not isinstance(requests, list) or len(requests) > MAX_REDUCTION_PREVIEWS:
            _fail("invalid_request", "reductionRequests must contain at most eight entries")
        if requests:
            _fail("invalid_request", "Custom packet loadouts do not accept unrelated reduction requests")
        normalized = {"schemaVersion": CUSTOM_CONTEXT_PACKET_SCHEMA_VERSION,
                      "variant": "custom-context-packet", "task": task,
                      "contextPreviewId": value["contextPreviewId"], "maxTokens": budget,
                      "reductionRequests": [], "customContextPacket": reference,
                      "customContextPacketText": text}
        if len(context_pack._json(normalized).encode("utf-8")) > MAX_SPEC_BYTES:
            _fail("invalid_request", "loadout spec exceeds its size limit")
        return normalized
    if (isinstance(value, dict) and type(value.get("schemaVersion")) is int
            and value.get("schemaVersion") == SOURCE_ONLY_SCHEMA_VERSION):
        allowed = {"schemaVersion", "variant", "task", "contextPreviewId", "maxTokens", "reductionRequests"}
        if (set(value) - allowed or value.get("variant") != "source-pack-only"):
            _fail("invalid_request", "loadout spec must match context-loadout/v2 source-pack-only")
        task = value.get("task")
        if not isinstance(task, str) or not task.strip() or len(task) > context_pack.MAX_TASK_CHARS:
            _fail("invalid_request", "task must contain 1 to 2048 characters")
        if not isinstance(value.get("contextPreviewId"), str) or not re.fullmatch(r"[0-9a-f]{32}", value["contextPreviewId"]):
            _fail("invalid_request", "context preview ID is invalid")
        budget = value.get("maxTokens")
        if type(budget) is not int or not 100 <= budget <= 8192:
            _fail("invalid_request", "maxTokens must be an integer from 100 to 8192")
        requests = value.get("reductionRequests", [])
        if not isinstance(requests, list) or len(requests) > MAX_REDUCTION_PREVIEWS:
            _fail("invalid_request", "reductionRequests must contain at most eight entries")
        reductions, seen = [], set()
        for request in requests:
            if (not isinstance(request, dict) or set(request) - {"itemId", "maxLines", "protectedLines"}
                    or not {"itemId", "maxLines"} <= set(request)
                    or not isinstance(request.get("itemId"), str) or not request["itemId"]
                    or len(request["itemId"]) > 160 or request["itemId"] in seen
                    or type(request.get("maxLines")) is not int
                    or not context_pack.REDUCTION_MIN_MAX_LINES <= request["maxLines"] <= context_pack.REDUCTION_MAX_LINES):
                _fail("invalid_request", "reduction request identity or line cap is invalid")
            protected = request.get("protectedLines", [])
            if (not isinstance(protected, list) or len(protected) > 100
                    or any(type(line) is not int or line < 1 for line in protected)
                    or len(set(protected)) != len(protected)):
                _fail("invalid_request", "protectedLines must contain unique positive line numbers")
            seen.add(request["itemId"])
            reductions.append({"itemId": request["itemId"], "maxLines": request["maxLines"],
                               "protectedLines": protected})
        normalized = {"schemaVersion": SOURCE_ONLY_SCHEMA_VERSION, "variant": "source-pack-only",
                      "task": task, "contextPreviewId": value["contextPreviewId"],
                      "maxTokens": budget, "reductionRequests": reductions}
        if len(context_pack._json(normalized).encode("utf-8")) > MAX_SPEC_BYTES:
            _fail("invalid_request", "loadout spec exceeds its size limit")
        return normalized
    legacy_keys = {"schemaVersion", "task", "contextPreviewId", "maxTokens", "ownerPacket"}
    profile_keys = {"schemaVersion", "task", "contextPreviewId", "maxTokens", "preferenceProfile"}
    if (not isinstance(value, dict) or (set(value) - {"reductionRequests"}) not in (legacy_keys, profile_keys)
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
    if "ownerPacket" in value:
        packet = value["ownerPacket"]
        owner_task, records, maestro_results = linked_context._validate(packet)
        if maestro_results:
            _fail("invalid_request", "Context loadouts accept only Research and Planning owner records")
        if owner_task != task:
            _fail("invalid_request", "owner packet task must match the loadout task")
        normalized_owner = {"ownerPacket": {"task": owner_task, "records": records}}
    else:
        normalized_owner = {"preferenceProfile": _preference_profile(value["preferenceProfile"], require_active=require_active)}
    requests = value.get("reductionRequests", [])
    if not isinstance(requests, list) or len(requests) > MAX_REDUCTION_PREVIEWS:
        _fail("invalid_request", "reductionRequests must contain at most eight entries")
    reductions, seen = [], set()
    for request in requests:
        if (not isinstance(request, dict) or set(request) - {"itemId", "maxLines", "protectedLines"}
                or not {"itemId", "maxLines"} <= set(request)
                or not isinstance(request.get("itemId"), str) or not request["itemId"]
                or len(request["itemId"]) > 160 or request["itemId"] in seen
                or type(request.get("maxLines")) is not int
                or not context_pack.REDUCTION_MIN_MAX_LINES <= request["maxLines"]
                <= context_pack.REDUCTION_MAX_LINES):
            _fail("invalid_request", "reduction request identity or line cap is invalid")
        protected = request.get("protectedLines", [])
        if (not isinstance(protected, list) or len(protected) > 100
                or any(type(line) is not int or line < 1 for line in protected)
                or len(set(protected)) != len(protected)):
            _fail("invalid_request", "protectedLines must contain unique positive line numbers")
        seen.add(request["itemId"])
        reductions.append({"itemId": request["itemId"], "maxLines": request["maxLines"],
                           "protectedLines": protected})
    normalized = {"schemaVersion": SCHEMA_VERSION, "task": task,
                  "contextPreviewId": value["contextPreviewId"], "maxTokens": budget,
                  **normalized_owner, "reductionRequests": reductions}
    if len(context_pack._json(normalized).encode("utf-8")) > MAX_SPEC_BYTES:
        _fail("invalid_request", "loadout spec exceeds its size limit")
    return normalized


def _revision_digest(loadout_id, version, spec):
    body = {"schemaVersion": spec["schemaVersion"], "loadoutId": loadout_id,
            "version": version, "spec": spec}
    return _sha(context_pack._json(body).encode("utf-8"))


def _preference_profile_text(profile):
    return ("## Custom preference profile · caller-provided, lower-priority data\n\n"
            + PREFERENCE_PROFILE_QUALIFICATION + "\n\n" + profile["text"])


def _revision_name(loadout_id, version):
    return f"loadout-{loadout_id}-v{version}.json"


def _read_revision(store, loadout_id, version):
    body = context_pack._load(store, _revision_name(loadout_id, version))
    if (not isinstance(body, dict) or set(body) != {
            "schema_version", "schemaVersion", "loadoutId", "version", "spec", "digest"}
            or body["schema_version"] != SCHEMA_VERSION
            or body["schemaVersion"] != body["spec"].get("schemaVersion") or body["loadoutId"] != loadout_id
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
    body = {"schema_version": SCHEMA_VERSION, "schemaVersion": spec["schemaVersion"], "loadoutId": loadout_id,
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
        body = {"schema_version": SCHEMA_VERSION, "schemaVersion": spec["schemaVersion"], "loadoutId": loadout_id,
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


def _source_file_hashes(manifest):
    rows = []
    for item in manifest.get("items", []):
        source = item.get("source", {}) if isinstance(item, dict) else {}
        if not isinstance(source, dict) or source.get("owner") not in {"project", "context"}:
            _fail("store_invalid", "Context source item identity is invalid")
        digest, path = source.get("file_sha256"), source.get("path")
        if not isinstance(path, str) or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            _fail("store_invalid", "Context source file hash is invalid")
        rows.append({"itemId": item.get("item_id"), "sourceOwner": source["owner"], "path": path,
                     "fileSha256": digest})
    return rows


def _assemble_source_only(revision, service):
    spec = revision["spec"]
    raw_json = service.export(spec["contextPreviewId"], format="json")
    raw_text = service.export(spec["contextPreviewId"], format="text")
    try:
        manifest = json.loads(raw_json.decode("utf-8"))
        rendered_text = raw_text.decode("utf-8")
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise context_pack.ContextPackError("store_invalid", "Context pack render is invalid") from exc
    if manifest.get("preview_id") != spec["contextPreviewId"] or manifest.get("task") != spec["task"]:
        _fail("task_mismatch", "source-only loadout task must match its selected Context preview")
    if manifest.get("project", {}).get("project_id") != service.project_id:
        _fail("binding_mismatch", "Context preview belongs to another configured project identity")
    pack_id = manifest.get("pack_id")
    if not isinstance(pack_id, str) or not re.fullmatch(r"[0-9a-f]{64}", pack_id):
        _fail("store_invalid", "Context pack identity is invalid")
    files = _source_file_hashes(manifest)
    text_sha = _sha(raw_text)
    source_artifact = {
        "schema": "context.source-pack-artifact.v1",
        "kind": "context_source_pack",
        "owner": "context-ai",
        "contextProjectId": service.project_id,
        "previewId": spec["contextPreviewId"],
        "revision": manifest.get("project", {}).get("head"),
        "packId": pack_id,
        "manifest": manifest,
        "manifestSha256": _sha(raw_json),
        "jsonRender": raw_json.decode("utf-8"),
        "jsonSha256": _sha(raw_json),
        "textRender": rendered_text,
        "textSha256": text_sha,
        "fileHashes": files,
    }
    source_artifact["artifactId"] = _sha(context_pack._json(source_artifact).encode("utf-8"))
    combined = f"# Context loadout {revision['loadoutId']} v{revision['version']}\n\n{rendered_text}"
    raw_combined = combined.encode("utf-8")
    if len(raw_combined) > 4 * spec["maxTokens"]:
        _fail("budget_too_small", "combined Context content exceeds the loadout budget")
    item_rows = manifest.get("items", [])
    inspection = {"includedContextItems": [x.get("item_id") for x in item_rows if isinstance(x, dict)],
                  "omittedContextItems": manifest.get("omissions", []),
                  "includedOwnerRefs": [], "omittedOwnerRefs": [],
                  "combinedBytes": len(raw_combined), "estimatedTokens": (len(raw_combined) + 3) // 4,
                  "budgetTokens": spec["maxTokens"]}
    reductions = [context_pack.preview_pack_reduction(
        service, spec["contextPreviewId"], request["itemId"], max_lines=request["maxLines"],
        protected_lines=request.get("protectedLines", []))
        for request in spec["reductionRequests"]]
    if len(context_pack._json(reductions).encode("utf-8")) > MAX_REDUCTION_BYTES:
        _fail("reduction_too_large", "combined reduction previews exceed their size limit")
    return {"schemaVersion": SOURCE_ONLY_SCHEMA_VERSION, "loadout": _public_revision(revision),
            "assemblyState": "assembled", "deliveryState": "not_sent",
            "contextPack": {"previewId": spec["contextPreviewId"], "packId": pack_id,
                            "manifest": manifest, "text": rendered_text, "textSha256": text_sha},
            "sourceArtifact": source_artifact, "reductionPreviews": reductions,
            "inspection": inspection, "text": combined, "textSha256": _sha(raw_combined)}


def _custom_packet_qualification(reference):
    return ("Source: current canonical Custom scoped Context packet. "
            f"Custom owner revision {reference['owner']['revision']}; "
            f"packet digest {reference['packetDigest']}. "
            "This retained content does not transfer approvals, authority or delivery state.")


def _assemble_custom_context_packet(revision, service):
    spec = revision["spec"]
    base_spec = {"schemaVersion": SOURCE_ONLY_SCHEMA_VERSION, "variant": "source-pack-only",
                 "task": spec["task"], "contextPreviewId": spec["contextPreviewId"],
                 "maxTokens": spec["maxTokens"], "reductionRequests": []}
    base_revision = {"schema_version": SCHEMA_VERSION, "schemaVersion": SOURCE_ONLY_SCHEMA_VERSION,
                     "loadoutId": revision["loadoutId"], "version": revision["version"],
                     "spec": base_spec, "digest": _revision_digest(revision["loadoutId"], revision["version"], base_spec)}
    base = _assemble_source_only(base_revision, service)
    reference = spec["customContextPacket"]
    custom_text = spec["customContextPacketText"]
    combined = (base["text"] + "\n\n## Custom scoped Context packet\n\n" +
                _custom_packet_qualification(reference) + "\n\n" + custom_text)
    raw = combined.encode("utf-8")
    if len(raw) > 4 * spec["maxTokens"]:
        _fail("budget_too_small", "The complete Custom Context packet does not fit; choose a larger budget or smaller source packet.")
    inspection = {**base["inspection"], "combinedBytes": len(raw), "estimatedTokens": (len(raw) + 3) // 4,
                  "customContextPacket": {"owner": reference["owner"]["id"],
                                          "ownerRevision": reference["owner"]["revision"],
                                          "packetDigest": reference["packetDigest"],
                                          "contextSha256": reference["contextSha256"]}}
    return {"schemaVersion": CUSTOM_CONTEXT_PACKET_SCHEMA_VERSION, "loadout": _public_revision(revision),
            "assemblyState": "assembled", "deliveryState": "not_sent", "contextPack": base["contextPack"],
            "sourceArtifact": base["sourceArtifact"], "customContextPacket": reference,
            "customContextPacketText": custom_text, "reductionPreviews": base["reductionPreviews"],
            "inspection": inspection, "text": combined, "textSha256": _sha(raw)}


def _research_citation_text(source):
    reference, peek = source["reference"], source["peek"]
    citation = peek["citation"]
    study, question = reference["study"], reference["question"]
    lines = [
        "## One exact Research citation",
        "",
        "This loadout retains one selected citation and its matching answer paragraphs; it does not expand to the whole Study answer.",
        "The host must reread the canonical Research source before freezing and verifying use. Context does not infer entailment, truth, currentness or completeness.",
        "",
        f"- Study: {study['id']} · revision {study['revision']} · SHA-256 {study['sha256']}",
        f"- Question: {question['id']} · SHA-256 {question['sha256']}",
        f"- Citation: {citation['id']} · {citation['sourceTitle']}",
        f"- Source record: {citation['recordId']} · version {citation['version']}",
        f"- Source digest: {citation['sourceDigest']} · notebook {citation['notebookId']}",
        f"- Exact location: page {citation['page']}, offsets {citation['start']}–{citation['end']}",
        f"- Research answer status: {peek['resultStatus']} · coverage: {peek['coverage']}",
        "",
        "### Retained citation quote" + (" · truncated by Research" if citation["quoteTruncated"] else ""),
        "",
        citation["quote"],
        "",
        "### Matching Research answer paragraphs",
        "",
    ]
    if peek["paragraphRefs"]:
        lines.extend(f"- {row['text']}" for row in peek["paragraphRefs"])
    else:
        lines.append("No retained answer paragraph references this citation.")
    lines.extend(["", "### Source qualifications", ""])
    lines.extend(f"- {qualification}" for qualification in peek["qualifications"])
    return "\n".join(lines)


def _assemble_research_citation(revision, service):
    spec = revision["spec"]
    base_spec = {"schemaVersion": SOURCE_ONLY_SCHEMA_VERSION, "variant": "source-pack-only",
                 "task": spec["task"], "contextPreviewId": spec["contextPreviewId"],
                 "maxTokens": spec["maxTokens"], "reductionRequests": []}
    base_revision = {"schema_version": SCHEMA_VERSION, "schemaVersion": SOURCE_ONLY_SCHEMA_VERSION,
                     "loadoutId": revision["loadoutId"], "version": revision["version"],
                     "spec": base_spec,
                     "digest": _revision_digest(revision["loadoutId"], revision["version"], base_spec)}
    base = _assemble_source_only(base_revision, service)
    source = spec["researchCitation"]
    citation_text = _research_citation_text(source)
    combined = base["text"] + "\n\n" + citation_text
    raw = combined.encode("utf-8")
    if len(raw) > 4 * spec["maxTokens"]:
        _fail("budget_too_small", "The selected Context pack and exact Research citation do not fit; choose a larger budget or smaller pack.")
    reference, peek = source["reference"], source["peek"]
    citation = peek["citation"]
    inspection = {**base["inspection"], "researchCitation": {
        "binding": reference,
        "owner": peek["owner"],
        "citationTitle": citation["sourceTitle"],
        "sourceDigest": citation["sourceDigest"],
        "recordId": citation["recordId"],
        "version": citation["version"],
        "page": citation["page"],
        "start": citation["start"],
        "end": citation["end"],
        "quoteTruncated": citation["quoteTruncated"],
        "matchingParagraphCount": len(peek["paragraphRefs"]),
        "resultStatus": peek["resultStatus"],
        "coverage": peek["coverage"],
        "qualifications": peek["qualifications"],
    }, "combinedBytes": len(raw), "estimatedTokens": (len(raw) + 3) // 4}
    return {"schemaVersion": RESEARCH_CITATION_SCHEMA_VERSION, "loadout": _public_revision(revision),
            "assemblyState": "assembled", "deliveryState": "not_sent", "contextPack": base["contextPack"],
            "sourceArtifact": base["sourceArtifact"], "researchCitation": source,
            "reductionPreviews": base["reductionPreviews"], "inspection": inspection,
            "text": combined, "textSha256": _sha(raw)}


def _assemble(store, revision, service):
    _assert_disjoint(store, service)
    spec = revision["spec"]
    if spec["schemaVersion"] == SOURCE_ONLY_SCHEMA_VERSION:
        return _assemble_source_only(revision, service)
    if spec["schemaVersion"] == CUSTOM_CONTEXT_PACKET_SCHEMA_VERSION:
        return _assemble_custom_context_packet(revision, service)
    if spec["schemaVersion"] == RESEARCH_CITATION_SCHEMA_VERSION:
        return _assemble_research_citation(revision, service)
    project_json = service.export(spec["contextPreviewId"], format="json")
    project_text = service.export(spec["contextPreviewId"], format="text")
    try:
        project_manifest = json.loads(project_json.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise context_pack.ContextPackError("store_invalid", "Context pack JSON is invalid") from exc
    linked_store = store / "owner-artifacts"
    if "preferenceProfile" in spec:
        profile = spec["preferenceProfile"]
        if project_manifest.get("task") != spec["task"]:
            _fail("task_mismatch", "preference loadout task must match the selected Context preview")
        profile_text = _preference_profile_text(profile)
        included = [{"kind": "preference_profile", "owner": "custom-ai",
                     "record_id": profile["profileId"],
                     "revision": f"kit-v{profile['kitVersion']}-profile-r{profile['profileRevision']}",
                     "digest": "sha256:" + profile["previewDigest"],
                     "qualification": PREFERENCE_PROFILE_QUALIFICATION}]
        owner_artifact = {"schema": "context.preference-profile-artifact.v1",
                          "profile": profile, "included": included, "omissions": [],
                          "text": profile_text, "render_sha256": _sha(profile_text.encode("utf-8"))}
        owner_body = {"schema_version": SCHEMA_VERSION, "render_sha256": owner_artifact["render_sha256"],
                      "artifact": owner_artifact}
        owner_body["artifact_id"] = _sha(context_pack._json(owner_body).encode("utf-8"))
        linked = {"included": included, "omissions": []}
        linked_body = owner_body
        owner_text = profile_text
    else:
        linked = linked_context.assemble(linked_store, spec["ownerPacket"], max_tokens=spec["maxTokens"])
        linked_body = context_pack._load(linked_store, f"linked-{linked['artifactId']}.json")
        owner_text = linked["text"]
    combined = (f"# Context loadout {revision['loadoutId']} v{revision['version']}\n\n"
                + project_text.decode("utf-8") + "\n\n" + owner_text)
    raw = combined.encode("utf-8")
    if len(raw) > 4 * spec["maxTokens"]:
        _fail("budget_too_small", "combined Context and owner content exceeds the loadout budget")
    project_pack_id = project_manifest.get("pack_id")
    if not isinstance(project_pack_id, str) or not re.fullmatch(r"[0-9a-f]{64}", project_pack_id):
        _fail("store_invalid", "Context pack identity is invalid")
    manifest = project_manifest.get("items", [])
    omissions = project_manifest.get("omissions", [])
    reduction_previews = [context_pack.preview_pack_reduction(
        service, spec["contextPreviewId"], request["itemId"], max_lines=request["maxLines"],
        protected_lines=request.get("protectedLines", []))
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


def _validate_reductions(reductions, requests, manifest, preview_id, pack_id):
    if (not isinstance(reductions, list) or len(reductions) != len(requests)
            or len(context_pack._json(reductions).encode("utf-8")) > MAX_REDUCTION_BYTES):
        _fail("store_invalid", "frozen reduction previews are invalid or oversized")
    manifest_items = manifest.get("items")
    if not isinstance(manifest_items, list):
        _fail("store_invalid", "frozen Context manifest item list is invalid")
    included_items = {item.get("item_id"): item for item in manifest_items if isinstance(item, dict)}
    for reduction, request in zip(reductions, requests):
        if not isinstance(reduction, dict):
            _fail("store_invalid", "frozen reduction preview is invalid")
        source_ref, size = reduction.get("source_ref"), reduction.get("size")
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
        if (reduction.get("schema") != context_pack.REDUCTION_SCHEMA
                or reduction.get("preview_id") != _sha(context_pack._json(
                    {k: v for k, v in reduction.items() if k != "preview_id"}).encode("utf-8"))
                or source_ref.get("preview_id") != preview_id or source_ref.get("pack_id") != pack_id
                or source_ref.get("item_id") != request["itemId"]
                or request["maxLines"] != reduction.get("max_lines")
                or request.get("protectedLines", []) != reduction.get("protected_lines", [])
                or source is None or source.get("kind") != "source"
                or source_ref.get("source") != source.get("source") or not valid_segments
                or _sha("".join(rebuilt).encode("utf-8")) != source_ref.get("raw_sha256")
                or size.get("before_bytes") != len("".join(rebuilt).encode("utf-8"))
                or size.get("after_bytes") != len("".join(projected).encode("utf-8"))
                or "".join(projected) != reduction.get("projected_text")):
            _fail("store_invalid", "reduction preview is not bound to its frozen Context source")


def _read_source_only(artifact_id, body):
    expected_fields = {"schema_version", "schemaVersion", "loadout", "assemblyState", "deliveryState",
                       "contextPack", "sourceArtifact", "reductionPreviews", "inspection", "text",
                       "textSha256", "artifactState", "artifactId"}
    if (set(body) != expected_fields or body.get("artifactId") != artifact_id
            or body.get("schema_version") != SCHEMA_VERSION
            or body.get("schemaVersion") != SOURCE_ONLY_SCHEMA_VERSION
            or body.get("assemblyState") != "assembled" or body.get("deliveryState") != "not_sent"
            or body.get("artifactState") != "frozen" or _snapshot_id(body) != artifact_id):
        _fail("store_invalid", "source-only Context loadout artifact integrity check failed")
    try:
        loadout = body["loadout"]
        if (not isinstance(loadout, dict) or loadout.get("state") != "referenced"
                or loadout.get("schemaVersion") != SOURCE_ONLY_SCHEMA_VERSION
                or loadout.get("loadoutId") != _identity(loadout.get("loadoutId"))
                or type(loadout.get("version")) is not int or loadout["version"] < 1
                or loadout.get("spec") != _spec(loadout.get("spec"), require_active=False)
                or loadout.get("digest") != _revision_digest(loadout["loadoutId"], loadout["version"], loadout["spec"])):
            _fail("store_invalid", "frozen source-only loadout revision is invalid")
        source = body["sourceArtifact"]
        source_fields = {"schema", "kind", "owner", "artifactId", "contextProjectId", "previewId", "revision", "packId",
                         "manifest", "manifestSha256", "jsonRender", "jsonSha256", "textRender", "textSha256", "fileHashes"}
        if (not isinstance(source, dict) or set(source) != source_fields
                or source.get("schema") != "context.source-pack-artifact.v1"
                or source.get("kind") != "context_source_pack" or source.get("owner") != "context-ai"
                or not isinstance(source.get("contextProjectId"), str) or not source["contextProjectId"]
                or source.get("previewId") != loadout["spec"]["contextPreviewId"]
                or not isinstance(source.get("manifest"), dict)
                or not isinstance(source["manifest"].get("project"), dict)
                or source.get("contextProjectId") != source.get("manifest", {}).get("project", {}).get("project_id")
                or source.get("revision") != source.get("manifest", {}).get("project", {}).get("head")):
            _fail("store_invalid", "frozen Context source identity is invalid")
        source_identity = {k: v for k, v in source.items() if k != "artifactId"}
        manifest = source["manifest"]
        raw_json = source["jsonRender"].encode("utf-8")
        if json.loads(raw_json.decode("utf-8")) != manifest:
            _fail("store_invalid", "frozen Context manifest differs from its exact JSON render")
        pack_id, wire, renders = context_pack._render_pack({k: v for k, v in manifest.items() if k != "pack_id"})
        rendered_text = source["textRender"].encode("utf-8")
        expected_files = _source_file_hashes(manifest)
        combined = body["text"].encode("utf-8")
    except (AttributeError, KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise context_pack.ContextPackError("store_invalid", "source-only Context loadout contents are invalid") from exc
    context = body["contextPack"]
    expected_context_ids = [x.get("item_id") for x in manifest.get("items", []) if isinstance(x, dict)]
    expected_combined = f"# Context loadout {loadout['loadoutId']} v{loadout['version']}\n\n{renders['text']['content']}"
    if (source.get("artifactId") != _sha(context_pack._json(source_identity).encode("utf-8"))
            or source.get("packId") != pack_id or wire != manifest
            or renders["json"]["content"].encode("utf-8") != raw_json
            or renders["text"]["content"].encode("utf-8") != rendered_text
            or source.get("manifestSha256") != _sha(raw_json) or source.get("jsonSha256") != _sha(raw_json)
            or source.get("textSha256") != _sha(rendered_text) or source.get("fileHashes") != expected_files
            or context != {"previewId": source["previewId"], "packId": pack_id, "manifest": manifest,
                           "text": renders["text"]["content"], "textSha256": _sha(rendered_text)}
            or body["text"] != expected_combined or _sha(combined) != body.get("textSha256")):
        _fail("store_invalid", "frozen Context source render or hashes do not match its identity")
    inspection = body["inspection"]
    if (not isinstance(inspection, dict) or inspection.get("includedContextItems") != expected_context_ids
            or inspection.get("omittedContextItems") != manifest.get("omissions")
            or inspection.get("includedOwnerRefs") != [] or inspection.get("omittedOwnerRefs") != []
            or inspection.get("combinedBytes") != len(combined)
            or inspection.get("estimatedTokens") != (len(combined) + 3) // 4
            or inspection.get("budgetTokens") != loadout["spec"]["maxTokens"]
            or len(combined) > 4 * loadout["spec"]["maxTokens"]):
        _fail("store_invalid", "frozen source-only loadout inspection does not match its content")
    _validate_reductions(body["reductionPreviews"], loadout["spec"]["reductionRequests"],
                         manifest, source["previewId"], pack_id)
    return body


def _read_custom_context_packet(artifact_id, body):
    expected_fields = {"schema_version", "schemaVersion", "loadout", "assemblyState", "deliveryState",
                       "contextPack", "sourceArtifact", "customContextPacket", "customContextPacketText",
                       "reductionPreviews", "inspection", "text", "textSha256", "artifactState", "artifactId"}
    if (not isinstance(body, dict) or set(body) != expected_fields or body.get("artifactId") != artifact_id
            or body.get("schema_version") != SCHEMA_VERSION or body.get("schemaVersion") != CUSTOM_CONTEXT_PACKET_SCHEMA_VERSION
            or body.get("assemblyState") != "assembled" or body.get("deliveryState") != "not_sent"
            or body.get("artifactState") != "frozen" or _snapshot_id(body) != artifact_id):
        _fail("store_invalid", "frozen Custom Context loadout artifact integrity check failed")
    loadout = body.get("loadout")
    if (not isinstance(loadout, dict) or loadout.get("state") != "referenced"
            or loadout.get("schemaVersion") != CUSTOM_CONTEXT_PACKET_SCHEMA_VERSION
            or loadout.get("loadoutId") != _identity(loadout.get("loadoutId"))
            or type(loadout.get("version")) is not int or loadout["version"] < 1):
        _fail("store_invalid", "frozen Custom Context loadout revision is invalid")
    spec = _spec(loadout.get("spec"), require_active=False)
    if (spec != loadout.get("spec") or spec["variant"] != "custom-context-packet"
            or loadout.get("digest") != _revision_digest(loadout["loadoutId"], loadout["version"], spec)):
        _fail("store_invalid", "frozen Custom Context loadout revision is invalid")
    reference = _custom_context_packet_reference(body.get("customContextPacket"))
    custom_text = body.get("customContextPacketText")
    if (reference != spec["customContextPacket"] or custom_text != spec["customContextPacketText"]
            or not isinstance(custom_text, str) or _sha(custom_text.encode("utf-8")) != reference["contextSha256"]):
        _fail("store_invalid", "frozen Custom Context packet source changed")
    source = body.get("sourceArtifact")
    if not isinstance(source, dict) or not isinstance(source.get("textRender"), str):
        _fail("store_invalid", "frozen Context source pack is missing")
    base_text = f"# Context loadout {loadout['loadoutId']} v{loadout['version']}\n\n{source['textRender']}"
    expected_text = (base_text + "\n\n## Custom scoped Context packet\n\n" +
                     _custom_packet_qualification(reference) + "\n\n" + custom_text)
    raw = expected_text.encode("utf-8")
    if (body.get("text") != expected_text or body.get("textSha256") != _sha(raw)
            or len(raw) > 4 * spec["maxTokens"]):
        _fail("store_invalid", "frozen Custom Context packet render or budget is invalid")
    inspection = body.get("inspection")
    if not isinstance(inspection, dict):
        _fail("store_invalid", "frozen Custom Context packet inspection is invalid")
    base_inspection = {key: value for key, value in inspection.items() if key != "customContextPacket"}
    base_size = len(base_text.encode("utf-8"))
    base_inspection["combinedBytes"] = base_size
    base_inspection["estimatedTokens"] = (base_size + 3) // 4
    expected_inspection = {**base_inspection, "combinedBytes": len(raw), "estimatedTokens": (len(raw) + 3) // 4,
                           "customContextPacket": {"owner": reference["owner"]["id"],
                                                   "ownerRevision": reference["owner"]["revision"],
                                                   "packetDigest": reference["packetDigest"],
                                                   "contextSha256": reference["contextSha256"]}}
    if inspection != expected_inspection or inspection.get("budgetTokens") != spec["maxTokens"]:
        _fail("store_invalid", "frozen Custom Context packet inspection does not match its render")
    base_spec = {"schemaVersion": SOURCE_ONLY_SCHEMA_VERSION, "variant": "source-pack-only",
                 "task": spec["task"], "contextPreviewId": spec["contextPreviewId"],
                 "maxTokens": spec["maxTokens"], "reductionRequests": []}
    base_loadout = {**loadout, "schemaVersion": SOURCE_ONLY_SCHEMA_VERSION, "spec": base_spec,
                    "digest": _revision_digest(loadout["loadoutId"], loadout["version"], base_spec)}
    base_body = {key: value for key, value in body.items()
                 if key not in {"customContextPacket", "customContextPacketText"}}
    base_body["schemaVersion"] = SOURCE_ONLY_SCHEMA_VERSION
    base_body["loadout"] = base_loadout
    base_body["inspection"] = base_inspection
    base_body["text"] = base_text
    base_body["textSha256"] = _sha(base_text.encode("utf-8"))
    base_body["artifactId"] = _snapshot_id(base_body)
    _read_source_only(base_body["artifactId"], base_body)
    return body


def _read_research_citation(artifact_id, body):
    expected_fields = {"schema_version", "schemaVersion", "loadout", "assemblyState", "deliveryState",
                       "contextPack", "sourceArtifact", "researchCitation", "reductionPreviews",
                       "inspection", "text", "textSha256", "artifactState", "artifactId"}
    if (not isinstance(body, dict) or set(body) != expected_fields or body.get("artifactId") != artifact_id
            or body.get("schema_version") != SCHEMA_VERSION or body.get("schemaVersion") != RESEARCH_CITATION_SCHEMA_VERSION
            or body.get("assemblyState") != "assembled" or body.get("deliveryState") != "not_sent"
            or body.get("artifactState") != "frozen" or _snapshot_id(body) != artifact_id):
        _fail("store_invalid", "frozen Research citation Context loadout integrity check failed")
    loadout = body.get("loadout")
    if (not isinstance(loadout, dict) or loadout.get("state") != "referenced"
            or loadout.get("schemaVersion") != RESEARCH_CITATION_SCHEMA_VERSION
            or loadout.get("loadoutId") != _identity(loadout.get("loadoutId"))
            or type(loadout.get("version")) is not int or loadout["version"] < 1):
        _fail("store_invalid", "frozen Research citation loadout revision is invalid")
    spec = _spec(loadout.get("spec"), require_active=False)
    if (spec != loadout.get("spec") or loadout.get("digest") !=
            _revision_digest(loadout["loadoutId"], loadout["version"], spec)):
        _fail("store_invalid", "frozen Research citation loadout revision is invalid")
    source = _research_citation(body.get("researchCitation"))
    if source != spec["researchCitation"]:
        _fail("store_invalid", "frozen Research citation differs from its reviewed source binding")
    context_source = body.get("sourceArtifact")
    if not isinstance(context_source, dict) or not isinstance(context_source.get("textRender"), str):
        _fail("store_invalid", "frozen Context source pack is missing")
    base_text = f"# Context loadout {loadout['loadoutId']} v{loadout['version']}\n\n{context_source['textRender']}"
    expected_text = base_text + "\n\n" + _research_citation_text(source)
    raw = expected_text.encode("utf-8")
    if (body.get("text") != expected_text or body.get("textSha256") != _sha(raw)
            or len(raw) > 4 * spec["maxTokens"]):
        _fail("store_invalid", "frozen Research citation render or budget is invalid")
    inspection = body.get("inspection")
    if not isinstance(inspection, dict):
        _fail("store_invalid", "frozen Research citation inspection is invalid")
    base_inspection = {key: value for key, value in inspection.items() if key != "researchCitation"}
    base_bytes = len(base_text.encode("utf-8"))
    base_inspection["combinedBytes"] = base_bytes
    base_inspection["estimatedTokens"] = (base_bytes + 3) // 4
    peek, citation = source["peek"], source["peek"]["citation"]
    expected_inspection = {**base_inspection, "combinedBytes": len(raw), "estimatedTokens": (len(raw) + 3) // 4,
                           "researchCitation": {
                               "binding": source["reference"], "owner": peek["owner"],
                               "citationTitle": citation["sourceTitle"], "sourceDigest": citation["sourceDigest"],
                               "recordId": citation["recordId"], "version": citation["version"],
                               "page": citation["page"], "start": citation["start"], "end": citation["end"],
                               "quoteTruncated": citation["quoteTruncated"],
                               "matchingParagraphCount": len(peek["paragraphRefs"]),
                               "resultStatus": peek["resultStatus"], "coverage": peek["coverage"],
                               "qualifications": peek["qualifications"],
                           }}
    if inspection != expected_inspection or inspection.get("budgetTokens") != spec["maxTokens"]:
        _fail("store_invalid", "frozen Research citation inspection does not match its exact projection")
    base_spec = {"schemaVersion": SOURCE_ONLY_SCHEMA_VERSION, "variant": "source-pack-only",
                 "task": spec["task"], "contextPreviewId": spec["contextPreviewId"],
                 "maxTokens": spec["maxTokens"], "reductionRequests": []}
    base_loadout = {**loadout, "schemaVersion": SOURCE_ONLY_SCHEMA_VERSION, "spec": base_spec,
                    "digest": _revision_digest(loadout["loadoutId"], loadout["version"], base_spec)}
    base_body = {key: value for key, value in body.items() if key != "researchCitation"}
    base_body["schemaVersion"] = SOURCE_ONLY_SCHEMA_VERSION
    base_body["loadout"] = base_loadout
    base_body["inspection"] = base_inspection
    base_body["text"] = base_text
    base_body["textSha256"] = _sha(base_text.encode("utf-8"))
    base_body["artifactId"] = _snapshot_id(base_body)
    _read_source_only(base_body["artifactId"], base_body)
    return body


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
    if isinstance(body, dict) and body.get("schemaVersion") == SOURCE_ONLY_SCHEMA_VERSION:
        return _read_source_only(artifact_id, body)
    if isinstance(body, dict) and body.get("schemaVersion") == CUSTOM_CONTEXT_PACKET_SCHEMA_VERSION:
        return _read_custom_context_packet(artifact_id, body)
    if isinstance(body, dict) and body.get("schemaVersion") == RESEARCH_CITATION_SCHEMA_VERSION:
        return _read_research_citation(artifact_id, body)
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
                or loadout.get("spec") != _spec(loadout.get("spec"), require_active=False)
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
        if owner_artifact.get("schema") == "context.preference-profile-artifact.v1":
            if set(owner_artifact) != {"schema", "profile", "included", "omissions", "text", "render_sha256"}:
                _fail("store_invalid", "frozen preference owner artifact is invalid")
            profile = _preference_profile(owner_artifact["profile"], require_active=False)
            owner_text = _preference_profile_text(profile)
            expected_included = [{"kind": "preference_profile", "owner": "custom-ai",
                                  "record_id": profile["profileId"],
                                  "revision": f"kit-v{profile['kitVersion']}-profile-r{profile['profileRevision']}",
                                  "digest": "sha256:" + profile["previewDigest"],
                                  "qualification": PREFERENCE_PROFILE_QUALIFICATION}]
            if (owner_artifact["included"] != expected_included or owner_artifact["omissions"] != []
                    or owner_artifact["text"] != owner_text
                    or owner_artifact["render_sha256"] != _sha(owner_text.encode("utf-8"))):
                _fail("store_invalid", "frozen preference source record does not match its rendered content")
            owner_pack = owner_wire = owner_renders = None
        else:
            owner_pack, owner_wire, owner_renders = context_pack._render_pack(
                {k: v for k, v in owner_artifact["manifest"].items() if k != "pack_id"})
            owner_text = owner_artifact["text"]
        combined = body["text"].encode("utf-8")
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise context_pack.ContextPackError("store_invalid", "loadout artifact contents are invalid") from exc
    inspection = body["inspection"]
    expected_context_ids = [row.get("item_id") for row in manifest.get("items", []) if isinstance(row, dict)]
    is_profile_artifact = owner_artifact.get("schema") == "context.preference-profile-artifact.v1"
    owner_valid = (
        owner_body.get("render_sha256") == owner_artifact.get("render_sha256")
        and _sha(owner_text.encode("utf-8")) == owner_body.get("render_sha256")
        and (is_profile_artifact or (
            owner_pack == owner_artifact.get("pack_id") and owner_wire == owner_artifact.get("manifest")
            and owner_renders["text"]["content"] == owner_text
            and owner_renders["text"]["sha256"] == owner_body.get("render_sha256")))
    )
    if (pack_id != project.get("packId") or wire != manifest or renders["text"]["content"].encode() != project_text
            or _sha(project_text) != project.get("textSha256") or owner_id != owner_body.get("artifact_id")
            or not owner_valid
            or combined.decode("utf-8") != (
                f"# Context loadout {loadout['loadoutId']} v{loadout['version']}\n\n"
                + project_text.decode("utf-8") + "\n\n" + owner_text)
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
    if old.get("schemaVersion") == SOURCE_ONLY_SCHEMA_VERSION or current.get("schemaVersion") == SOURCE_ONLY_SCHEMA_VERSION:
        old_source_id = old.get("sourceArtifact", {}).get("packId", old["contextPack"]["packId"])
        current_source_id = current.get("sourceArtifact", {}).get("packId", current["contextPack"]["packId"])
        owners_changed = (old.get("sourceArtifact") is None) != (current.get("sourceArtifact") is None)
        owners_changed = owners_changed or old_source_id != current_source_id
        return {"schemaVersion": max(old.get("schemaVersion", SCHEMA_VERSION), current.get("schemaVersion", SCHEMA_VERSION)),
                "artifactId": artifact_id,
                "comparedTo": {"loadoutId": current["loadout"]["loadoutId"],
                               "version": current["loadout"]["version"], "digest": current["loadout"]["digest"]},
                "changed": not same_spec or project_changed or owners_changed,
                "changes": {"spec": not same_spec, "projectPack": project_changed,
                            "ownerPacket": owners_changed,
                            "revision": old_loadout["version"] != current["loadout"]["version"]},
                "before": {"version": old_loadout["version"], "digest": old_loadout["digest"],
                           "packId": old["contextPack"]["packId"], "textSha256": old["textSha256"], **before},
                "after": {"version": current["loadout"]["version"], "digest": current["loadout"]["digest"],
                          "packId": current["contextPack"]["packId"], "textSha256": current["textSha256"], **after},
                "state": "comparison_only"}
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
