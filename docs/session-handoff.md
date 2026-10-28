# Fresh-session reconstruction

`SessionHandoffService` freezes an operator-selected set of already-opened records into a local package for a fresh native session. It keeps each source intact and separate from the user's concise handoff prose. It does not discover records, read unrelated chats, call an owner or model, launch a session, or deliver the export. Starting a native session and deciding what to do remain separate actions.

## Complete local path

The caller prepares a bounded JSON request from exact Signals `knowledge/record` responses and any other explicitly opened, supported owner records. The input file is an operator-selected file outside the source repositories. The command never accepts a path, URL or command from record content.

```sh
python3 scripts/session_handoff.py \
  --project /absolute/consumer \
  --store /private/context-handoff-store \
  --project-id consumer-instance \
  create /private/handoff-request.json

python3 scripts/session_handoff.py \
  --project /absolute/consumer \
  --store /private/context-handoff-store \
  --project-id consumer-instance \
  preview 53eac3e8-d8d6-4c6f-9d51-2be8ff4b6b0b --format json --max-bytes 32000

python3 scripts/session_handoff.py \
  --project /absolute/consumer \
  --store /private/context-handoff-store \
  --project-id consumer-instance \
  export PREVIEW_ID --format json --output /private/fresh-session.json
```

The output path is create-only, must be outside the configured project and Context trees, and is written with private file mode. To inspect exact saved text, call the explicit `reopen HANDOFF_ID`; `show HANDOFF_ID` returns redacted metadata and source references without the private handoff or record bodies. `revise HANDOFF_ID --expected-revision N --handoff TEXT` appends a user-authored synthesis revision and cannot edit source records. A revision invalidates its previous previews. Reopen, preview, revise and export refuse changed project or selected Context source observations.

## Input contract

The request uses a canonical caller UUID. Each selected owner record includes its exact selection identity, instance and epoch; exact UTF-8 content and content type; owner export time or `null`; caller observation and qualification; user-chosen section; and optional whole-record inclusion choice.

```json
{
  "request_id": "53eac3e8-d8d6-4c6f-9d51-2be8ff4b6b0b",
  "purpose": "Resume the release review using current evidence",
  "handoff": "Recheck the dated recommendation before acting.",
  "guidance_ids": ["guidance:core/testing.md"],
  "records": [{
    "selection": {
      "ref": {
        "owner": "planning-ai",
        "kind": "decision",
        "id": "R-12",
        "revision": "sha256:ada96d5c94596f5b9ff65ddde03cec32b06fe55ef640389f45c8f1ffbf3ec526",
        "digest": "ada96d5c94596f5b9ff65ddde03cec32b06fe55ef640389f45c8f1ffbf3ec526"
      },
      "instance_id": "planning-store-1",
      "owner_epoch": null
    },
    "content_type": "text/markdown",
    "content": "Exact complete source record text",
    "export_as_of": "2026-10-23T10:00:00Z",
    "observation": {"state": "frozen", "reason": "caller snapshot"},
    "qualification": "Dated recommendation; current applicability is unverified.",
    "section": "decision",
    "include": true
  }]
}
```

For every record, `digest` is SHA-256 of the exact UTF-8 content and `revision` is `sha256:<digest>`. Supported owners are `signals-ai`, `planning-ai` (`decision`, `review`, `reflection`), `principles-ai` (`principle`, `study-session`), and the exact Context `context-loadout` artifact. Signals native kinds remain owner-defined; the owner itself and its exact instance/epoch are still validated. Signals records require a nonempty `owner_epoch`; Planning, Principles and Context use `null`. A Context loadout carries a closed owner binding for artifact, loadout/version/digest, rendered text hash, source artifact and producer revision. Deep rereads that exact artifact through the Context owner before native creation; browser text is not accepted. The frozen loadout remains historical data, not a sent receipt, current source check or approval. Duplicate full identities are rejected, while identical record IDs from distinct owner stores remain distinct. Content is bounded at 128 KiB per record and 1 MiB total, with no truncation.

`section` is `decision`, `finding`, `question`, or `work`. Set `include` to `false` and provide `omit_reason` for an explicit whole-record omission. Preview also omits whole records that do not fit its byte cap, and reports the reason. Any omission retains the full source in the private handoff store so a later preview can select it; the exported record contains source digest/length and omission reason, not a clipped excerpt.

The handoff prose and `purpose` are explicitly user-authored. Guidance IDs are resolved through Context's existing active-resource and dependency/notice resolver; selected guidance is copied unchanged with exact source metadata. No automatically chosen guidance or source summary is added.

## Identity, freshness and authority

The private store is bound to configured project and Context root paths, directory device/inode identity, project instance ID, sanitized origin identity digest, branch and upstream, and store path. Credential-bearing remote strings are never persisted or emitted. Handoff snapshots also bind HEAD, index and dirty-status observations and the selected Context guidance closure. These Git observations are non-atomic; any changed observation requires a new handoff and preview.

Owner records are caller-supplied frozen snapshots, not cryptographic owner attestations. The exact source digest, full Signals selection identity, instance, epoch, export-as-of value or `unknown`, caller observation, qualification and chosen section are retained. Context does not reread an owner store, substitute a successor, or claim that its historical state is still live. Text labels historical records as untrusted data, frozen and not live-verified. JSON labels them `historical_data_only` and `frozen_snapshot_unverified_live`.

The reconstruction has a fresh-history marker. It carries no earlier tool/execution state and no task-acceptance flag. Historical decisions, task receipts, instructions, status language and hostile strings remain quoted original data; none becomes current authority, approval, accepted work or proof of completed effects. Current task, newly resolved selected guidance, user-authored synthesis, and historical records occupy separate fields and sections. Prior approvals, installation and sent receipts are never transferred to the new session.

JSON preserves exact complete content for every included record and its full qualifications/provenance. Text fences keep included source content intact. Neither representation summarizes or truncates a source. The complete render must fit the requested byte cap; `estimated_tokens` uses the existing `ceil(UTF-8 bytes/4)` estimate and is not a model-token measurement. Preview renders are immutable and replayed on export; a changed handoff revision, project identity, project observation, selected guidance, stored source digest or render is rejected.

The service uses Context's existing private, bounded, no-follow immutable store and file-mode protections. Records are only read from the explicit request envelope; request and export paths are local CLI arguments with no-follow checks. No browser/HTTP source path, recursive discovery, URL fetching, credential read, provider operation, clipboard action or native session launch exists in this owner CLI.

## API

`SessionHandoffService(project, *, store, context_root=None, project_id="selected-project")` exposes `create(request)`, `show(handoff_id)`, `reopen(handoff_id)`, `revise(handoff_id, *, expected_revision, handoff)`, `preview(handoff_id, *, max_bytes=32000, format="json")` and `export(preview_id, *, format=None)`. `create` returns the UUID, current revision, request-meaning digest, idempotent-reopen flag and staleness indicator without source content. `show` is metadata-only; `reopen` is explicit and returns full saved text after freshness verification.

The standalone CLI takes the same global `--project`, `--store`, `--project-id` and optional `--context-root` settings before its subcommand. This producer is complete offline and synthetic; it does not establish that any native host obeys the exported text or improves task outcomes.
