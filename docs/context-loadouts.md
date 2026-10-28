# Versioned task context loadouts

`scripts/context_loadout.py` composes an existing source-verified Context pack
preview with either caller-supplied Research and Planning records or one typed
Custom preference-profile export. It owns reusable selection revisions and
immutable composed snapshots. It never reads Research, Planning, or Custom
owner stores, sends content to a host, or
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

The additive `context-loadout/v2` spec with `variant: "source-pack-only"` freezes an exact Context preview without Research, Planning or Custom input. V1 schemas, digest bytes, artifacts and cold-reader behavior remain unchanged. The source-only artifact records the Context project ID, preview ID, project revision, exact Context manifest and text/JSON renders, and each selected source file hash. `inspect`, `compare` and `freeze` re-export through the canonical Context pack service and refuse source drift; `read` verifies retained bytes and hashes without reopening project files. Both variants use the same UTF-8 bytes divided by four estimate and explicit budget. See [context-loadout-v2.schema.json](../schemas/context-loadout-v2.schema.json).

The additive `context-loadout/v4` spec with `variant: "research-citation"`
retains one exact Research citation binding and the bounded canonical owner read
that contains its quote, source locator, matching answer paragraphs, status,
coverage and qualifications. It does not expand the selection to the whole Study
answer. The native Context engine validates and preserves this closed projection;
the integrating host remains responsible for rereading Research before review,
freeze and send verification. A frozen v4 artifact remains `not_sent`, and the
native cold reader verifies the exact retained bytes without claiming that a
quote proves entailment, truth, currentness or completeness. The existing v1,
v2 and v3 readers remain unchanged. The v4 spec includes `task`,
`contextPreviewId`, `maxTokens`, an empty `reductionRequests` list, and
`researchCitation: {reference, peek}`. `reference` uses
`deep.research-study-citation-binding.v1`; `peek` must be the complete, closed
`deep.research-study-citation-peek.v1` projection returned by Research's
citation read tool. The host binds the artifact to the active conversation in
its own durable association. Selection, installation and sending remain
separate host actions.

The additive `context-loadout/v5` spec with `variant: "principle-decision"`
retains one exact Principles contextual-decision version and the owner `decision.read`
result. Context validates the version digest and owner-reported currentness, then
renders the complete human-authored applicability, exceptions, assumptions,
tradeoffs, judgment and qualifications without interpreting them. The integrating
host rereads the same decision before review, freeze and send verification; changed,
missing or unknown currentness blocks those steps. Frozen v5 artifacts remain
`not_sent`; cold reads verify the historical bytes without transferring approval or
activation. The existing v1-v4 readers remain unchanged.

```json
{
  "schemaVersion": 2,
  "variant": "source-pack-only",
  "task": "fix billing total",
  "contextPreviewId": "<32-hex Context preview ID>",
  "maxTokens": 3000
}
```

The CLI operations are identical to v1: `create`, `revise`, `inspect`, `compare`, `freeze`, and `read`. The source-only branch carries an explicit Context-owned source artifact; it does not synthesize linked Research/Planning or preference records. Freezing reports `not_sent`; only the integrating host can verify and send it.

The input names an already frozen Context preview and preserves the exact
caller-supplied Research and Planning records:

```json
{
  "schemaVersion": 1,
  "task": "change billing total",
  "contextPreviewId": "<32-hex Context preview ID>",
  "maxTokens": 3000,
  "reductionRequests": [{"itemId": "<selected full-source item ID>", "maxLines": 12,
                         "protectedLines": [17, 18]}],
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
(100–8192), exactly one of `ownerPacket` or `preferenceProfile`, and optional `reductionRequests` (up to eight
`{itemId, maxLines, protectedLines?}` entries with an 8–100 line cap. `protectedLines` is an explicit list
of 1-based physical source line numbers, bounded to 100; out-of-range lines fail and a protected selection
that exceeds the cap blocks reduction. Exact full-source bytes and the complete kept/omitted segment map
remain bound to the frozen source identity and digest. The owner packet is the existing linked-context
v1 shape with one Research answer and one Planning intent; its task must match.
The linked-context producer also accepts schema v2 Mission-result packets, but
loadout v1 deliberately accepts only the Research/Planning pair. Any non-empty
`maestro_results` list is rejected as `invalid_request`, never silently dropped.
The alternative `preferenceProfile` is the closed
`custom.preference-profile-export.v1` record, including its owner revision,
profile lineage, expiry, preferences, conflict notes, exact rendered text hash,
and export receipt. It is not a native setting. Its text is labeled as lower
priority than current system, developer, user, project instructions and access
policy. The loadout owner validates and preserves the typed record but does not
reopen the Custom store; the integrating host must reverify that source before
load and again before send. Frozen historical artifacts remain readable after
the profile expires, but they cannot be newly assembled or verified for send.
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
and cap-dropped reasons. A caller may explicitly protect up to 100 1-based
physical source lines for each selected full-source item. Their exact contents
must fit the line cap or reduction is blocked; selected line numbers and source
identity are retained in the frozen preview. This is caller-directed scope,
not automatic task relevance scoring or evidence-quality assessment. Reduction
previews remain separate inspection aids; the reducer does not replace or
silently edit the frozen Context pack. The token count uses the existing
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
