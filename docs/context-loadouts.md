# Versioned task context loadouts

`scripts/context_loadout.py` composes an existing source-verified Context pack
preview with caller-supplied Research and Planning records. It owns reusable
selection revisions and immutable composed snapshots. It never reads Research
or Planning owner stores, validates their claims, sends content to a host, or
records provider acknowledgement. Owner records remain explicitly
`caller_validated_data`; callers must preserve their real owner identity and
qualification instead of inventing verification.

The versioned Python API is:

```python
create(store, loadout_id, spec)
revise(store, loadout_id, expected_version=1, expected_digest=DIGEST, spec=NEW_SPEC)
inspect(store, loadout_id, version=1, digest=DIGEST, service=context_pack_service)
compare(store, loadout_id, artifact_id, version=2, digest=NEW_DIGEST,
        service=context_pack_service)
freeze(store, loadout_id, version=2, digest=NEW_DIGEST,
       service=context_pack_service)
read(store, artifact_id)
```

The input names an already frozen Context preview and preserves the exact
caller-supplied Research and Planning records:

```json
{
  "schemaVersion": 1,
  "task": "change billing total",
  "contextPreviewId": "<32-hex Context preview ID>",
  "maxTokens": 3000,
  "reductionRequests": [{"itemId": "<selected full-source item ID>", "maxLines": 12}],
  "ownerPacket": {
    "task": "change billing total",
    "records": [
      {"kind":"research_answer","owner":"research","record_id":"answer-7","revision":"r4","digest":"sha256:<64 lowercase hex>","title":"Finding","text":"Caller-supplied answer text","qualification":"actual Research qualification"},
      {"kind":"planning_intent","owner":"planning","record_id":"intent-3","revision":"p2","digest":"sha256:<64 lowercase hex>","title":"Intent","text":"Caller-supplied plan text","qualification":"actual Planning qualification"}
    ]
  }
}
```

`spec` has `schemaVersion: 1`, `task`, `contextPreviewId`, `maxTokens`
(100–8192), `ownerPacket`, and optional `reductionRequests` (up to eight
`{itemId, maxLines}` entries with an 8–100 line cap). The owner packet is the existing linked-context
v1 shape with one Research answer and one Planning intent; its task must match.
The closed input schema is [context-loadout-v1.schema.json](../schemas/context-loadout-v1.schema.json).
Research and Planning IDs, revisions, digests, and qualifications are retained
as caller claims. Project files and selected Context guidance are bound by the
named Context preview and are reread by `ContextPackService.export` on every
inspect, compare, and freeze. The loadout store is separate from project,
Context, and Context-pack stores.

Create writes immutable version 1. Revise appends a new version only when the
caller supplies the current version and digest. A conflict requires rereading
the current revision. Inspect returns the exact Context JSON/text render, its
included item IDs and omission reasons, the linked Research/Planning render,
any requested deterministic reduction previews, and the combined byte/token
estimate. Reduction previews retain exact source spans and their kept, omitted,
and cap-dropped reasons. They remain separate inspection aids; the reducer does
not replace or silently edit the frozen Context pack. The token count uses the existing
`ceil(UTF-8 bytes / 4)` estimate, not a provider tokenizer. The combined
render must fit the declared budget; nothing is silently clipped. Adjust the
Context preview or loadout explicitly if it does not fit.

Freeze stores the selected revision, exact nested manifests, all rendered
content, and hashes in an immutable `context-loadout/v1` artifact. `read` is a
cold read and verifies the outer artifact digest, Context pack serialization,
linked-owner serialization, and exact rendered bytes without consulting source
owners. A later source change makes inspect/compare/freeze against the old
preview fail with `source_drift`; create a new Context preview and append a
loadout revision to compare that candidate. `compare` is read-only and reports
the before/after pack IDs, included/omitted refs, content digests, and which
inputs changed. It never retargets a snapshot or changes the reusable loadout.

The returned states distinguish `referenced`, `assembled`, and `frozen`;
delivery is explicitly `not_sent`. No `sent` or `acknowledged` receipt exists.
The native host owns actual sending and acknowledgement.

The JSON CLI supports `create`, `revise`, `inspect`, `compare`, `freeze`, and
`read`. Every command uses a private local store; inspection commands also
require an explicitly configured project and Context-pack store. Run
`python3 scripts/context_loadout.py --help` for flags. No provider, model,
clipboard, upload, or installation step is involved.

```sh
python3 scripts/context_loadout.py create --store /private/loadouts --loadout-id billing --spec spec.json
python3 scripts/context_loadout.py inspect --store /private/loadouts --loadout-id billing --version 1 --digest DIGEST --project /repo --context-store /private/context-packs
python3 scripts/context_loadout.py freeze --store /private/loadouts --loadout-id billing --version 1 --digest DIGEST --project /repo --context-store /private/context-packs
python3 scripts/context_loadout.py read --store /private/loadouts --artifact-id ARTIFACT_ID
```
