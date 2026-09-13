# Custom project standards

`custom/` contains opt-in, opinionated project practice distilled from repeated work. [`core/`](../core/) remains the canonical, broadly reusable layer; these files compose its general rules into a house style for projects that choose it.

## Load by need

- Use [`project-intent.md`](project-intent.md) to establish value, priorities, scope, and honest claims.
- Use [`technical-design.md`](technical-design.md) for the simplest complete architecture and implementation boundary.
- Use [`ai-implementation.md`](ai-implementation.md) when deciding what established tooling, deterministic code, and models should each own.
- Use [`context-efficiency.md`](context-efficiency.md) when reducing context, token use, latency, or model cost without lowering the quality bar.
- Use [`delivery.md`](delivery.md) when a task includes implementation through review, refinement, version control, publication, or release.

Do not load the whole directory by default. Start with the smallest relevant combination and retrieve another file only when the task reaches its decision boundary.

## Composition and authority

- Apply explicit task requirements and the consuming project's scoped instructions first.
- Treat these files as specializations of the linked core contexts, not replacements for correctness, safety, testing, review, or versioning rules.
- Reference canonical guidance instead of copying it into a project-specific variant. Keep local exceptions as small deltas with an owner or rationale.
- Resolve a real conflict explicitly. Do not silently combine incompatible rules or let an aspirational preference override an observable contract.
- Evaluate useful file combinations against no-context and core-only baselines before making them always-on context.

The objective is consistent judgment with little context: enough shared preference to avoid relearning the same lessons, without turning project history into a monolithic prompt.
