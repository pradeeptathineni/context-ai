# Custom project standards

`custom/` contains the maintainer's opinionated practice distilled from repeated work. A personal entry point can make its relevant files defaults across projects; another project can adopt selected files. [`core/`](../core/) remains the canonical, broadly reusable layer. These files compose its general rules into a house style without replacing a project's own contract.

## Load by need

- Use [`project-intent.md`](project-intent.md) to establish value, priorities, scope, and honest claims.
- Use [`technical-design.md`](technical-design.md) for the simplest complete architecture and implementation boundary.
- Use [`ai-implementation.md`](ai-implementation.md) when deciding what established tooling, deterministic code, and models should each own.
- Use [`context-efficiency.md`](context-efficiency.md) when reducing context, token use, latency, or model cost without lowering the quality bar.
- Use [`delivery.md`](delivery.md) when a task includes implementation through review, refinement, version control, publication, or release.
- Use [`prior-art.md`](prior-art.md) before choosing a substantial new capability, dependency, protocol, service, or development tool.
- Use [`patterns.md`](patterns.md) when deciding ownership, state, effects, or whether an architectural pattern earns its cost.
- Use [`orchestration.md`](orchestration.md) when considering separate agents, specialist roles, or an independent review.
- Use [`model-deliberation.md`](model-deliberation.md) when choosing a model, reasoning level, or escalation path for a new run.
- Use [`writing.md`](writing.md) for voice, reader-first explanations, editing, and anti-slop review.
- Use [`code-comments.md`](code-comments.md) when changing comments, docstrings, or public API documentation.
- Use [`evidence-claims.md`](evidence-claims.md) when reporting tests, live behavior, benchmarks, reviews, or releases.

Do not load the whole directory by default. Start with the smallest relevant combination and retrieve another file only when the task reaches its decision boundary.

For a substantial new build, `prior-art.md` and `patterns.md` are the usual pair. For a normal code fix, the repository's own instructions and relevant core files may be enough. These routes are defaults for consideration, not permission to override a project's explicit contract.

## Composition and authority

- Apply explicit task requirements and the consuming project's scoped instructions first.
- Treat these files as specializations of the linked core contexts, not replacements for correctness, safety, testing, review, or versioning rules.
- Reference canonical guidance instead of copying it into a project-specific variant. Keep local exceptions as small deltas with an owner or rationale.
- Resolve a real conflict explicitly. Do not silently combine incompatible rules or let an aspirational preference override an observable contract.
- Evaluate useful file combinations against no-context and core-only baselines before making them always-on context.

The objective is consistent judgment with little context: enough shared preference to avoid relearning the same lessons, without turning project history into a monolithic prompt.
