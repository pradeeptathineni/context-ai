# Project loadouts

A manifest selects resources; a resolved lock pins their bytes; a use receipt records what was actually read or run. These have separate files and purposes. Project instructions and explicit user authority take precedence.

## Supported catalogue

| ID | Use | Verification recipe |
| --- | --- | --- |
| standard | Proportional inspect/implement/test/review/deliver; existing tools and prior art | Project tests, actual diff, truthful completion |
| context-authoring | Compression, authority, coherence, provenance and refresh | Metadata/links/schema, retained requirements, compatibility |
| research-evidence | Primary evidence, comparative options, freshness, Signals exchange | Exact bytes, provenance, citations, honest mode and constraints |
| web-experience | Impeccable instruction-only design, UX/content, accessibility and browser critique | Static build, screenshots, interactions, axe, asset budget/reduced motion |
| react-web | React rules matched to actual framework; composes web-experience | Real version/client-server/static-export detection and browser checks |
| service-api | API trust/contracts, persistence/failure behavior, existing stack | Real route/type/schema tests and isolated database/migration checks |
| aws-infrastructure | Existing Terraform/AWS identity/state/hosting constraints | Safe source inspection, format/isolated validation, authorized plan/rollback |
| release-review | Final review, compatibility, immutable release and destination | Clean checkout/package, remote SHA/CI then tag/release verification |

Each has a real disposable materialization test in `tests/test_loadouts.py`. The actual library used standard + context-authoring; research-evidence guides source/adoption stages; release-review guides publication. The browser exercise in `examples/web/` uses standard + web-experience. These tested compositions do not imply every possible cross-product or production stack is tested.

## Commands

Use Python 3.10+ and Ruby for the retained repository validator. No global install or inference call is needed:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python scripts/context_ai.py list
.venv/bin/python scripts/context_ai.py explain react-web
.venv/bin/python scripts/context_ai.py plan standard react-web --project /absolute/project --provider codex --brand expressive
.venv/bin/python scripts/context_ai.py apply standard react-web --project /absolute/project --provider codex --brand expressive
.venv/bin/python scripts/context_ai.py verify --project /absolute/project
.venv/bin/python scripts/context_ai.py refresh --project /absolute/project
.venv/bin/python scripts/context_ai.py undo --project /absolute/project
```

`plan` prints a resolution, write inventory and resource diff on stdout without changing the project. Read it before application. `apply` copies only the selected resources and their explicit runtime/notice dependencies into `.context-ai/resources/`, installs selected skill routers in `.agents/skills/`, and appends one owned block to root AGENTS.md. It preflights all paths and refuses unowned existing targets or edited/missing managed files. It never changes global configuration or executes check recipes. Reapplication of an identical resolution is stable; applying a new pin is a separate explicit checkpoint action.

`verify` checks resource pins, ownership, routing and required capability availability. Optional capability discovery can be incomplete: a CLI-presence check is not proof that a project has a compatible runtime/browser/database. The agent must run the selected recipe. `refresh` proposes a lock/file diff, preserves options when reusing the installed selection, and never activates it. It compares local reviewed library bytes; it does not fetch upstream or run Signals research. Refresh sources/evidence explicitly, append a successor decision, then inspect/apply the proposal.

`undo` removes unchanged owned files and the unchanged routing block. It preserves edited files/blocks and reports conflicts, retaining an undo-pending receipt. Resolve those conflicts before reapplying. The managed area should be committed or exported when another machine needs the same pin; local dogfood receipts and private project bindings may remain ignored. Empty directories may remain after undo. Application is preflighted with atomic individual writes and a final lock; it is not a crash-atomic filesystem transaction or protection against a concurrent hostile filesystem writer.

## Public schema-1 contract

Loadout YAML has `id`, description/characteristics, ordered composition/modules/skills, required/optional capabilities, bounded options, stage routing, check recipes and decision references. `schemas/loadout.schema.json` owns its allowed fields. Only short ordered composition is supported: depth-first parents then selection, deduplicated by ID; cycles and conflicting defaults fail. The brand option is quiet or expressive. One primary style procedure applies at a stage; project/brand intent wins over advisory taste.

A lock has its own schema and pins resource SHA-256s, library revision/tree digest, selected loadouts, stage routing, options, capability definitions/states, checks and current decision revisions. Source tree hashing excludes the lock itself. An installation receipt additionally records owned file hashes and the exact root routing block. Schemas reject unknown fields except explicitly defined optional recovery metadata. YAML safe parsing rejects duplicate/non-string keys, aliases and object tags. Approved relative paths cannot traverse or follow symlinks. `resources.yaml` declares file prerequisites. Markdown links are informational and never expand closure; directories, escapes, cycles and active instruction filenames fail. Selected upstream bytes and required notices are checked against `sources.lock.json`. Unselected upstream files cannot block unrelated work. Manifests have no executable expressions or installer authority.

Decisions append revisions with a predecessor; `current_decisions()` derives the current view. Old exported pins continue to resolve with their original source bytes. `sources.lock.json` owns upstream revision/license/file hashes; snapshots remain inactive, with instruction filenames renamed. Selected resources include licence/notice dependencies. Decisions are pinned in the lock; the full decision/catalog/source trees remain available in the source checkout, rather than copied into every composition. The external `standard` skill is preserved; no new skill uses that discovery name.

## Evidence, discovery and limits

The frozen Signals v1 interface is `schemas/evidence-bundle-v1.schema.json`, copied unchanged from the supplied kit. Use `scripts/evidence.py` with an exact-byte digest and pinned producer repository/40-character commit, or `--checkpoint` and `--producer`. It validates schema and semantic references, public URLs without fetching, modes/privacy, support for adoption advice, empty-result honesty and explicit stale/unknown freshness. Fixture mode has no public admission flag. Test-only fixture admission is separate. Source IDs existing does not prove support for the claim; hashes prove bytes, not truth or cryptographic producer identity. The trusted local checkpoint boundary supplies identity. Recommendations, unknown extension policies and constraints never activate a capability.

A use receipt records capability/pin, consumer/stage, read/invoked/validated/not_used, discovery mode, result and command/artifact reference. Installation is separate. Native discovery in this active desktop session is not inferred from filesystem installation: explicit reads are recorded honestly. Reopen the project in a fresh trusted session for metadata discovery; see the [Codex adapter](../providers/openai/codex.md). An unavailable optional browser does not block unrelated API work, but web acceptance remains incomplete until exercised.

This library equips existing agents. It includes no runtime, independent signal-scoring engine, hosted service, package-registry release, automatic upstream installer, global hooks, paid API connection or deployment side effect. Live Terraform/AWS and backend checks depend on the consuming project's authority and environment. [Compatibility and migration](compatibility.md) explains preserved paths and identifiers.
