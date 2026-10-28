# Choose AI-engineering equipment

Browse the catalog, then choose a profile whose AI-engineering purpose, host environment and evidence match your task. Ordinary work starts with the project's instructions and native tools. A selection preserves an option and its reason. Delivery previews the current Context source and locks exact resource versions when applied; direct upstream options retain their declared pins.

Run from the Context source with Python 3.10+ and the pinned source environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python scripts/context_ai.py catalog
.venv/bin/python scripts/context_ai.py profiles
.venv/bin/python scripts/context_ai.py select labs
```

The [portal](../examples/web/index.html) shows equipment, loadouts and scoped trial evidence. [Catalog YAML](../library/catalog.yaml) holds options and assessments; [profiles](../library/profiles) retain compatible example selections, historical snapshots and recipe policies. Five examples have no project/runtime binding; `simulation` is unchanged. Legacy selections and policy allowlists remain for existing callers, not as evidence of current personal authorization. A custom consumer owns its current setup and private effective selection; the committed examples do not synchronize that state. See [consumer ownership](adoption.md#reusable-library-and-custom-consumers). The original loadout families, concepts, upstream notices, task packets and direct reads remain available. A task packet resolves one task's guidance; a library profile captures a recurring AI-engineering setup. Neither runs an agent.

Signals owns general project opportunities, interests and feedback. The [verified transfer](project-suggestions.md) retains all 13 original records and their absence of original IDs or saved annotation fields. `suggestions` remains a read-only compatibility response with `status: moved`, the Signals destination and recovery references; it emits no active opportunity list. Existing schema-v1 profiles may retain the deprecated optional `suggestions` field in history, but current profile and catalog views expose AI-engineering configuration only.

## Deliver a selection safely

Choose a disposable or authorized consumer. `--profile` names a catalog profile by ID or its YAML filename; it does not import arbitrary configuration from that argument. These commands use the same pins, preview, edit protection, recovery and undo as explicit loadouts:

```sh
.venv/bin/python scripts/context_ai.py plan --profile home-lab --project /absolute/consumer --provider both
.venv/bin/python scripts/context_ai.py apply --profile home-lab --project /absolute/consumer --provider both
.venv/bin/python scripts/context_ai.py verify --project /absolute/consumer
.venv/bin/python scripts/context_ai.py refresh --profile home-lab --project /absolute/consumer
.venv/bin/python scripts/context_ai.py export --project /absolute/consumer
.venv/bin/python scripts/context_ai.py undo --project /absolute/consumer
```

Inspect the plan before apply. Refresh previews; apply commits the selected update. Verify checks bytes and runtime probes, and reports project checks as not run. For an existing installation, `refresh` without a profile preserves its exact installed selections. Portable locks remain independently usable without Signals or live Context research. `recover` handles interrupted writes; `rebind` explicitly accepts a moved consumer. Undo retains unmanaged instructions and edited managed files. A managed instruction block itself must remain intact until removal; conflicting changes fail visibly.

Codex and Claude receive thin routers to one pinned resource copy. New or changed project instructions may require a fresh host session. Where native skill discovery has not refreshed, explicitly read the selected procedure before its relevant action. No current chat/tool interception or model change is inferred from installed files. Shell output recipes do not cover native Read/Grep automatically.

Direct upstream options, including a whole ECC harness, retain their own installation boundary. Context never silently executes that installer or delivers a duplicate copied skill. Inspect its selected revision, dependencies and scope, then follow its own installer under project authority.

## Deliver from your own profile file

`--library-profile FILE` resolves recurring selections from one caller-owned schema-v1 profile file (the [library profile schema](../schemas/library-profile.schema.json)) without adding it to Context's committed examples:

```sh
.venv/bin/python scripts/context_ai.py select --library-profile /absolute/my-profile.yaml
.venv/bin/python scripts/context_ai.py plan --library-profile /absolute/my-profile.yaml --project /absolute/consumer --provider both
.venv/bin/python scripts/context_ai.py apply --library-profile /absolute/my-profile.yaml --project /absolute/consumer --provider both
.venv/bin/python scripts/context_ai.py refresh --library-profile /absolute/my-profile.yaml --project /absolute/consumer
```

The four entry points differ in what they read:

| Entry point | Reads | Does |
| --- | --- | --- |
| `--profile` | A committed catalog profile selected by the basename of its argument | Legacy delivery of the six public examples, with optional `--state` effective selections. Unchanged. |
| `--library-profile FILE` | That exact absolute regular file, whatever its name | Preview or explicitly authorized delivery of its selections. |
| `packet --profile FILE` | A task profile | An advisory one-task packet; installs nothing. |
| `--with CAPABILITY` | Registered resources | Delivers resources, with no recurring selection or reason record. |

The file's own `id` is its identity, never its filename, and it need not match any committed profile; the same basename as a committed example selects only what the file declares. Reading uses the existing bounded safe YAML reader and schema, then the normal catalog checks: every option must exist, its concern must match, and no concern may have two owners. Failures are reported before any consumer or state write. The same selection delivers exactly the resources that the equivalent explicit `--with` selection would, through the same preview, edit protection, recovery and undo. `select` output carries an `origin` record (path and SHA-256 of the file) so the source of a selection is visible.

Limits:

- Only `select`, `plan`, `apply` and `refresh` accept the flag. It is refused with `--profile`, positional selections, `--lock`, `--with`, `--option`, `--brand`, `--design-procedure` and `--state`, and with every other command including `verify`, `export`, `undo`, `trial`, `evolve`, `decide`, `catalog`, `profiles`, `packet` and `handoff`.
- The file is only read; Context never writes to it. Its declared `policy` and `snapshot` are preserved data, not permission: no trial, update, scheduling or installer is executed or authorized by them, and no state events apply to it.
- An option delivered by direct upstream can be previewed, but `apply` refuses it as before; use its own native installer.
- An applied consumer stays pinned to its exact installed lock. Editing the file changes nothing installed; run a new `plan`, then a separately authorized `apply`. `refresh` with the flag only previews. `verify`, `export` and `undo` use the installed lock, not the file, and roll back through the native lifecycle.

This closes external recurring selection and delivery only. The six public profile examples still own the committed standing policy and snapshot identity, and private history and policy seeded by those records have not moved; full policy/history extraction remains incomplete.

## Compare and equip a code review

`select` output includes a `comparison` for each chosen concern. It lists every catalog option for that concern with its purpose, status, limits and scoped evidence, and labels each assessment as source-supported or locally tested. It describes fit; it never chooses for you. The `code-review` concern offers two options. `matt-pocock-code-review` delivers the pinned upstream code-review skill through a thin [adapter](../procedures/code-review.md); it runs the axes sequentially by default and needs no tracker setup or sub-agents. `context-review` is the owned [consequential-change review](../procedures/review.md) with a complexity axis and caller tracing. The synthetic [review-equipment profile](../examples/library-profiles/review-equipment.yaml) pairs the focused review with the owned `context-tdd` regression loop:

```sh
.venv/bin/python scripts/context_ai.py select --library-profile "$PWD/examples/library-profiles/review-equipment.yaml"
.venv/bin/python scripts/context_ai.py plan --library-profile "$PWD/examples/library-profiles/review-equipment.yaml" --project /absolute/consumer --provider both
```

The plan lists the exact pinned resource hashes, the upstream pin, its license and the `context-code-review`/`context-tdd` routers before anything is written. Installation, native discovery, an actual read and a useful review are separate observations; no native review usefulness is established for either option yet.

## Use a controlled trial

Trial planning is read-only. Execution accepts a registered recipe, an empty disposable directory and its reviewed isolation boundary. Arbitrary candidate commands are never accepted.

```sh
.venv/bin/python scripts/context_ai.py trial output-helper --destination /absolute/new-trial
.venv/bin/python scripts/context_ai.py trial output-helper --destination /absolute/new-trial --execute
.venv/bin/python scripts/context_ai.py trial tdd-consumer --destination /absolute/new-tdd-trial --execute
```

For the optional executable preservation stress profile, acquire only the inspected wheel set first, then use the normal CLI:

```sh
.venv/bin/python scripts/context_trial_wheels.py --cache /absolute/owned/trial-wheels
.venv/bin/python scripts/context_ai.py trial hypothesis-undo --destination /absolute/new-preservation-trial --wheel-cache /absolute/owned/trial-wheels
.venv/bin/python scripts/context_ai.py trial hypothesis-undo --destination /absolute/new-preservation-trial --wheel-cache /absolute/owned/trial-wheels --execute
```

This pin currently supports macOS CPython 3.12 x86_64. Missing wheels or unsupported execution remain visible as blocked; acquisition never runs candidate code. The exact dependency and license review is in [the trial record](hypothesis-trial.md). It adds no normal runtime dependency.

The macOS backend denies personal HOME, external reads/writes and network, then tests those denials before execution. Missing or failed isolation produces a retained blocked result. The output recipe runs a real executable against controlled failures. The TDD recipe is a deterministic consumer fixture tied to pinned guidance; it does not establish that the guide itself ran or helped a human. Trial records retain commands, versions, resource hashes, failures and timing. API charges and served model identity stay unknown when not supplied.

## Follow relevant evidence

[Interests](../library/interests.yaml) connect unresolved AI-engineering choices to profiles and concepts. Due queries guide native host research; they do not turn every concept into a research job. Signals v1 evidence is admitted with exact bytes, producer identity and commit; native primary-source research remains available without Signals.

The original general-interest IDs remain readable with moved markers and [frozen source records](../history/general-interests-3d77344.yaml). They produce no due research or trials in Context. Existing retained intake events and assessments remain available; a new intake against one of those IDs returns the owner and history reference. The active `project-equipment` scope covers concrete AI-engineering choices.

```sh
.venv/bin/python scripts/context_ai.py evolve --state /absolute/private-library
.venv/bin/python scripts/context_ai.py evolve --state /absolute/private-library --input /absolute/evidence.json --sha256 EXACT_SHA256 --producer pradeeptathineni/signals-ai --commit FULL_COMMIT --interest project-equipment
.venv/bin/python scripts/context_ai.py pause --state /absolute/private-library
.venv/bin/python scripts/context_ai.py resume --state /absolute/private-library
```

A new observation creates scoped inspection/trial proposals. Each activation permits at most two trusted trial attempts; later finite passes resume eligible deferred work. `--execute` runs only a known recipe explicitly allowed by the profile's trial policy. Unchanged bytes skip completed work; an explicit execution pass retries only when the trusted recipe, runtime or reviewed preparation changes. a re-fetch with unchanged claims/candidates/source revisions skips trials too. Failed or missing sources preserve current selections. Semantic assessment belongs to the host reader and is recorded through `assess --input ASSESSMENT.yaml --state PRIVATE_DIR`; its local artifact hashes are verified and copies retained. Catalog changes are reviewed edits to the canonical YAML; no web content can write policy.

`decide PROFILE OPTION --sha256 INTAKE_DIGEST --state PRIVATE_DIR` requires non-fixture retained intake and an option in that profile's allowed-update policy. It changes the effective future selection, replacing its concern owner. Installed consumers remain pinned until a separate delivery preview/apply. No public release, billing, global settings or production timer follows from a decision.

Deep may also request a Context-owned equipment review using the exact retained
Sandbox trial-pair reference and an explicit project criterion. The owner checks
the current profile, allowed update, selected baseline/candidate identities,
single declared `identity.equipment` treatment, completed comparable pair and
declared Context compatibility. The selected criterion must be frozen in the
Sandbox plan and record candidate `pass` against baseline `fail`; a structural
pair without that exact result remains `insufficient_evidence`. Insufficient
or changed evidence cannot be accepted. A successful preview only makes the
exact candidate eligible for human review; it does not infer general benefit
or superiority, and the user's project criterion remains separate from the
Sandbox criterion. Separate explicit
acceptance appends an immutable event to the existing private profile state and
changes future profile selection only. The event preserves the Sandbox ID and
digest, predecessor profile digest, criterion, human reason and compatibility
qualification. It does not install, activate or send anything. Deep rereads the
canonical Sandbox packet and current Context owner before preview, acceptance
and cold reopening; unknown measurements remain unknown.

Private state holds immutable numbered events, exact admitted bundles and assessment artifacts. Catalog exports include that state only when `--state` is explicitly provided. The public portal reads approved committed library data. Scheduling uses the native host configuration in [the maintenance example](../examples/library-maintenance.yaml); production recurrence remains disabled until explicitly configured.
