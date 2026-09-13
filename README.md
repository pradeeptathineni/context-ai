# context-ai

Reusable AI context engineering.

`context-ai` is a small standard library of context that otherwise gets recreated across projects, agents, and providers. It favors concise, reviewable guidance over monolithic prompts and keeps durable behavior separate from model data, provider mechanics, and evidence.

## What lives where

- [`core/`](core/) contains provider-independent behavioral context. Load only the files relevant to the task.
- [`custom/`](custom/) contains opt-in, opinionated project standards that compose and specialize the canonical core.
- [`models/routing.yaml`](models/routing.yaml) is a machine-readable policy for selecting a model profile and reasoning level from task attributes.
- [`providers/`](providers/) contains product-specific adapters: discovery, scope, precedence, configuration, and consumption guidance.
- [`evals/`](evals/) defines how context quality can be compared without putting nondeterministic model calls in CI.
- A nested `sourced/` directory may hold a pinned, redistributable upstream artifact when a local snapshot has clear value. None are included in v0.2.0.
- [`docs/references.md`](docs/references.md) maps maintained artifacts to the sources that materially shaped them.

Markdown is used for instructions people and models should read naturally. YAML is used where consumers need stable fields, validation, and routing logic. Provider adapters reference canonical context instead of copying it.

## Use it

Read the smallest useful set of files. For example, an engineering task might use:

```text
core/engineering.md
core/development.md
core/testing.md
```

A project using Codex can route from its `AGENTS.md` without embedding the full library:

```markdown
For substantial changes, read the project's copies of `core/engineering.md`
and `core/context.md`. For implementation, also read `core/development.md`
and `core/testing.md`.
```

An integration can evaluate task attributes against `models/routing.yaml`, select the first matching route, and resolve its logical profile to a current provider model. Callers should depend on route and profile names rather than scattering model IDs.

See [`providers/openai/codex.md`](providers/openai/codex.md) for Codex-specific instruction discovery and configuration behavior.

Projects that adopt the opinionated layer should select from [`custom/README.md`](custom/README.md), not load the directory wholesale. For example, an AI implementation may add `custom/ai-implementation.md`; add `custom/delivery.md` when the task needs the full implementation-to-integration loop or includes publication or release.

## Design

Context is a finite attention budget. Start with small, always-relevant instructions; retrieve task-specific context just in time; and load provider guidance only for that provider. Preserve project facts, decisions, and non-obvious constraints. Avoid repeating generic knowledge a capable model already has.

The five layers have different change pressures:

1. Canonical context changes when durable guidance improves.
2. Custom context changes when repeated project practice justifies an opinionated specialization.
3. Structured configuration changes when a machine-readable contract or binding changes.
4. Provider adapters change with product behavior.
5. References and evaluations show why an artifact exists and whether it still works.

This separation lets model and provider facts evolve without rewriting the behavioral library.

## v0.2.0 scope

This release adds five custom contexts for project intent, technical design, AI implementation, context efficiency, and complete delivery, plus a small router for selective use. The nine canonical core contexts, OpenAI model-routing policy, Codex adapter, provenance map, deterministic validation, and evaluation protocol remain intact. Custom guidance stays a delta from canonical context and composes references rather than copying content. Additional providers, Agent Skills packaging, `llms.txt`, and automated model-graded evals wait for a real consumer or evidence that they improve outcomes.

Run validation with:

```sh
ruby scripts/validate.rb
git diff --check
```

Releases follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html); notable changes are recorded in [`CHANGELOG.md`](CHANGELOG.md). See [`docs/references.md`](docs/references.md) for the sourcing policy and review dates.

## License

[MIT](LICENSE)
