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

Private state holds immutable numbered events, exact admitted bundles and assessment artifacts. Catalog exports include that state only when `--state` is explicitly provided. The public portal reads approved committed library data. Scheduling uses the native host configuration in [the maintenance example](../examples/library-maintenance.yaml); production recurrence remains disabled until explicitly configured.
