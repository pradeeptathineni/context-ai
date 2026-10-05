# References and provenance

## Sourcing policy

Prefer authoritative specifications, then first-party product documentation, then maintained and adopted open-source implementations, then high-quality engineering publications. Use synthesis only where those sources do not settle the repository's design. Adoption informs interoperability; it does not replace evidence.

External material is summarized and linked unless a pinned local copy has clear maintenance value and redistribution is permitted. A vendored artifact must record its local path, upstream URL, revision or tag, license, and review date, and must remain distinct from canonical adaptations. Volatile provider and model facts are reviewed against the product surface that consumes them.

All external sources below were reviewed on **2026-09-12** unless another date is shown. No upstream artifacts are vendored in v0.2.0, so no `sourced/` directory exists.

## Repository context and configuration map

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

- [`evals/README.md`](../evals/README.md)
  - [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) informed the baseline/trial/grader protocol, stable environments, outcome grading, trace inspection, and cost/latency capture.
  - [OpenAI: Working with evals](https://developers.openai.com/api/docs/guides/evals) informed the reusable evaluation workflow.
  - The initial scenarios implement the behavioral risks this repository is intended to reduce.
- [`evals/usage-cases.md`](../evals/usage-cases.md) exercises the routes as deterministic expectation cases and records one small fresh-session proxy. The proxy showed file loading and different decision detail, without establishing an improvement.

- [`scripts/validate.rb`](../scripts/validate.rb) and [`.github/workflows/validate.yml`](../.github/workflows/validate.yml)
  - [GitHub Actions quickstart](https://docs.github.com/en/actions/get-started/quickstart) supplied the minimal push and pull-request workflow convention.
  - Validation rules come directly from the repository's v0.2.0 integrity contract; no third-party validation framework is used.

## Cross-provider conventions considered

- [Claude Code memory and `CLAUDE.md`](https://code.claude.com/docs/en/memory): hierarchical and on-demand instructions, imports, path-scoped rules, and the distinction between always-loaded context and skills. It also documents importing `AGENTS.md` from `CLAUDE.md` rather than duplicating it.
- [Gemini CLI `GEMINI.md`](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md): global/workspace/just-in-time hierarchy, imports, inspection commands, and configurable context filenames.
- [GitHub Copilot repository instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions-in-your-ide/add-repository-instructions-in-your-ide): repository-wide, path-specific, and agent instruction mechanisms.
- [Agent Skills specification](https://agentskills.io/specification): a plausible future packaging target for specialized on-demand workflows, not a replacement for provider-independent canonical context or always-on repository routing.

These sources influenced the layer boundaries and future extension model. Provider adapters for Claude Code, Gemini CLI, and Copilot are intentionally absent until there is a consumer to validate them.
