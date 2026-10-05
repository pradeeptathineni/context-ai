# References and provenance

## Sourcing policy

Prefer authoritative specifications, then first-party product documentation, then maintained and adopted open-source implementations, then high-quality engineering publications. Use synthesis only where those sources do not settle the repository's design. Adoption informs interoperability; it does not replace evidence.

External material is summarized and linked unless a pinned local copy has clear maintenance value and redistribution is permitted. A vendored artifact must record its local path, upstream URL, revision or tag, license, and review date, and must remain distinct from canonical adaptations. Volatile provider and model facts are reviewed against the product surface that consumes them.

All external sources below were reviewed on **2026-09-12** unless another date is shown. No upstream artifacts are vendored in v0.2.0, so no `sourced/` directory exists.

## Repository context and configuration map

- [`concepts.yaml`](../concepts.yaml) names provider-neutral decision areas drawn from this library's existing core and custom contexts, ShouldaUsedThat's decision contract, and Maestro AI's reuse register. The breadth of the index is this repository's synthesis; a listed concept is not a sourced claim that one tool owns it. Reviewed 2026-10-05.
- [`signals/common.yaml`](../signals/common.yaml) holds only standards and practice with directly supporting originals: [AGENTS.md](https://agents.md/), [Agent Skills](https://agentskills.io/specification), [MCP](https://modelcontextprotocol.io/specification/2026-07-28), [JSON Schema](https://json-schema.org/specification), [OpenAPI](https://spec.openapis.org/oas/v3.2.1.html), [OpenTelemetry](https://opentelemetry.io/docs/specs/otel/), [Semantic Versioning](https://semver.org/spec/v2.0.0.html), [SLSA](https://slsa.dev/spec/v1.2/), pinned [No AI slop](https://github.com/petergyang/no-ai-slop/blob/000650b156983f5159695b441477f4e63b25dc85/skills/no-ai-slop/SKILL.md), and pinned [ShouldaUsedThat](https://github.com/pradeeptathineni/shoulda-used-that/blob/6edaff07d582a2d2d2d06145643f22dbfee3ca0e/docs/architecture/product-contract.md) and [Maestro AI](https://github.com/pradeeptathineni/maestro-ai/blob/f21844f12442c2fefdcf64f737c7423245959457/docs/architecture/reuse-register.md) artifacts. Reviewed 2026-10-05.
- [`providers/openai/signals.yaml`](../providers/openai/signals.yaml) indexes supported Codex and ChatGPT capabilities against their original [OpenAI documentation](https://learn.chatgpt.com/docs/customization/overview). Each entry's `source_refs` resolves to a specific page in `sources.yaml`; capability access and product surfaces must be checked at use time. Reviewed 2026-10-05.
- [`sources.yaml`](../sources.yaml) is the original-source registry for signal entries, with publisher, URL, and review date. It complements this artifact-level influence map and the model-binding sources kept in `models/routing.yaml`. Reviewed 2026-10-05.
- [`docs/concepts-and-signals.md`](concepts-and-signals.md) records this repository's layer and loading decisions, based on the original sources above and the existing context hierarchy. Reviewed 2026-10-05.

- [`.agents/skills/standard/SKILL.md`](../.agents/skills/standard/SKILL.md)
  - [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills) establishes metadata-first discovery, repository and user skill paths, symlink support, and explicit versus implicit invocation. Reviewed 2026-10-05.
  - [OpenAI: Plugins](https://learn.chatgpt.com/docs/plugins) distinguishes local skills from cross-surface plugin distribution; [Hooks](https://learn.chatgpt.com/docs/hooks) documents event checks and tool-coverage limits; [Rules](https://learn.chatgpt.com/docs/agent-configuration/rules) documents command-prefix policies and their matching limits. Reviewed 2026-10-05.
  - [OpenAI: AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [Config basics](https://learn.chatgpt.com/docs/config-file/config-basic), and [Developer commands](https://learn.chatgpt.com/docs/developer-commands) supplied the native owner map. Reviewed 2026-10-05.
  - [OpenAI: Personalize ChatGPT](https://learn.chatgpt.com/docs/personalize), [Projects](https://learn.chatgpt.com/docs/projects), and [Memories](https://learn.chatgpt.com/docs/customization/memories) distinguish durable preferences and project instructions from recall. Reviewed 2026-10-05.
  - The prior-art gate composes [`custom/prior-art.md`](../custom/prior-art.md) with the maintainer's ShouldaUsedThat and Maestro reuse decisions described below. Those decisions justify a check, not mandatory adoption of one tool.

- [`AGENTS.md`](../AGENTS.md)
  - [AGENTS.md open format](https://agents.md/) established plain Markdown, nested scope, and the agent-oriented repository entry point.
  - [OpenAI: Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) informed the small task router, progressive disclosure, and removal of always-read document stacks.
  - [OpenAI Codex's real root `AGENTS.md`](https://github.com/openai/codex/blob/main/AGENTS.md) was inspected as an adopted implementation; its repository-specific detail supported keeping this library's much smaller file proportional to its scope.

- [`core/engineering.md`](../core/engineering.md)
  - [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) supported simple, composable patterns and complexity justified by measured need.
  - [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model) reinforced explicit completion boundaries and verification proportional to the task and model.

- [`core/context.md`](../core/context.md)
  - [Anthropic: Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) supplied the finite attention-budget, high-signal-token, just-in-time retrieval, and context-pollution principles.
  - [Agent Skills specification](https://agentskills.io/specification) demonstrated metadata-first progressive disclosure with instructions and resources loaded on demand.
  - [Model Context Protocol specification](https://modelcontextprotocol.io/specification/2025-06-18) clarified the distinction between context content and a transport for resources, prompts, and tools, including trust boundaries for tool metadata.
  - [`llms.txt` proposal](https://llmstxt.org/) informed machine-readable documentation discovery; it is deferred because this release is a repository rather than a hosted documentation site.

- [`core/compression.md`](../core/compression.md)
  - [Anthropic: Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) informed compaction as a long-horizon context-management technique.
  - [OpenAI API compaction guide](https://developers.openai.com/api/docs/guides/compaction) confirmed compaction as a distinct context operation. The retention checklist and source-to-summary fidelity check are this project's synthesis.

- [`core/development.md`](../core/development.md)
  - [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) informed incremental progress, explicit state, and handoff continuity.
  - [OpenAI: Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) informed proportional task setup, completion criteria, and current-model restraint.

- [`core/research.md`](../core/research.md)
  - [Anthropic: Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) informed just-in-time retrieval and relevance-based context selection.
  - [`llms.txt` proposal](https://llmstxt.org/) informed preference for concise, agent-readable source indexes when authoritative sites publish them.
  - The source hierarchy, licensing gate, fact/inference distinction, and diminishing-return stop rule are project synthesis.

- [`core/testing.md`](../core/testing.md)
  - [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model) informed proportional verification and avoiding unnecessary repeated checks.
  - [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) informed outcome-based checks and matching grader type to behavior.

- [`core/review.md`](../core/review.md)
  - [OpenAI Codex `AGENTS.md` guidance](https://developers.openai.com/codex/guides/agents-md) informed concise, scoped review rules and keeping mechanical formatting in deterministic checks.
  - [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) informed inspecting traces and failures rather than trusting aggregate results alone.

- [`core/benchmarking.md`](../core/benchmarking.md)
  - [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) supplied task/trial/grader/harness distinctions, repeated trials, stable environments, transcript inspection, and combined deterministic/model/human grading.
  - [OpenAI: Working with evals](https://developers.openai.com/api/docs/guides/evals) supported explicit test data, criteria, and repeatable evaluation workflows.

- [`core/versioning.md`](../core/versioning.md)
  - [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) supplied repository release semantics and the separation of a `v`-prefixed Git tag from the semantic version.
  - [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) supplied the human-oriented Unreleased and dated release structure.

### Opinionated custom context

The custom layer is a project-owned synthesis of recurring practice, reviewed on **2026-09-12**. It introduces no volatile external facts and derives its general rules from the canonical files and their sources above.

The additional house files below were reviewed on **2026-10-05**. They distill patterns from the maintainer's own work; a linked project decision shows what informed the guidance, not a claim that the guidance is universally proven.

- [`custom/README.md`](../custom/README.md) applies the progressive-disclosure and authority rules in [`core/context.md`](../core/context.md) to opt-in house standards.
- [`custom/project-intent.md`](../custom/project-intent.md) specializes [`core/engineering.md`](../core/engineering.md) around durable user value, proportional scope, and evidence-qualified claims.
- [`custom/technical-design.md`](../custom/technical-design.md) composes [`core/engineering.md`](../core/engineering.md), [`core/development.md`](../core/development.md), and [`core/testing.md`](../core/testing.md) into a condensed-but-complete design standard.
- [`custom/ai-implementation.md`](../custom/ai-implementation.md) composes engineering, context, testing, and benchmarking guidance into an established-tooling, deterministic-mechanism, then bounded-model decision order.
- [`custom/context-efficiency.md`](../custom/context-efficiency.md) combines [`core/context.md`](../core/context.md), [`core/compression.md`](../core/compression.md), and [`core/benchmarking.md`](../core/benchmarking.md) to minimize total tokens subject to retained outcome quality.
- [`custom/delivery.md`](../custom/delivery.md) specializes development, testing, review, and versioning into an authorized end-to-end implementation, refinement, commit, push, and release loop.
- [`custom/prior-art.md`](../custom/prior-art.md) draws on [ShouldaUsedThat's product contract](https://github.com/pradeeptathineni/shoulda-used-that/blob/6edaff07d582a2d2d2d06145643f22dbfee3ca0e/docs/architecture/product-contract.md), [reuse gate](https://github.com/pradeeptathineni/shoulda-used-that/blob/6edaff07d582a2d2d2d06145643f22dbfee3ca0e/docs/architecture/dogfood-reuse-audit.md), and [Maestro's reuse register](https://github.com/pradeeptathineni/maestro-ai/blob/f21844f12442c2fefdcf64f737c7423245959457/docs/architecture/reuse-register.md). The disposition and stop rules are this library's synthesis.
- [`custom/patterns.md`](../custom/patterns.md) draws on [Maestro ADR-004](https://github.com/pradeeptathineni/maestro-ai/blob/f21844f12442c2fefdcf64f737c7423245959457/docs/architecture/ADR-004-model-led-research.md) for the model/host boundary, [ShouldaUsedThat's reuse gate](https://github.com/pradeeptathineni/shoulda-used-that/blob/6edaff07d582a2d2d2d06145643f22dbfee3ca0e/docs/architecture/dogfood-reuse-audit.md) for a minimal custom residual, and [Blueprint AI's evolution contract](https://github.com/pradeeptathineni/blueprint-ai/blob/64e7603bf3f01af98d82f4dfd6a9829b63cc3c20/docs/evolution.md) for typed postconditions and exact replay.
- [`custom/orchestration.md`](../custom/orchestration.md) uses [OpenAI's Codex subagent guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents) and [Maestro's reuse register](https://github.com/pradeeptathineni/maestro-ai/blob/f21844f12442c2fefdcf64f737c7423245959457/docs/architecture/reuse-register.md) to distinguish useful independent work from unmeasured fanout.
- [`custom/model-deliberation.md`](../custom/model-deliberation.md) uses [OpenAI model selection](https://developers.openai.com/api/docs/guides/model-selection), [reasoning guidance](https://developers.openai.com/api/docs/guides/reasoning), and [Codex model availability](https://learn.chatgpt.com/docs/models). Product access and model rankings are volatile; verify at use time.
- [`custom/writing.md`](../custom/writing.md) combines the maintainer's established voice with [ShouldaUsedThat's public writing loop](https://github.com/pradeeptathineni/shoulda-used-that/blob/6edaff07d582a2d2d2d06145643f22dbfee3ca0e/docs/architecture/public-writing.md), [home-lab's reader-first README](https://github.com/pradeeptathineni/home-lab/blob/7768131dc21f5a3bb1e46aeebce16fe8972cc887/README.md), and [no-ai-slop's editorial guidance](https://github.com/petergyang/no-ai-slop/blob/main/skills/no-ai-slop/SKILL.md). The latter is a writing reference, not an installed quality gate.
- [`custom/code-comments.md`](../custom/code-comments.md) is a maintainer preference synthesized from repeated code-review corrections and language-native documentation practice; it does not disclose private project configuration or impose a comment quota.
- [`custom/evidence-claims.md`](../custom/evidence-claims.md) distills [Maestro's explicit verification limits](https://github.com/pradeeptathineni/maestro-ai/blob/f21844f12442c2fefdcf64f737c7423245959457/docs/architecture/ADR-004-model-led-research.md), [ShouldaUsedThat's source/assessment distinction](https://github.com/pradeeptathineni/shoulda-used-that/blob/6edaff07d582a2d2d2d06145643f22dbfee3ca0e/docs/architecture/product-contract.md), [Labs' plan-versus-work distinction](https://github.com/pradeeptathineni/labs/blob/6037ea6bd0c39f0dd1a2375a4d4250b143bf1e3d/README.md), and the existing testing and benchmarking contexts.

- [`models/routing.yaml`](../models/routing.yaml)
  - [OpenAI API models](https://developers.openai.com/api/docs/models) and [Codex models](https://learn.chatgpt.com/docs/models) were refreshed on 2026-10-05 for current IDs, effort levels, and retirement notices. Codex-Spark retired on 2026-09-14, so the stable `realtime_coding` route now binds to a current focused-work model without promising Spark latency or universal access.
  - The selected GPT-6 Sol binding reflects the Codex app task model list on this host on 2026-10-05. GPT-6.1 Sol has a separate rollout. Recheck product, authentication, workspace, client, and rollout at use time; the dated CLI checks in [`evals/usage-cases.md`](../evals/usage-cases.md) record a rejection on 0.147.0 and successful low-effort runs after updating to 0.160.0.
  - The first-match task taxonomy and logical profiles preserve the repository's original routing design; source metadata and runtime availability checks isolate its volatile bindings.

- [`providers/openai/codex.md`](../providers/openai/codex.md)
  - [OpenAI: Custom instructions with `AGENTS.md`](https://developers.openai.com/codex/guides/agents-md) is authoritative for discovery order, override behavior, closest-scope precedence, session timing, fallback filenames, and the default byte limit. Reviewed 2026-09-12.
  - [OpenAI: Config basics](https://developers.openai.com/codex/config-basic) is authoritative for trusted project configuration and configuration precedence. Reviewed 2026-09-12.
  - [AGENTS.md open format](https://agents.md/) supplied cross-agent scope and plain-Markdown conventions.
  - [OpenAI: Configuration Reference](https://developers.openai.com/codex/config-reference) documents native `model_reasoning_effort`; the discovery and configuration boundaries above were refreshed on 2026-10-05.

- [`docs/adoption.md`](adoption.md)
  - [OpenAI: Custom instructions with `AGENTS.md`](https://developers.openai.com/codex/guides/agents-md) supports the global-to-project loading order, override behavior, and fresh-session activation check. Reviewed 2026-10-05.
  - [OpenAI: Config basics](https://developers.openai.com/codex/config-basic) separates native model and reasoning settings from advisory prompt text. Reviewed 2026-10-05.
  - [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills) supports the repository skill path, user-level symlink, and fresh-session use. Reviewed 2026-10-05.

- [`evals/README.md`](../evals/README.md)
  - [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) informed the baseline/trial/grader protocol, stable environments, outcome grading, trace inspection, and cost/latency capture.
  - [OpenAI: Working with evals](https://developers.openai.com/api/docs/guides/evals) informed the reusable evaluation workflow.
  - The initial scenarios implement the behavioral risks this repository is intended to reduce.
- [`evals/usage-cases.md`](../evals/usage-cases.md) exercises the routes as deterministic expectation cases and records one small fresh-session proxy. The proxy showed file loading and different decision detail, without establishing an improvement.

- [`scripts/lookup.rb`](../scripts/lookup.rb) reads the validated registry and resolves concept-specific signal sources without a new dependency; its output does not assert runtime capability. Reviewed 2026-10-05.
- [`scripts/validate.rb`](../scripts/validate.rb) and [`.github/workflows/validate.yml`](../.github/workflows/validate.yml)
  - [GitHub Actions quickstart](https://docs.github.com/en/actions/get-started/quickstart) supplied the minimal push and pull-request workflow convention.
  - Validation rules come directly from the repository's v0.2.0 integrity contract; the original validator uses Ruby standard libraries; loadout and interchange validation additionally use pinned PyYAML and jsonschema.

## Cross-provider conventions considered

- [Claude Code memory and `CLAUDE.md`](https://code.claude.com/docs/en/memory): hierarchical and on-demand instructions, imports, path-scoped rules, and the distinction between always-loaded context and skills. It also documents importing `AGENTS.md` from `CLAUDE.md` rather than duplicating it.
- [Gemini CLI `GEMINI.md`](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md): global/workspace/just-in-time hierarchy, imports, inspection commands, and configurable context filenames.
- [GitHub Copilot repository instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions-in-your-ide/add-repository-instructions-in-your-ide): repository-wide, path-specific, and agent instruction mechanisms.
- [Agent Skills specification](https://agentskills.io/specification): the format now used for the `standard` backpack. It complements provider-independent canonical context and always-on repository routing.

These sources influenced the layer boundaries and future extension model. Provider adapters for Claude Code, Gemini CLI, and Copilot are intentionally absent until there is a consumer to validate them.

## v1 bootstrap (reviewed 2026-10-05)

`loadouts/standard.yaml`, `loadouts/context-authoring.yaml`, `loadouts/research-evidence.yaml`, `capabilities.yaml`, `decisions/bootstrap.yaml`, `skills/context-loadout/SKILL.md`, `procedures/research-evidence.md`, and `docs/loadouts.md` implement the delivery policy in the user-supplied context-signals-v1-kit. The decision ledger records project policy separately from source-supported interfaces. The frozen `schemas/evidence-bundle-v1.schema.json` is an unchanged kit contract, intended for canonical ownership by Signals; it grants no execution authority.

The research procedure composes `core/research.md` with the MIT-licensed Maestro research skill at producer commit f21844f12442c2fefdcf64f737c7423245959457; it is a summary, not a second research engine. [Producer procedure](https://github.com/pradeeptathineni/maestro-ai/blob/f21844f12442c2fefdcf64f737c7423245959457/.agents/skills/maestro-research/SKILL.md).

[Current Codex models](https://learn.chatgpt.com/docs/models) supports the balanced profile's GPT-6.1 Sol binding and documents Spark retirement. Availability still depends on the account/client. Installed desktop tool metadata exposes that binding here; no inference probe, API entitlement claim, or global settings change was needed.

`.agents/skills/context-loadout/SKILL.md` is a local generated router owned by materialization; the maintained source is `skills/context-loadout/SKILL.md`. It preserves the existing locally installed `standard` skill. `evals/bootstrap-use.json` records a builder-proxy explicit read and actual validator maintenance, not independent compliance or measured token savings.

## v1 modules and selections (reviewed 2026-10-05)

Canonical additions `core/code-comments.md`, `core/version-control.md`, `core/prior-art.md` label source-supported fundamentals and local choices. House guidance now lives in `overlays/`; the previous `custom/` files are compatibility routes. `concepts.yaml` keeps schema-1 string definitions and adds details with module/decision/evidence references. `decisions/adapters.yaml` records tested adapter, tooling and model choices and an immutable D-007 successor.

- `overlays/README.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/ai-implementation.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/code-comments.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/context-efficiency.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/delivery.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/evidence-claims.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/model-deliberation.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/orchestration.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/patterns.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/prior-art.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/project-intent.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/technical-design.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `overlays/writing.md`: the corresponding previously reviewed house policy, moved without semantic rewrite.
- `domains/infrastructure/aws.md`: source links and policy labels are at module level.
- `domains/service/api.md`: source links and policy labels are at module level.
- `domains/web/accessibility.md`: source links and policy labels are at module level.
- `domains/web/browser-verification.md`: source links and policy labels are at module level.
- `domains/web/design.md`: source links and policy labels are at module level.
- `domains/web/performance.md`: source links and policy labels are at module level.
- `domains/web/product-ux.md`: source links and policy labels are at module level.
- `domains/web/react.md`: source links and policy labels are at module level.
- `loadouts/aws-infrastructure.yaml`: declarative project policy selected by the v1 kit, validated with materialized consumer examples.
- `loadouts/context-authoring.yaml`: declarative project policy selected by the v1 kit, validated with materialized consumer examples.
- `loadouts/react-web.yaml`: declarative project policy selected by the v1 kit, validated with materialized consumer examples.
- `loadouts/release-review.yaml`: declarative project policy selected by the v1 kit, validated with materialized consumer examples.
- `loadouts/research-evidence.yaml`: declarative project policy selected by the v1 kit, validated with materialized consumer examples.
- `loadouts/service-api.yaml`: declarative project policy selected by the v1 kit, validated with materialized consumer examples.
- `loadouts/standard.yaml`: declarative project policy selected by the v1 kit, validated with materialized consumer examples.
- `loadouts/web-experience.yaml`: declarative project policy selected by the v1 kit, validated with materialized consumer examples.

`sources.lock.json` is the single authority for snapshot revision, license and exact-file hashes. `procedures/web-design.md` selects an instruction-only Impeccable adapter. Executable launchers, downloads, hooks and extensions were inspected as optional mechanisms and excluded; none was activated. MIT Vercel licensing is declared by the preserved upstream README/skill metadata; Apache notices/terms remain with Impeccable/Anthropic.

Source: [impeccable](https://github.com/pbakaus/impeccable/tree/ece38d9904b8a619b3f77cab476eacad09c4fb11), revision `ece38d9904b8a619b3f77cab476eacad09c4fb11`, Apache-2.0. Inactive documentation snapshots and notices:

- `sourced/impeccable/design/LICENSE`
- `sourced/impeccable/design/NOTICE.md`
- `sourced/impeccable/design/instruction.md`
- `sourced/impeccable/design/reference/adapt.md`
- `sourced/impeccable/design/reference/adapt.native.md`
- `sourced/impeccable/design/reference/android.md`
- `sourced/impeccable/design/reference/animate.md`
- `sourced/impeccable/design/reference/audit.md`
- `sourced/impeccable/design/reference/audit.native.md`
- `sourced/impeccable/design/reference/bolder.md`
- `sourced/impeccable/design/reference/clarify.md`
- `sourced/impeccable/design/reference/colorize.md`
- `sourced/impeccable/design/reference/component-review.md`
- `sourced/impeccable/design/reference/craft-floor.md`
- `sourced/impeccable/design/reference/craft.md`
- `sourced/impeccable/design/reference/critique.md`
- `sourced/impeccable/design/reference/degraded/asset-producer.md`
- `sourced/impeccable/design/reference/degraded/documenter.md`
- `sourced/impeccable/design/reference/degraded/finish-reviewer.md`
- `sourced/impeccable/design/reference/degraded/manual-edit-applier.md`
- `sourced/impeccable/design/reference/delight.md`
- `sourced/impeccable/design/reference/distill.md`
- `sourced/impeccable/design/reference/doctor.md`
- `sourced/impeccable/design/reference/document.md`
- `sourced/impeccable/design/reference/extract.md`
- `sourced/impeccable/design/reference/generate.md`
- `sourced/impeccable/design/reference/harden.md`
- `sourced/impeccable/design/reference/hooks.md`
- `sourced/impeccable/design/reference/init.md`
- `sourced/impeccable/design/reference/ios.md`
- `sourced/impeccable/design/reference/layout.md`
- `sourced/impeccable/design/reference/live-setup.md`
- `sourced/impeccable/design/reference/live.md`
- `sourced/impeccable/design/reference/mode-operate.md`
- `sourced/impeccable/design/reference/mode-persuade.md`
- `sourced/impeccable/design/reference/mode-read.md`
- `sourced/impeccable/design/reference/new-work.md`
- `sourced/impeccable/design/reference/onboard.md`
- `sourced/impeccable/design/reference/operate.md`
- `sourced/impeccable/design/reference/optimize.md`
- `sourced/impeccable/design/reference/overdrive.md`
- `sourced/impeccable/design/reference/polish.md`
- `sourced/impeccable/design/reference/quieter.md`
- `sourced/impeccable/design/reference/region-map.md`
- `sourced/impeccable/design/reference/routing.md`
- `sourced/impeccable/design/reference/shape.md`
- `sourced/impeccable/design/reference/typeset.md`
- `sourced/impeccable/design/reference/visualize.md`

Source: [anthropic](https://github.com/anthropics/skills/tree/683bc88e56f3e09ba94f7055977f3d3aa499f202), revision `683bc88e56f3e09ba94f7055977f3d3aa499f202`, Apache-2.0. Inactive documentation snapshots and notices:

- `sourced/anthropic/design/LICENSE.txt`
- `sourced/anthropic/design/instruction.md`

Source: [vercel](https://github.com/vercel-labs/agent-skills/tree/063bee94c3f4df8453406c830b0a7df0f2860278), revision `063bee94c3f4df8453406c830b0a7df0f2860278`, MIT. Inactive documentation snapshots and notices:

- `sourced/vercel/react/README.md`
- `sourced/vercel/react/compiled-guide.md`
- `sourced/vercel/react/compiled-guide.upstream.txt`
- `sourced/vercel/react/instruction.md`
- `sourced/vercel/react/rules/_sections.md`
- `sourced/vercel/react/rules/_template.md`
- `sourced/vercel/react/rules/advanced-effect-event-deps.md`
- `sourced/vercel/react/rules/advanced-event-handler-refs.md`
- `sourced/vercel/react/rules/advanced-init-once.md`
- `sourced/vercel/react/rules/advanced-use-latest.md`
- `sourced/vercel/react/rules/async-api-routes.md`
- `sourced/vercel/react/rules/async-cheap-condition-before-await.md`
- `sourced/vercel/react/rules/async-defer-await.md`
- `sourced/vercel/react/rules/async-dependencies.md`
- `sourced/vercel/react/rules/async-parallel.md`
- `sourced/vercel/react/rules/async-suspense-boundaries.md`
- `sourced/vercel/react/rules/bundle-analyzable-paths.md`
- `sourced/vercel/react/rules/bundle-barrel-imports.md`
- `sourced/vercel/react/rules/bundle-conditional.md`
- `sourced/vercel/react/rules/bundle-defer-third-party.md`
- `sourced/vercel/react/rules/bundle-dynamic-imports.md`
- `sourced/vercel/react/rules/bundle-preload.md`
- `sourced/vercel/react/rules/client-event-listeners.md`
- `sourced/vercel/react/rules/client-localstorage-schema.md`
- `sourced/vercel/react/rules/client-passive-event-listeners.md`
- `sourced/vercel/react/rules/client-swr-dedup.md`
- `sourced/vercel/react/rules/js-batch-dom-css.md`
- `sourced/vercel/react/rules/js-cache-function-results.md`
- `sourced/vercel/react/rules/js-cache-property-access.md`
- `sourced/vercel/react/rules/js-cache-storage.md`
- `sourced/vercel/react/rules/js-combine-iterations.md`
- `sourced/vercel/react/rules/js-early-exit.md`
- `sourced/vercel/react/rules/js-flatmap-filter.md`
- `sourced/vercel/react/rules/js-hoist-regexp.md`
- `sourced/vercel/react/rules/js-index-maps.md`
- `sourced/vercel/react/rules/js-length-check-first.md`
- `sourced/vercel/react/rules/js-min-max-loop.md`
- `sourced/vercel/react/rules/js-request-idle-callback.md`
- `sourced/vercel/react/rules/js-set-map-lookups.md`
- `sourced/vercel/react/rules/js-tosorted-immutable.md`
- `sourced/vercel/react/rules/rendering-activity.md`
- `sourced/vercel/react/rules/rendering-animate-svg-wrapper.md`
- `sourced/vercel/react/rules/rendering-conditional-render.md`
- `sourced/vercel/react/rules/rendering-content-visibility.md`
- `sourced/vercel/react/rules/rendering-hoist-jsx.md`
- `sourced/vercel/react/rules/rendering-hydration-no-flicker.md`
- `sourced/vercel/react/rules/rendering-hydration-suppress-warning.md`
- `sourced/vercel/react/rules/rendering-resource-hints.md`
- `sourced/vercel/react/rules/rendering-script-defer-async.md`
- `sourced/vercel/react/rules/rendering-svg-precision.md`
- `sourced/vercel/react/rules/rendering-usetransition-loading.md`
- `sourced/vercel/react/rules/rerender-defer-reads.md`
- `sourced/vercel/react/rules/rerender-dependencies.md`
- `sourced/vercel/react/rules/rerender-derived-state-no-effect.md`
- `sourced/vercel/react/rules/rerender-derived-state.md`
- `sourced/vercel/react/rules/rerender-functional-setstate.md`
- `sourced/vercel/react/rules/rerender-lazy-state-init.md`
- `sourced/vercel/react/rules/rerender-memo-with-default-value.md`
- `sourced/vercel/react/rules/rerender-memo.md`
- `sourced/vercel/react/rules/rerender-move-effect-to-event.md`
- `sourced/vercel/react/rules/rerender-no-inline-components.md`
- `sourced/vercel/react/rules/rerender-simple-expression-in-memo.md`
- `sourced/vercel/react/rules/rerender-split-combined-hooks.md`
- `sourced/vercel/react/rules/rerender-transitions.md`
- `sourced/vercel/react/rules/rerender-use-deferred-value.md`
- `sourced/vercel/react/rules/rerender-use-ref-transient-values.md`
- `sourced/vercel/react/rules/server-after-nonblocking.md`
- `sourced/vercel/react/rules/server-auth-actions.md`
- `sourced/vercel/react/rules/server-cache-lru.md`
- `sourced/vercel/react/rules/server-cache-react.md`
- `sourced/vercel/react/rules/server-dedup-props.md`
- `sourced/vercel/react/rules/server-hoist-static-io.md`
- `sourced/vercel/react/rules/server-no-shared-module-state.md`
- `sourced/vercel/react/rules/server-parallel-fetching.md`
- `sourced/vercel/react/rules/server-parallel-nested-fetching.md`
- `sourced/vercel/react/rules/server-serialization.md`
- `sourced/vercel/react/upstream-README.md`
- `sourced/vercel/web/instruction.md`
- `sourced/vercel/web/upstream-README.md`

Ruler fit check used npm `@intellectronica/ruler@0.3.44` with install scripts disabled and `--agents codex --no-mcp --no-gitignore --no-skills --local-only`, first dry-run then apply in a disposable repository. It regenerated AGENTS and preserved the original in its generated output; the evidence/ownership remainder still belongs to Context. No multi-provider replication, general runtime or compressor was adopted.

`evals/web-exercise.json`, `evals/verification-stage-use.json`, `evals/v1-acceptance.md`, and `examples/web/brief.md` record local fixture/browser observations and policy, with the source pins above. `docs/compatibility.md` documents the schema/path migration contract. PyYAML and jsonschema are explicit maintained parsing/validation dependencies; `requirements.txt` retains exact PyPI artifact hashes. Browser development dependencies and transitive integrity values are in package-lock.json. No upstream installer is executed by the delivered loadout command.

Pinned upstream text retains its original whitespace, including Markdown hard breaks and blank EOF lines. `.gitattributes` exempts only `sourced/` from those two whitespace checks; authored content keeps normal checks and source hashes remain enforced.

`evals/signals-evidence.bundle.json` preserves the real agent-assisted Signals export, exact SHA-256 62e5cb9a6d825a1d5194a28035640b248ee05e344bb41fd816355c1a378cb8da, from `pradeeptathineni/signals-ai` commit 4ab32a1d7ae09ae0ebb6102b4b2d7571291c5c97. `evals/signals-roundtrip.json` maps its ten candidates/claim IDs to Context decisions without activation; `decisions/peer.yaml` appends the evidence-bound D-005 successor. These are source summaries/advice and actual interchange observations, not model-led or independent benefit measurements.

## Responsibility reconsideration

`core/prior-art.md` and `skills/pact-hrr/SKILL.md` adapt the maintainer-supplied PACT/HRR playbook, reviewed 2026-10-05. The canonical workflow owns comparison, use and revision; the skill is a router. [Agent Skills](https://agentskills.io/specification) and [OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills) support metadata-first, on-demand procedures, reviewed 2026-10-05. This is direct source inspection, not native discovery or evidence of efficiency.

`resources.yaml` declares runtime prerequisites independently of informational Markdown navigation. `tests/test_resources.py` demonstrates the former implicit instruction inclusion and the corrected closure, including dependency cycles, missing files, path escape and notice retention. Reviewed 2026-10-05; installed bytes and actual loaded input remain separate measurements.

`procedures/react-review.md` adapts pinned Vercel navigation to the installed compiled guide; framework-specific advice remains conditional. The focused closure review identified and corrected Mac filename casing and missing React/design routes. Reviewed 2026-10-05.

`decisions/composition.yaml` records measured closure choices, including the precise supported packaging/React claims in the verified Signals successor at `ee4aea154c461aaa8f9f0cbb770240c28c19dde7`. Those source claims do not prove local efficiency.
