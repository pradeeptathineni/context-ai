# Compatibility and migration

Pre-1 library releases and integer schema versions have separate meanings. Loadout, evidence and model routing use schema 1; resolution/installation and concepts use schema 2. Changes to their documented fields or semantics require compatibility review; published tags are immutable.

Catalog schema 2 unifies definitions, scope, aliases, modules and coverage with shared defaults. The Ruby lookup supports both catalog shapes; `scripts/concepts.py definitions` emits a string map for older direct consumers. Existing schema-1 pins remain reproducible from exact source commits. Current decisions use catalog concept IDs directly. Exact old source commits retain earlier labels and remain reproducible.

The generated `concept-needs` handoff is now schema 2: it contains curated question groups with exact concept, source, claim and current-decision bindings. The schema-1 all-catalog handoff is available from its source commit; `coverage` and `options` remain separate CLI views.

House policies live in `overlays/`. The pre-1 `custom/` routers were removed because no loadout selected them; exact old source commits retain the old paths. Read a task-relevant overlay directly or use loadouts for a recurring project selection.

Codex is the current supported materialization adapter. Its project-local skill routers use unique context-prefixed names; the existing standard discovery name is untouched. Instruction-only upstream adaptations declare omitted binaries/hooks and preserve pinned documentation/notice files. A project can continue a stage on its earlier lock while the library advances; review a refresh at a checkpoint before changing the active pin.

Exact snapshots remain available in Git commits and exported release/checkpoint archives. Materialization does not retrieve an old revision automatically: use the exact checkout/archive to reproduce that pin. New `git archive COMMIT` exports expand the tracked `REVISION` marker using Git `export-subst`; checkout copies, tree-only archives and older archives may lack a concrete marker. The resolver uses Git only when the source itself is the repository root, then a concrete archive marker, otherwise `exported-tree` plus resource hashes. A consumer repository surrounding an export cannot supply the library commit. A marker records provenance; resource hashes still establish selected bytes. Use the commit or archive digest as the source identity; no stable designation is implied.

## Portable ownership

Resolution/installation schema 2 separates a relative project declaration from local `bound_project`. Existing schema-1 receipts still verify in their original directory. Copied legacy receipts refuse until `rebind` verifies every owned byte, routing block and required command, then changes only the binding. Edits cause refusal; no hand-editing or falsified ownership is required. `export` emits a portable pin; `apply --lock` verifies its resources against the selected source checkout. An active refresh remains a proposal. `recover` uses a local write journal to restore interrupted application while retaining later edits. Keep installation receipts and recovery records local.

## Current decision and CLI views

`decisions` expands shared defaults and selects the latest revision of each record; predecessors remain available for provenance and exact pins. `decisions LOADOUT` and `explain LOADOUT` limit the view to the resolved composition. Current records use catalog concept IDs. Old installed locks contain their original resolved records and still verify without consulting the current registry.

`explain` now includes inherited selections, effective options, stage routes and check recipes. Capability definitions retain their existing shape; `capability_requirements` states required/optional declarations without implying availability. `verify` retains `verified` and `owned_files`, and adds its installation scope, executed runtime probes, missing optional boundaries, suggested checks and `project_checks: "not_run"`. These additive command outputs do not change lock or installation schema 2. A structured per-task use receipt is optional; project-specific reporting contracts still apply.


## Task options and evidence inspection

`packet --profile FILE --project DIR` adds a read-only schema-1 task profile contract in `schemas/task-profile.schema.json`. Existing command meanings, loadout schema 1 and lock/installation schema 2 remain unchanged. Resource capability definitions can include optional `stages` hints used only for packet slicing; omitted hints apply to all selected stages. New materializations pin the updated definitions; old locks retain their original bytes and behavior. No existing installation is refreshed automatically. Packets report missing required tool candidates as unresolved advice; `plan`/`apply` continue to require their presence. Explicit profile choices and packet advice never override user/project instructions or authorize execution.

`--option KEY=VALUE` extends the existing option boundary; old guided/lightweight and brand flags retain their meaning. Registry schema 1 validates finite alternatives; a loadout's optional `null` value selects its declared default. Lock/installation schemas remain 2 and pin resolved string values. Old installations verify their pinned definitions without consulting new options; exact source checkouts remain necessary for old pin reproduction. `available` remains candidate presence; local machine locations and observed versions appear in reports, not locks.

The Signals evidence-bundle v1 input schema is unchanged. Real imports now reject incompatible producer protocols. The reusable `inspect_bundle` and current direct CLI output qualify observation age with `source_age_days` and `input_schema_version`; `load_bundle`, the explicit `--legacy-summary` flag and legacy checkpoint transport preserve the original v1 summary keys and 30-day label for replay. The label supplies no selection authority. No new Signals search/result schema or live adapter is defined here.

## Native-sufficient selection

`plan` and `apply` without loadout IDs now select no additional task guidance. The empty stage map is accepted by lock schema 2; earlier nonempty locks and all named loadouts retain their meaning. The default writes an owned routing block and license pin for lifecycle management, with no skills or tool probes. Explicit `--with context-*` resources can be delivered without a composed loadout or its setup guide. Refresh preserves installed selections; switching to no IDs with `plan` previews removals before `apply`.

Task profile schema 1 now makes `pact` optional, defaulting to no prior-art pass; an explicit true disposition is preserved. `packet`, `plan` and `apply` add `selection_outcome` (`native-sufficient` or `focused`). This reports declared selection, not semantic task classification, observed activation or human value. Exact older readers may reject the new empty map; reproduce old pins from their old source and use the current source for new native-sufficient pins. No installation is silently migrated.

## Greenfield personal library (unreleased)

Catalog, project profile, interest, assessment and private event documents use independent schema version 1. `docs/product.yaml` is the bundle's schema-3 product ledger. Existing loadout, task-packet, evidence-bundle and schema-2 installation/portable-lock contracts keep their meanings. No published tag changes.

`--profile` on plan/apply/refresh selects a catalog project profile by ID or basename; packet continues to read a supplied task-profile file. Existing explicit loadout and `--with` commands remain the delivery primitive. Refresh without a new selection preserves the installed set.

Claude unmanaged prose imports are delegated to the host. Context uses an explicit owned block when CLAUDE.md shadows AGENTS.md, except a verified filesystem alias to AGENTS.md. It no longer interprets arbitrary Markdown to suppress delivery. Existing managed blocks remain refreshable/removable; standalone imports retain their original bytes and may cause duplicate reading on a host that also resolves them. No claim of native discovery follows from this routing choice.

Private immutable evidence/history and future selections survive missing peers. Production schedules are paused configuration, with finite native-host activation documented separately. No candidate-supplied command or policy field is executed.
