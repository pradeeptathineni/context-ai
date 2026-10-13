# Context AI

Context AI is an evidence-backed library of reusable AI development guidance and project selections. It helps an existing agent find relevant engineering principles, practices, skills and tooling, then use them in the project's own environment. Ordinary work starts with project instructions and native tools; add Context only when it addresses a concrete need.

Context supplies reusable mechanisms, not one person's operating setup. A custom consumer owns its current preferences, machine and account facts, model choices and resource budgets. The public project profiles are pinned examples, not live personal configuration. See [the ownership boundary](docs/adoption.md#reusable-library-and-custom-consumers).

Use one file directly, resolve several choices for a task, or pin a reusable project loadout. Context manages selected files and their lifecycle. Your agent owns interpretation and execution; its native controls own models, permissions and delegation. Signals supplies optional external research evidence, while Context owns contextual adoption and composition.

## Use one context

Give your agent an exact checkout or archive path and a specific need:

> Read SOURCE_PATH/overlays/writing.md and correct this README command. Preserve the project's instructions, make the edit, and run its documentation checks. Report what you read and checked.

A direct read needs no installation or Python environment. A link is a pointer until the agent reads it. Use [diagnosis](procedures/diagnose.md) for an observable failure, [review](procedures/review.md) for a consequential diff, or a relevant [core](core/context.md), [overlay](overlays/README.md) or [domain](domains/service/api.md) file. If the project already supplies enough guidance, use it without extra Context reads.

For several task choices, the [context-loadout skill](skills/context-loadout/SKILL.md) can resolve an optional read-only [task profile](docs/task-profiles.md). It recommends resources and development choices without installing anything or changing the active model.

## Keep a project selection

The [catalog and project profiles](docs/library.md) preserve options, reasons, evidence and recurring selections. The [portal](examples/web/index.html) shows these public choices and installs nothing. Follow the source-environment setup in the library guide, then run from the Context checkout:

```sh
.venv/bin/python scripts/context_ai.py catalog
.venv/bin/python scripts/context_ai.py select home-lab
.venv/bin/python scripts/context_ai.py plan --profile home-lab --project /absolute/consumer --provider both
.venv/bin/python scripts/context_ai.py apply --profile home-lab --project /absolute/consumer --provider both
.venv/bin/python scripts/context_ai.py verify --project /absolute/consumer
.venv/bin/python scripts/context_ai.py refresh --project /absolute/consumer
.venv/bin/python scripts/context_ai.py undo --project /absolute/consumer
```

Review the plan before applying. Refresh proposes an update; apply performs it. Undo preserves unmanaged instructions and edited managed files. The [loadout command contract](docs/loadouts.md) covers explicit compositions, prerequisites, portable pins, recovery and removal. Shared resource bytes feed thin Codex and Claude routers; new instructions may require a fresh host session.

Selection, installation, actual use and benefit are separate observations. `verify` checks installed bytes and required runtime probes, and reports consumer project checks as not run. Run those checks in the consumer. [Evaluations](evals/README.md) retain native baselines, failed trials and scoped results; passing tests do not establish human usefulness or general efficiency gains. [Product scope](docs/PRODUCT.md) distinguishes delivery from value.

## Where things belong

| Source | Responsibility |
| --- | --- |
| `core/` | Canonical, provider-independent engineering behavior. |
| `overlays/` | Reusable optional custom variants of core guidance; their paths remain stable. |
| `domains/`, `procedures/`, `skills/` | Concern-specific modules and on-demand methods, with concern owners in `ownership.yaml`. |
| `library/` | Catalog options, pinned example project profiles and scoped AI-engineering interests. A custom consumer owns its current selection and private state. |
| `loadouts/`, `capabilities.yaml`, `resources.yaml` | Composition declarations, trusted definitions and explicit resource dependencies. |
| `scripts/context_ai.py`, `schemas/` | Declaration validation, destination discovery, pinned delivery, verification, refresh, recovery and undo. |
| `concepts.yaml`, `signals/`, `sources.yaml`, `decisions/` | Decision vocabulary, sourced candidates, original sources and current contextual choices. |
| `sourced/`, `sources.lock.json`, `docs/references.md` | Exact upstream snapshots, integrity/license pins and material influences. |
| `models/`, `providers/` | Structured model advice and host-specific consumption boundaries. |
| `evals/`, `history/` | Reproducible evidence, comparative baselines and required migration records. |

Generated portal and product views read these sources. Private library state and consumer ownership receipts stay local. General project opportunities belong to Signals; [migration references](docs/project-suggestions.md) preserve the transfer and recovery records.

## Develop this library

Read [AGENTS.md](AGENTS.md). Use Python 3.10+, Ruby and Node 20+; CI uses Python 3.12 and Node 24. Create the source-local development environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.txt
```

Run the complete repository and browser gates:

```sh
ruby scripts/validate.rb
.venv/bin/python scripts/check_loadouts.py
.venv/bin/python scripts/build_product.py --check
.venv/bin/python scripts/build_catalog.py --check
.venv/bin/ruff check scripts tests
.venv/bin/python -m unittest discover -s tests
npm ci --ignore-scripts
node node_modules/playwright/cli.js install chromium
npm run build:web
npm run test:web
git diff --check
```

The full suite exercises all loadouts and needs the supported Node and pinned Chromium runtimes. Consumer selections require only their declared prerequisites. [Compatibility](docs/compatibility.md) explains stable identifiers, exact-source replay and migrations.

The latest published library tag is **v0.3.0**; subsequent work is **Unreleased** in [CHANGELOG.md](CHANGELOG.md). Schema versions are independent. The withdrawn v1.0.0 designation remains reserved; no stable release is implied. Repository-owned content is [MIT](LICENSE); upstream files retain their own licenses and notices.
