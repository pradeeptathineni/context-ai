# Project loadouts

For one task, start with project instructions and read only relevant guidance directly. No installation is required. For a recurring project selection, a manifest selects resources and a resolved lock pins their bytes. Report actual use and checks separately in the task result; a structured use receipt is optional unless the project requires one. Project instructions and explicit user authority take precedence.

## Supported catalogue

| ID | Use | Verification recipe |
| --- | --- | --- |
| standard | Proportional inspect/implement/test/review/deliver; existing tools and prior art | Project tests, actual diff, truthful completion |
| context-authoring | Compression, authority, coherence, provenance and refresh | Metadata/links/schema, retained requirements, compatibility |
| research-evidence | Primary evidence, comparative options, freshness, Signals exchange | Exact bytes, provenance, citations, honest mode and constraints |
| web-experience | Selected instruction-only design, UX/content, accessibility and browser critique | Static build, screenshots, interactions, axe, asset budget/reduced motion |
| react-web | React rules matched to actual framework; composes web-experience | Real version/client-server/static-export detection and browser checks |
| service-api | API trust/contracts, persistence/failure behavior, existing stack | Real route/type/schema tests and isolated database/migration checks |
| aws-infrastructure | Existing Terraform/AWS identity/state/hosting constraints | Safe source inspection, format/isolated validation, authorized plan/rollback |
| release-review | Final review, compatibility, immutable release and destination | Clean checkout/package, remote SHA/CI then tag/release verification |

Each has a real disposable materialization test in `tests/test_loadouts.py`. The complete development suite exercises all eight and needs Node 20+ even for a documentation-only library change; individual consumer selections use only their declared prerequisites. The actual library used standard + context-authoring; research-evidence guides source/adoption stages; release-review guides publication. The browser exercise in `examples/web/` uses standard + web-experience. These tested compositions do not imply every possible cross-product or production stack is tested.

## Commands

Run the CLI from the Context source directory with Python 3.10+. Its dependencies stay in that source-local environment. Ruby is needed for Context development validation, not consumer installation. Run task checks from the consumer directory. No global install or inference call is needed:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python scripts/context_ai.py list
.venv/bin/python scripts/context_ai.py decisions
.venv/bin/python scripts/context_ai.py tools --project /absolute/project
.venv/bin/python scripts/context_ai.py explain standard --option review_mode=fresh
.venv/bin/python scripts/context_ai.py explain react-web --design-procedure lightweight
.venv/bin/python scripts/context_ai.py plan standard react-web --project /absolute/project --provider codex --brand "Warm paper, restrained ink, existing typography" --design-procedure lightweight
.venv/bin/python scripts/context_ai.py apply standard react-web --project /absolute/project --provider codex --brand "Warm paper, restrained ink, existing typography" --design-procedure lightweight
.venv/bin/python scripts/context_ai.py verify --project /absolute/project
.venv/bin/python scripts/context_ai.py refresh --project /absolute/project
.venv/bin/python scripts/context_ai.py undo --project /absolute/project
```

`explain` resolves the same ordered parents, stage routes, bounded options and decisions as `plan`, without writing or checking local tool availability. Its capabilities are declarations, not availability claims. `decisions` derives all current choices from the existing resolver; `decisions LOADOUT` narrows them to that composition. Historical predecessors are excluded from both views.

`plan` prints a resolution, write inventory, owned-file removal inventory and resource diff on stdout without changing the project. Read it before application. `apply` copies only the selected resources and their explicit runtime/notice dependencies into `.context-ai/resources/`, installs selected skill routers in `.agents/skills/`, and appends one owned block to root AGENTS.md. It preflights all paths and refuses unowned existing targets or edited/missing managed files. It never changes global configuration or executes check recipes. Reapplication of an identical resolution is stable; applying a new pin is a separate explicit checkpoint action.

`verify` checks resource pins, ownership and routing, then actually runs reviewed bounded Python/Git/Node version probes at their discovered locations when required. `observed_versions` and local `capability_discovery` report those observations separately from integrity and project checks. Unknown command probes fail rather than execute manifest-supplied expressions. Optional capability discovery can be incomplete: a CLI-presence check is not proof that a project has a compatible runtime/browser/database. The JSON explicitly reports `project_checks: "not_run"`, lists suggested checks, names the required version probes actually executed and reports unavailable optional capabilities with their boundaries. The agent must run the relevant project recipe and report its result. `refresh` proposes a lock/file diff, preserves options when reusing the installed selection, and never activates it. It compares local reviewed library bytes; it does not fetch upstream or run Signals research. Refresh only sources/evidence that can change a decision. Append a successor for a material choice, then inspect/apply the proposal.

`undo` removes unchanged owned files and the unchanged routing block. It preserves edited files/blocks and reports conflicts, retaining an undo-pending receipt. Resolve those conflicts before reapplying. Export a portable resolution for another machine with `export --project /absolute/project > selection.json`. Apply it against the matching source checkout with `apply --lock /absolute/selection.json --project /absolute/clone`. Keep the machine-bound installation receipt local; do not publish its absolute path. For an unchanged copied legacy installation, `rebind --project /absolute/clone` verifies its bytes/routing before changing ownership; edited copies safely refuse. Empty directories may remain after undo. Application preflights all paths and records recovery bytes before atomic individual writes. In-process failures roll back. After interruption, `recover --project /absolute/project` restores unchanged transaction writes; post-interruption user edits are reported and retained. Ownership commands refuse while recovery is pending. This is recoverable application, not a multi-file atomic filesystem transaction or a defense against concurrent hostile writers.

## Public contracts

Loadout YAML has `id`, description/characteristics, ordered composition/modules/skills, required/optional capabilities, options, stage routing, check recipes and decision references. `schemas/loadout.schema.json` owns its fields. Composition is depth-first parents then selection, deduplicated by ID; cycles and conflicting defaults fail. An option key in a loadout makes it applicable; `null` selects the registry default. Existing explicit values remain valid.

`capabilities.yaml` and `schemas/capabilities.schema.json` own the small option vocabulary. Finite alternatives have a default, applicability description, aliases to existing capability definitions and optional explicit incompatible option/value pairs. Brand is bounded project intent (1-2000 characters). Code validates explicit supported values and aliases; it makes no model call or keyword-based task choice. `explain` shows `option_choices`; the agent uses task/project facts to choose. Aliases replace selected definitions from the base registry, so only selected resources/notices enter the closure. Informational links do not pull in another alternative.

| Option | Default and alternatives | Behavior |
| --- | --- | --- |
| `design_procedure` | `guided`, `lightweight` | Guided selects pinned Impeccable for substantial design; lightweight selects pinned Anthropic for a bounded existing surface. Same browser/accessibility floor. |
| `review_mode` (standard) | `direct`, `fresh` | Direct selects artifact review; fresh adds the bounded-reader procedure and existing orchestration guidance. Host support and authority must be established by the agent; instructions cannot supply them. |

Use `--option KEY=VALUE` repeatedly for explicit choices. `--design-procedure` and `--brand` remain compatibility flags with identical meaning; conflicting duplicate flags fail. Unknown, inapplicable, conflicting aliases and declared incompatible pairs fail usefully. Refresh preserves applicable explicit choices, and changing a selection drops inapplicable inherited options. No automatic recommendation overrides the pin or silently substitutes a lower-quality fallback.

Schema-2 resolutions use `project: .` for portability. Schema-2 installation receipts own the local `bound_project`; current tooling verifies and migrates schema-1 receipts explicitly. A lock has its own schema and pins resource SHA-256s, library revision/tree digest, selected loadouts, stage routing, options, capability definitions/states, checks and current decision revisions. Source tree hashing excludes the lock itself. An installation receipt additionally records owned file hashes and the exact root routing block. Schemas reject unknown fields except explicitly defined optional recovery metadata. YAML safe parsing rejects duplicate/non-string keys, aliases and object tags. Approved relative paths cannot traverse or follow symlinks. `resources.yaml` declares file prerequisites. Markdown links are informational and never expand closure; directories, escapes, cycles and active instruction filenames fail. Selected upstream bytes and required notices are checked against `sources.lock.json`. Unselected upstream files cannot block unrelated work. Manifests have no executable expressions or installer authority.

Decisions append revisions with a predecessor for material changes; `current_decisions()` derives the current view and expands explicitly shared record defaults. `decisions` and `explain` expose the resolved records, including applicability, alternatives, evidence, uncertainty and validation. Decision records use current concept IDs and cite accountable modules or original sources. Exact older source commits retain the earlier labels for pinned reproduction. Old exported pins continue to resolve with their original source bytes. `sources.lock.json` owns upstream revision/license/file hashes; snapshots remain inactive, with instruction filenames renamed. Selected resources include licence/notice dependencies. Decisions are pinned in the lock; the full decision/catalog/source trees remain available in the source checkout, rather than copied into every composition. The external `standard` skill is preserved; no new skill uses that discovery name. Generated skill descriptions use the actual selected procedure triggers; unowned same-name project metadata is refused even under a different folder name.

## Project-local discovery

`tools --project /absolute/project` works without installation; `plan`/`refresh` include the selected `capability_discovery` report. Inspection reads bounded manifests as data, with no scripts, configuration imports, package-manager downloads, browser launch, network or consumer writes. It reports command locations, declared manager/lockfile candidates, script recipes and installed Playwright package metadata. `exercised: false` remains until an explicit probe/check; the historical lock `available` boolean means a resource/command candidate exists, never runnable project behavior.

Node inspection respects `packageManager` (npm/pnpm/yarn/bun), existing lockfiles and a nearest ancestor explicitly declaring the member in `workspaces` or `pnpm-workspace.yaml`. Workspace globs match path segments (`*`, `?`, `[]`, `**` and leading `!` exclusions); braces/extglobs and unsafe paths are rejected with an explicit boundary. `packages/*` cannot admit a nested nonmember. Hoisted/local package symlinks may resolve within that workspace, including pnpm's store there. Escapes fail with an actionable boundary. Conflicting managers, Yarn PnP, external stores and nondeclared workspace arrangements require explicit project inspection; no npm fallback or network resolution is guessed. Playwright's manifest/CLI and version are distinct from installed browser binaries and successful launch. Actual browser/project checks belong to the host agent after inspecting side effects.

Python discovery uses an in-project `.venv` with `pyvenv.cfg`; its final interpreter symlink may point to a managed system runtime. Symlinked environment/bin directories are rejected explicitly. A Python project declaration without that environment reports the gap instead of substituting Context's interpreter. PATH Python is used only without a declared project environment. Custom environments require an explicit project choice outside this bounded resolver. Version probes do not establish dependencies or project correctness.

Absolute observations stay in local reports, never portable pins. Native host browser/subagent availability is reported by the host separately from PATH and verified through supported operations. Writing a router does not prove its metadata was discovered or its instructions were used.

## Evidence, discovery and limits

The supported frozen Signals v1 input is `schemas/evidence-bundle-v1.schema.json`, copied unchanged from the supplied kit. Use `scripts/evidence.py` with an exact-byte digest and pinned producer repository/40-character commit, or legacy `--checkpoint` and `--producer` through `scripts/legacy_evidence.py`. It validates schema and semantic references, public URLs without fetching, modes/privacy, support for adoption advice, empty-result honesty and unknown observation dates. Current `inspect_bundle` / direct CLI output reports `source_age_days` and preserved dates as information, with no universal adoption cutoff. It accepts only the supported `signals-evidence-v1` real producer protocol; incompatible versions fail. `load_bundle`, `--legacy-summary`, and checkpoint transport retain the frozen v1 age-label output for replay. Those legacy labels are not current selection policy. Fixture mode has no public admission flag. Test-only fixture admission is separate. Source IDs existing does not prove support for the claim; hashes prove bytes, not truth or cryptographic producer identity. The trusted local checkpoint boundary supplies identity. Recommendations, unknown extension policies and constraints never activate a capability.

An ordinary task result names the guidance actually read, tools invoked, checks run and outcome. When a comparison or audit needs a structured use receipt, record capability/pin, consumer/stage, read/invoked/validated/not_used, discovery mode, result and command/artifact reference. There is no required per-task receipt schema. Installation is separate. Native discovery in this active desktop session is not inferred from filesystem installation: explicit reads are recorded honestly. Reopen the project in a fresh trusted session for metadata discovery; see the [Codex adapter](../providers/openai/codex.md). An unavailable optional browser does not block unrelated API work, but web acceptance remains incomplete until exercised.

This library equips existing agents. It includes no runtime, independent signal-scoring engine, hosted service, package-registry release, automatic upstream installer, global hooks, paid API connection or deployment side effect. Live Terraform/AWS and backend checks depend on the consuming project's authority and environment. [Compatibility and migration](compatibility.md) explains preserved paths and identifiers.

## Pre-1 publication

The validator rejects a stable `release_version` and stable tag refs in `GITHUB_REF`; CI runs it on pushes and pull requests. There is no automatic publisher. Before a manual 0.x tag/release, require the intended remote commit and successful repository/web checks, then create a new annotated tag. The withdrawn `v1.0.0` name stays reserved; stable publication needs a separate future user decision.
