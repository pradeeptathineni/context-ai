# context-ai

Context AI is my personal library of project equipment, standards, choices and evidence. Browse what fits a project, keep older alternatives with their limits, and pin only the guidance or tools that earn a role. Ordinary work starts with the project's instructions and native tools.

The [catalog and profiles](docs/library.md) show actual selections for Labs, home-lab, Signals, Principles and an exploratory simulation interest. [Project opportunities](docs/project-suggestions.md) connect inspected needs to a concrete next action. The [local portal](examples/web/index.html) brings options, reasons and evidence together; it installs nothing.

```sh
.venv/bin/python scripts/context_ai.py catalog
.venv/bin/python scripts/context_ai.py select labs
.venv/bin/python scripts/context_ai.py suggestions
```

[Safe delivery and maintenance](docs/library.md) provide preview, pinned setup, refresh, verified controlled trials, finite evidence intake, policy-bound future selections and undo. Shared resources feed Codex and Claude through thin adapters. The [140-concept index](concepts.yaml), original loadout scope and upstream attribution remain available without becoming required reading for every task. [Product scope](docs/PRODUCT.md) separates implemented behavior from demonstrated benefit.

## Use it for a task

Give your agent the change you need and the Context source path:

> Use Context AI at SOURCE_PATH to fix this failing integration. Inspect this project's instructions and tools, choose the smallest useful execution profile, complete the fix, and report what you used and verified.

The ordinary outcome is **native-sufficient**: use the project's guidance and tools with zero additional Context reads. The [context-loadout skill](skills/context-loadout/SKILL.md) helps when several choices need resolution; a read-only [execution packet](docs/task-profiles.md) can validate explicit selections. You do not need to name modules, options or model routes. A profile or installation is optional for a one-off task.

| Need | Start here |
| --- | --- |
| Ordinary covered task | Use project guidance and native tools; select no added guidance. No setup or receipt is required. |
| One capability gap | Read a relevant file from an exact Context checkout or archive. For verbose output, use [bounded capture and retrieval](procedures/output.md). |
| Several choices in one task | Let the agent resolve a [task profile](docs/task-profiles.md), then read its selected guidance and use native tools. |
| Repeated work in one project | Let the agent choose, preview, and pin a loadout. Read only the guidance for the current stage. |

If the project's own guidance is enough, complete the task with that. For either route, check claims against the project and run its relevant tests.

When the task needs a diagnostic method, read [diagnose and fix](procedures/diagnose.md). For a correctness/compatibility review, read [review](procedures/review.md). For a bounded interaction correction, read [lightweight design](procedures/web-design-lightweight.md) and [browser verification](domains/web/browser-verification.md). These procedures use the consumer's tools and preserve its instructions and visual identity.

An ordinary agent request can be:

> Use Context AI at SOURCE_PATH for this maintenance task. Preserve this repository's instructions, read only guidance that helps the change, implement it, and run the relevant project checks. Report what you used and what the checks showed.

For recurring use, the agent can choose from:

| Loadout | Select when |
| --- | --- |
| essentials | A consequential decision, regression risk or test-first task calls for prior-art search, TDD and spec/standards/complexity review |
| standard | Substantial development needs inspect/implement/test/review/delivery guidance (composes essentials) |
| context-authoring | Context authority, compression, provenance or compatibility is changing |
| research-evidence | A decision needs primary evidence and comparative options |
| web-experience | Web design, UX, accessibility or browser acceptance is changing |
| react-web | The web task also needs guidance for its actual React framework |
| service-api | API contracts, persistence or failure behavior is changing |
| aws-infrastructure | Existing Terraform/AWS planning or validation is involved |
| release-review | An authorized publication needs compatibility and release checks |

Selections compose; `standard` includes `essentials` and `react-web` includes `web-experience`. `standard` defaults to direct review; `--option review_mode=fresh` selects one bounded native reader when the host and existing authority permit it. A bounded existing web edit can choose `--design-procedure lightweight`; substantial design work defaults to guided. The [loadout guide](docs/loadouts.md) describes options and composition.

Run these commands **from the Context source directory**, using Python 3.10+ and a source-local environment. The target is the consuming project's absolute directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python scripts/context_ai.py tools --project /absolute/project
.venv/bin/python scripts/context_ai.py plan --project /absolute/project --provider both
.venv/bin/python scripts/context_ai.py apply --project /absolute/project --provider both
.venv/bin/python scripts/context_ai.py verify --project /absolute/project
```

With no loadout IDs or `--with`, `plan` and `apply` select native-sufficient: no added task guidance or skill routers. They still manage a minimal project selection and its lifecycle. Explicit loadout IDs remain available; `refresh` without IDs preserves an existing selection. Review the plan before applying, including removals when changing an installed selection: it shows selected files, local tool candidates and project changes. `tools` inspects declarations, local packages, workspace ownership and PATH without running scripts or fetching packages. Installed Playwright files do not prove browser readiness. Application copies selected resources into `.context-ai/`, creates thin skill routers (`.agents/skills` for Codex, `.claude/skills` for Claude Code, `--provider codex|claude|both`) and adds a managed block to the project's `AGENTS.md`; Claude Code reads that natively unless a CLAUDE.md shadows it, in which case an owned CLAUDE.md block is added. It protects existing instructions and edited files. `verify` checks the installation and required runtime probes; it reports project checks as **not run**. Run those checks from the **consumer directory** and inspect its diff. Report what you actually read, invoked, and checked; a structured use receipt is optional for a comparison or audit.

For a recurring verbose-output need, select only the operation:

```sh
.venv/bin/python scripts/context_ai.py plan --with context-output --project /absolute/project --provider both
.venv/bin/python scripts/context_ai.py apply --with context-output --project /absolute/project --provider both
```

Then run from the consumer directory:

```sh
python3 .context-ai/resources/scripts/context_output.py run --log test-raw.log -- python3 -m unittest discover -s tests
python3 .context-ai/resources/scripts/context_output.py inspect test-raw.log --query 'Caused by' --query error
```

The command runs once, keeps raw output in a new owned file and returns the producer's exit status. The partial view defaults to 4 KiB and 40 evidence lines; expand a relevant range or query when the cause is missing. Native Read/Grep/Glob need their own explicit limits. This stdlib operation installs no hooks or service. [Output handling](procedures/output.md) gives the full boundary.

`refresh` previews changes to a selection; `undo` removes unchanged owned files and preserves user edits. See the [command contract](docs/loadouts.md) for details, [compatibility and recovery](docs/compatibility.md) for moving or restoring a selection, and the [Codex](providers/openai/codex.md) and [Claude Code](providers/anthropic/claude-code.md) adapters for discovery limits.

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

Tests exercise all nine loadouts for both hosts, portable file pins, edited-file protection and recovery from interrupted application. The [web exercise](examples/web/brief.md) includes browser, interaction and accessibility checks. These are automated and builder checks. The [selective-value campaign](evals/selective-value.md) records the current native-sufficient default and measured focused routes. Earlier same-task consumer trials are recorded in [essentials](evals/essentials-trial.md), [host activation](evals/host-activation.md) and [efficiency](evals/context-efficiency-trial.md); human usefulness remains unmeasured.

Installation verification does not run consumer project tests. Fixture tests, local browser checks and reported file reads do not establish production behavior, human usefulness or native skill activation. The [loadout guide](docs/loadouts.md#evidence-discovery-and-limits) details these boundaries.

Library releases use immutable annotated tags and [CHANGELOG](CHANGELOG.md). Schema versions remain independent. Repository-owned content is [MIT](LICENSE); upstream snapshots retain their own declared licences and notices.

The premature v1.0.0 designation was withdrawn; its source commit remains available. Development continues in 0.x. Stable publication requires a separate future approval.
