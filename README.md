# context-ai

Evidence-backed context and project loadouts for AI-assisted development.

Choose the guidance a project needs, pin it, and use it through the agent you already have. Context AI provides concise behavioral modules, a practical web design/verification procedure, and project-local Codex delivery with file ownership and undo. It keeps source evidence, adoption decisions, installed resources, and actual use separate.

## Choose a loadout

| Loadout | What it equips |
| --- | --- |
| standard | Proportional development, prior art, comments, tests, review and delivery |
| context-authoring | Context compression, authority, coherence, provenance and compatibility |
| research-evidence | Primary evidence and useful options through the Signals research method |
| web-experience | Impeccable-led instruction-only design, UX, accessibility and browser critique |
| react-web | Web experience plus React guidance matched to the actual framework |
| service-api | API trust/contracts, persistence, failures and isolated migrations |
| aws-infrastructure | Existing Terraform/AWS planning, validation and hosting boundaries |
| release-review | Final review, meaningful checks and immutable publication |

Selections compose: `standard + web-experience + react-web` is valid. A backend task does not select the design suite. Project instructions, user brand and authorized scope remain decisive.

## Use it

From an exact checkout or exported release archive, with Python 3.10+:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python scripts/context_ai.py list
.venv/bin/python scripts/context_ai.py plan standard react-web --project /absolute/project --provider codex
.venv/bin/python scripts/context_ai.py apply standard react-web --project /absolute/project --provider codex
.venv/bin/python scripts/context_ai.py verify --project /absolute/project
```

Review the plan before applying. The command copies selected resources/notice dependencies into `.context-ai/`, creates selected skill routers, and appends one managed AGENTS block. Existing instructions and edited files are protected. `refresh` proposes a new lock/diff; `undo` removes unchanged owned materialization and preserves user edits. Read the routed stage resources explicitly when the running client has not refreshed skill discovery.

See the [command and schema contract](docs/loadouts.md), [compatibility/migration guide](docs/compatibility.md), and [Codex adapter](providers/openai/codex.md). Existing direct module and concept lookup consumers remain supported.

## What lives where

- [core](core/engineering.md): canonical provider-independent behavior, including comments, version control and prior art.
- [domains](domains/web/design.md): concern-specific web, service and infrastructure guidance.
- [overlays](overlays/README.md): opt-in house policy; old custom paths remain compatibility routers.
- [loadouts](loadouts/standard.yaml): authored selections; resolved locks and use receipts are separate artifacts.
- [context-loadout skill](skills/context-loadout/SKILL.md): selection/use procedure, alongside the preserved local standard skill.
- [concepts](concepts.yaml), [sources](sources.yaml), and [decisions](decisions/bootstrap.yaml): definitions, sourced prior-art candidates and project dispositions.
- [source lock](sources.lock.json) and inactive sourced snapshots: exact upstream pins with licences/notices.
- [model routing](models/routing.yaml): stable logical profiles and reviewed provider bindings; no global settings change.

## Proof and limits

The [bootstrap receipt](evals/bootstrap-use.json) records actual explicit reads and validator maintenance before bulk implementation. All eight loadouts have materialized consumer tests. The [web exercise](examples/web/brief.md) builds a static fixture, tests four viewport widths and two palettes with Playwright/axe, and has an inspected critique/revision pass. [Release evidence](evals/v1-acceptance.md) records outcomes and their limits; [references](docs/references.md) records influences and review dates.

Codex is the v1 delivery adapter. Impeccable binaries/hooks/extensions are excluded; its selected documentation works through direct reads. This is a context library, with no agent runtime, automatic tool installation, deployment side effects or signal-scoring engine. Capability presence checks are followed by project-specific verification recipes. Fixture tests, local browser judgment and self-reported reads do not prove production behavior, human usefulness, or native skill activation. Signals evidence advice never grants installation authority.

Run the deterministic gates:

```sh
ruby scripts/validate.rb
.venv/bin/python scripts/check_loadouts.py
.venv/bin/python -m unittest discover -s tests -v
npm ci --ignore-scripts
npm run build:web
npm run test:web
git diff --check
```

The browser gate uses Node 24 in CI (Node 20+ required) and the pinned Playwright Chromium runtime: `node node_modules/playwright/cli.js install chromium`. CI also preserves its screenshots and results.

Library releases use immutable annotated tags and [CHANGELOG](CHANGELOG.md). Schema versions remain independent. Repository-owned content is [MIT](LICENSE); upstream snapshots retain their own declared licences and notices.
