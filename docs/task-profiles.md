# Equip a software task

Ask your existing agent to use Context for the task in ordinary language. It inspects the consuming project's scoped instructions, architecture, stack, tools and acceptance criteria, then chooses what would help. The [context-loadout skill](../skills/context-loadout/SKILL.md) owns this step. Project and user instructions always win.

For one settled task, a direct read or the project's own guidance may suffice. When several choices need checking, the agent writes a small profile and resolves it from an exact Context source checkout:

```sh
.venv/bin/python scripts/context_ai.py packet --profile /absolute/task.yaml --project /absolute/project
```

Use Context's source-local Python environment described in [loadouts](loadouts.md). The CLI, schema and example profiles live in that source checkout, rather than a consumer's installed resources. JSON and safe YAML are accepted. The command returns JSON advice and writes no consumer files. It performs selected static tool discovery without command probes, imports of project configuration, package scripts, network, installation or model calls. `task` is retained as the intended outcome; code never classifies its words.

The agent reads the packet's guidance, inspects unresolved boundaries and performs the task through its native tools within existing authority. Paths in the packet are relative to the Context source; listing them is not reading them. Report actual guidance reads, tool invocations, project checks and their results. A resolved packet is not evidence that the recommended work happened.

## Profile contract

The [schema](../schemas/task-profile.schema.json) owns version 1. Required fields are `schema_version`, `task`, `pact` and `verification`. Other choices are omitted unless they help the current task.

```yaml
schema_version: 1
task: Fix the service integration rejecting supported protocol replies.
context:
  mode: direct
  resources:
  - procedures/diagnose.md
  - domains/service/api.md
pact:
  required: false
  reason: The protocol contract and component ownership are settled.
verification:
- Reproduce the rejection before the fix; verify supported replies and incompatible-version failures afterward.
unresolved:
- Live producer credentials are unavailable; local contract tests cannot establish live integration.
```

| Field | Decision and default |
| --- | --- |
| `task` | Agent-interpreted outcome, preserved for review. No keyword routing. |
| `context` | Omitted means direct with no additional reads. `direct.resources` chooses guidance paths. `loadout.loadouts`, `stages` and optional `options` reuse the existing composition/option vocabulary. |
| `capabilities` | Explicit existing capability IDs mapped to `required` or `optional`; omitted means none beyond the selected loadout. Resource capabilities select instructions; commands receive static discovery. |
| `model` | Optional literal attributes for existing first-match [model routing](../models/routing.yaml). Omitted preserves the session without a recommendation; `{}` requests the policy fallback. Only attribute keys used by the current routes are accepted. |
| `orchestration` | `single_agent` by default; `separate_investigations`, `separate_implementation` or `fresh_review` select advisory guidance. No delegation or model changes occur. |
| `pact` | Explicit `required` boolean and reason. Required adds canonical prior-art guidance; the agent applies PACT/HRR and records the decision in the consuming project's existing artifact. |
| `verification` | Nonempty observable expectations. Text is never executable configuration. |
| `unresolved` | Known gaps, such as missing live credentials or an unclear acceptance criterion. The packet adds untested tool and host boundaries. |

Use task facts to make these choices, rather than copying them into another inventory. Scope, consequence, ambiguity, architecture, requirements, interaction and autonomy belong in `model` only when they affect a route. Technical concerns select existing resources/loadouts; stack facts justify capabilities. There is no redundant concern taxonomy, risk score, permissions field, scheduler or command manifest.

For model routing, supplied values match literally; omitted attributes never match a required literal. `*` belongs to policy and matches present or absent attributes. Unknown values can fall through to the policy fallback; the agent must inspect the returned route and correct mistaken interpretation. The binding is dated advice: verify the available model/reasoning controls on the active surface and preserve explicit session settings. The resolver does not select a new session or escalate automatically.

## Direct reads and recurring selections

Direct profiles select only their resources, explicit resource-capability prerequisites/notices and guidance justified by PACT/model/orchestration choices. For example, select `context-web-design-lightweight` for a bounded existing page correction and separately include browser verification. Direct mode has no loadout options: select the named resource alternative, or use a staged loadout for its bounded options.

For a project that repeatedly needs web work, a profile may propose:

```yaml
schema_version: 1
task: Redesign the product page within the established visual identity.
context:
  mode: loadout
  loadouts: [web-experience]
  stages: [design, test]
  options:
    design_procedure: lightweight
    brand: Preserve the existing typography, wordmark and restrained palette.
model:
  intent: coding
  scope: bounded
  interaction: iterative
pact:
  required: false
  reason: Existing product architecture and dependencies remain settled.
verification:
- Inspect desktop/mobile appearance, keyboard navigation, meaningful interactions and accessibility using the project tools.
```

This resolves current stage guidance, the selected primary design procedure, source notices and advisory checks. Resource capability `stages` hints keep unrelated procedures out; a missing hint conservatively applies to all selected stages. Command requirements remain the loadout's project requirements. An explicit task capability is always retained and can strengthen an optional requirement. Unknown loadouts, stages, options, capabilities and unsafe paths fail. Missing command candidates are reported as unresolved, including required ones; the advisory packet can still explain what is missing. The existing materialization resolver still refuses missing required capabilities.

`loadout` mode proposes a recurring composition; it does not install or update it. Use [plan/apply](loadouts.md) separately when persistence is justified and authorized. A packet against the current source does not read or refresh a consumer's installed lock; use that pin for an active pinned run. Review a changed selection at a task boundary. Historical pins remain reproducible from their exact source checkout.

Fresh review must be explicit in `orchestration` when its procedure or review-stage option is selected. A loadout's review-stage `review_mode` and orchestration must agree: fresh with `fresh_review`, direct otherwise. This catches contradictory advice without treating the recommendation as delegation permission. The host agent establishes authority, support and bounded ownership; if unavailable, report the gap and explicitly revise the choice. Native tools may exist without a PATH executable, so local tool observations cannot prove native browser or subagent readiness.

## Selection ownership after HRR

The [D-004 revision 3 decision](../decisions/composition.yaml) retains one selection owner:

| Part | Responsibility |
| --- | --- |
| README / project AGENTS | First-use route and scoped authority; point to the equipping owner without reproducing its workflow. |
| `context-loadout` | Interpret ordinary tasks, select the smallest sufficient resources and development shape, optionally resolve a profile or propose a recurring pin. |
| `standard` | Native-capability/prior-art judgment at consequential junctions; no competing task router. |
| Direct reads / loadouts / options | One-task retrieval or recurring reproducible composition; bounded alternatives change the selected definitions. |
| Procedures / concepts | Perform a specific method or name a decision for progressive lookup; neither is a semantic task classifier. |
| Model routing / orchestration | Resolve literal route attributes and advise a work shape; host controls actual settings and delegation. |
| Capability discovery | Static selected project candidates and uncertainty; agent observes native tools and runs authorized checks. |
| PACT/HRR | Reconsider consequential responsibility choices and record evidence/disposition, without becoming a mandatory phase for routine work. |

The deciding prior art was [native skill selection](https://learn.chatgpt.com/docs/build-skills), [Agent Skills progressive disclosure](https://agentskills.io/specification), and [Superpowers explicit planning](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/writing-plans/SKILL.md), reviewed 2026-10-05. Native skill descriptions and model judgment already handle semantic routing. Learn from explicit constraints/verification; importing a mandatory planning/execution lifecycle would overlap current owners. No external dependency or new skill/concept is needed.

[Example profiles](../examples/task-profiles) cover the six ordinary requests and a project-guidance-only edit. They are inspectable agent judgments under stated assumptions, not a classifier's outputs or proof of human usefulness. [Evaluation evidence](../evals/task-profiles.md) separates resolver checks from actual use.
