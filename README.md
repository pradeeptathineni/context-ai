# context-ai

Context AI is a library of guidance for AI-assisted software work. Read one relevant file for a task, or pin a selected set of files (a **loadout**) in a project that will use them repeatedly. Your agent still follows that project's instructions and runs its checks.

The library covers engineering, research, writing, web work, APIs, infrastructure, and evaluation. It also records where consequential guidance came from. The [project loadout tool](docs/loadouts.md) currently delivers selected files to Codex projects; it does not run an agent or install the tools those files discuss.

## Use it for a task

Start with the consuming project's instructions and the change you need to make. Then choose a route:

| Need | Start here |
| --- | --- |
| One task | Read a relevant file from an exact Context checkout or archive. A README change, for example, may benefit from [writing guidance](overlays/writing.md). No setup or receipt is required. |
| Repeated work in one project | Use the [context-loadout skill](skills/context-loadout/SKILL.md) to choose, preview, and pin a loadout. Read only the guidance for the current stage. |

If the project's own guidance is enough, complete the task with that. For either route, check claims against the project and run its relevant tests.

An ordinary agent request can be:

> Use Context AI at SOURCE_PATH for this maintenance task. Preserve this repository's instructions, read only guidance that helps the change, implement it, and run the relevant project checks. Report what you used and what the checks showed.

For a loadout, choose the work it must support:

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

Selections compose; `react-web` includes `web-experience`. A bounded existing web edit can choose `--design-procedure lightweight`; substantial design work defaults to guided. The [loadout guide](docs/loadouts.md) describes options and composition.

Run these commands **from the Context source directory**, using Python 3.10+ and a source-local environment. The target is the consuming project's absolute directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python scripts/context_ai.py explain standard
.venv/bin/python scripts/context_ai.py plan standard --project /absolute/project
.venv/bin/python scripts/context_ai.py apply standard --project /absolute/project
.venv/bin/python scripts/context_ai.py verify --project /absolute/project
```

Review the plan before applying: it shows the files and project changes. Application copies selected resources into `.context-ai/`, creates skill routers and adds a managed block to the project's `AGENTS.md`. It protects existing instructions and edited files. `verify` checks the installation and required runtime probes; it reports project checks as **not run**. Run those checks from the **consumer directory** and inspect its diff. Report what you actually read, invoked, and checked; a structured use receipt is optional for a comparison or audit.

`refresh` previews changes to a selection; `undo` removes unchanged owned files and preserves user edits. See the [command contract](docs/loadouts.md) for details, [compatibility and recovery](docs/compatibility.md) for moving or restoring a selection, and the [Codex adapter](providers/openai/codex.md) for discovery limits.

## How the parts fit

| Part | Job |
| --- | --- |
| [Concepts](concepts.yaml) | Name distinct decisions an agent may need to make. |
| [Signals](signals/common.yaml) | Offer sourced options for some concepts; an option is not a selection. |
| [Decisions](decisions/composition.yaml) | Record what Context currently chose, why, and when to reconsider. |
| [Core](core/engineering.md) | Give short provider-independent behavior for actual work. |
| [Overlays](overlays/README.md) and [domains](domains/web/design.md) | Add optional house practice or concern-specific guidance. |
| [Skills](skills/context-loadout/SKILL.md) | Route a repeatable procedure when the agent discovers or explicitly reads it. |
| [Loadouts](loadouts/standard.yaml) | Select and pin files and capabilities for repeated project work. |
| [Provider adapter](providers/openai/codex.md) | Explain how a particular agent host receives the selected guidance. |
| Local installation and use | Record owned files in the project; report actual reads, invocations and checks in the task result. |

A task selects the relevant guidance directly or through a loadout. [Concept lookup](scripts/lookup.rb) can surface options for a consequential choice; [model routing](models/routing.yaml) keeps volatile model bindings structured. Evidence informs a decision, and installation makes selected resources available. The agent still has to read them and do the work.

## Change this library

Start with [repository guidance](AGENTS.md). Read the relevant `core/` and `overlays/` files for your change; a link in `AGENTS.md` is a route, not a file you have already loaded. For a docs change, check the prose against the actual command or API behavior before editing. Keep canonical rules in `core/`, put optional house practice in `overlays/`, and add a loadout or dependency only for a real consumer.

For a first checkout, use Python 3.10+, Ruby, and Node 20+ (CI uses Node 24). Create a source-local environment and install the development dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.txt
```

Run these repository checks before handing off a change:

```sh
ruby scripts/validate.rb
.venv/bin/python -m unittest discover -s tests
git diff --check
```

The Python suite materializes every loadout and probes Node, even for docs changes. For the full CI path, also run Ruff and loadout validation, then the web build and browser tests:

```sh
.venv/bin/ruff check scripts tests
.venv/bin/python scripts/check_loadouts.py
npm ci --ignore-scripts
node node_modules/playwright/cli.js install chromium
npm run build:web
npm run test:web
```

The browser tests need the pinned Playwright Chromium runtime. Use an existing supported Node on your `PATH`; these commands do not install or switch Node. See [references](docs/references.md) for source reviews, [compatibility](docs/compatibility.md) for migrations, and [CHANGELOG](CHANGELOG.md) for releases.

## Proof and limits

Tests exercise all eight loadouts, portable file pins, edited-file protection and recovery from interrupted application. The [web exercise](examples/web/brief.md) includes browser, interaction and accessibility checks. These are automated and builder checks; human usefulness and model input savings remain unmeasured.

Installation verification does not run consumer project tests. Fixture tests, local browser checks and reported file reads do not establish production behavior, human usefulness or native skill activation. The [loadout guide](docs/loadouts.md#evidence-discovery-and-limits) details these boundaries.

Library releases use immutable annotated tags and [CHANGELOG](CHANGELOG.md). Schema versions remain independent. Repository-owned content is [MIT](LICENSE); upstream snapshots retain their own declared licences and notices.

The premature v1.0.0 designation was withdrawn; its source commit remains available. Development continues in 0.x. Stable publication requires a separate future approval.
