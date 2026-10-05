# context-ai

Evidence-backed context and project loadouts for AI-assisted development.

Choose the guidance a project needs, pin it, and use it through the agent you already have. Context AI provides concise behavioral modules, a practical web design/verification procedure, and project-local Codex delivery with file ownership and undo. It keeps source evidence, adoption decisions, installed resources, and actual use separate.

## Use it for a task

Start with the consuming project's instructions and intended change. Context is optional guidance: read it when it can improve a decision or catch a failure.

For a small settled task, read a relevant module directly from an exact checkout or archive. No Python environment, installation or receipt file is needed. For example, a README usage change may need [writing guidance](overlays/writing.md); verify the example against the real API and run the project's own checks. Skip design, deployment and unrelated stage guidance. If the project already supplies sufficient instructions, say so and complete the task.

An ordinary agent request can be:

> Use Context AI at SOURCE_PATH for this maintenance task. Preserve this repository's instructions, read only guidance that helps the change, implement it, and run the relevant project checks. Report what you used and what the checks showed.

For a reusable project selection, use the [context-loadout skill](skills/context-loadout/SKILL.md) and the command below. Pin the selection once, then read only the current stage. Installation does not run the project tests.

| Loadout | Select when |
| --- | --- |
| standard | Substantial development needs inspect/implement/test/review/delivery guidance |
| context-authoring | Context authority, compression, provenance or compatibility is changing |
| research-evidence | A decision needs primary evidence and comparative options |
| web-experience | Web design, UX, accessibility or browser acceptance is changing |
| react-web | The web task also needs guidance for its actual React framework |
| service-api | API contracts, persistence or failure behavior is changing |
| aws-infrastructure | Existing Terraform/AWS planning or validation is involved |
| release-review | An authorized publication needs compatibility and release checks |

Selections compose; `react-web` includes `web-experience`. A bounded existing web edit can choose `--design-procedure lightweight`; substantial design work defaults to guided. Preserve the user's brand and choose one primary procedure. Backend and documentation tasks do not select the design suite.

Run these commands **from the Context source directory**, using Python 3.10+ and a source-local environment. The target is the consuming project's absolute directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python scripts/context_ai.py explain standard
.venv/bin/python scripts/context_ai.py plan standard --project /absolute/project
.venv/bin/python scripts/context_ai.py apply standard --project /absolute/project
.venv/bin/python scripts/context_ai.py verify --project /absolute/project
```

Review the plan before applying. It lists resources, stage routes, capabilities, options, suggested checks and owned writes. Application copies into `.context-ai/`, creates selected skill routers and appends one managed AGENTS block; existing instructions and edited files are protected. `verify` checks that installation and required runtime probes; it reports project checks as **not run**. Execute the relevant task checks from the **consumer directory** and inspect the resulting diff. Report actual reads, invocations and outcomes in the task result; a structured use receipt is optional for a comparison or audit.

`refresh` proposes a new lock/diff; `undo` removes unchanged owned files and preserves user edits. See the [command contract](docs/loadouts.md) for changing a selection, [compatibility and recovery](docs/compatibility.md) for moving or restoring it, and the [Codex adapter](providers/openai/codex.md) for discovery limits. An exported source works without Git metadata; its resource hashes still pin the selected bytes.

## What lives where

- [core](core/engineering.md): canonical provider-independent behavior, including comments, version control and prior art.
- [domains](domains/web/design.md): concern-specific web, service and infrastructure guidance.
- [overlays](overlays/README.md): opt-in house policy; old custom paths remain compatibility routers.
- [loadouts](loadouts/standard.yaml): authored selections for recurring project work; task use is reported separately.
- [context-loadout skill](skills/context-loadout/SKILL.md): selection/use procedure, alongside the preserved local standard skill.
- [concepts](concepts.yaml) and [sources](sources.yaml): decision areas and original references. Use `scripts/context_ai.py decisions` for the resolved current choices, or `explain LOADOUT` for choices applying to a selection; predecessors stay outside that reading path.
- [source lock](sources.lock.json) and inactive sourced snapshots: exact upstream pins with licences/notices.
- [model routing](models/routing.yaml): stable logical profiles and reviewed provider bindings; no global settings change.

## Proof and limits

Tests cover all eight selections, explicit dependency closure, portable pins, edited-file protection and interruption recovery. The existing [web exercise](examples/web/brief.md) checks four widths, two example palettes, interactions and accessibility with Playwright/axe. [References](docs/references.md) records source influences and review dates. These are deterministic and builder checks; human usefulness and model input savings remain unmeasured.

Codex is the current delivery adapter. Impeccable binaries/hooks/extensions are excluded; its selected documentation works through direct reads. This is a context library, with no agent runtime, automatic tool installation, deployment side effects or signal-scoring engine. Installation verification suggests project-specific checks; the working agent must execute them. Fixture tests, local browser judgment and self-reported reads do not prove production behavior, human usefulness, or native skill activation. Signals evidence advice never grants installation authority.

Run the deterministic gates:

```sh
.venv/bin/python -m pip install --require-hashes -r requirements-dev.txt
.venv/bin/ruff check scripts tests
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

The premature v1.0.0 designation was withdrawn; its source commit remains available. Development continues in 0.x. Stable publication requires a separate future approval.
