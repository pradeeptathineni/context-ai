# Compatibility and migration

Pre-1 library releases and integer schema versions have separate meanings. Loadout, evidence and model routing use schema 1; resolution/installation and concepts use schema 2. Changes to their documented fields or semantics require compatibility review; published tags are immutable.

Core modules and existing concept/profile/route IDs remain stable. Catalog schema 2 unifies definitions, scope, aliases, modules and coverage with shared defaults. All 140 IDs remain. The Ruby lookup supports both shapes; `scripts/concepts.py definitions` emits the legacy string map for direct YAML consumers. Schema-1 pins remain reproducible from exact source commits. Kit seed concept names remain in immutable bootstrap decisions and are resolved by the explicit alias map in the contract validator; they are not new mandatory Signals vocabulary.

House policies moved from custom/ to overlays/. Every old custom Markdown path remains a short routing document; a linked overlay is loaded only after an actual read. Existing standard skill and lookup entrypoints keep working. New consumers should select overlays through loadouts. No private neon1 information belongs in this public library.

Codex is the current supported materialization adapter. Its project-local skill routers use unique context-prefixed names; the existing standard discovery name is untouched. Instruction-only upstream adaptations declare omitted binaries/hooks and preserve pinned documentation/notice files. A project can continue a stage on its earlier lock while the library advances; review a refresh at a checkpoint before changing the active pin.

Exact snapshots remain available in Git commits and exported release/checkpoint archives. Materialization does not retrieve an old revision automatically: use the exact checkout/archive to reproduce that pin. Use the commit or archive digest as the bootstrap identity; no stable designation is implied.

## Portable ownership

Resolution/installation schema 2 separates a relative project declaration from local `bound_project`. Existing schema-1 receipts still verify in their original directory. Copied legacy receipts refuse until `rebind` verifies every owned byte, routing block and required command, then changes only the binding. Edits cause refusal; no hand-editing or falsified ownership is required. `export` emits a portable pin; `apply --lock` verifies its resources against the selected source checkout. An active refresh remains a proposal. `recover` uses a local write journal to restore interrupted application while retaining later edits. Keep installation receipts and recovery records local.
