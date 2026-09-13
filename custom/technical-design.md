# Technical design

Use with [`core/engineering.md`](../core/engineering.md), [`core/development.md`](../core/development.md), and [`core/testing.md`](../core/testing.md).

## Build the simplest complete system

- Define the observable contract first: inputs, outputs, state, ownership, failure behavior, security boundaries, and compatibility obligations.
- Implement the least complicated design that satisfies that contract end to end. Fewer parts are useful only when no required behavior disappears.
- Keep code, configuration, documentation, and context condensed but complete. Remove duplication and ceremony before removing meaning or safeguards.
- Make the main path obvious and important boundaries explicit. Handle a failure in the layer that owns the state or recovery decision.
- Prefer cohesive components, narrow interfaces, one canonical representation, and changes that can be reviewed and reversed.

## Choose mechanisms in order

1. Inspect and reuse sound repository patterns, components, and data.
2. Prefer relevant standards and well-maintained ecosystem tooling when their fit, interoperability, security, license, and operating cost are verified.
3. Use language and platform primitives or a small deterministic implementation when they meet the contract more clearly.
4. Add a dependency, service, abstraction, or extension point only for a demonstrated present need.
5. Introduce model-driven or agentic behavior only where semantic judgment creates value that deterministic machinery cannot provide well; follow [`ai-implementation.md`](ai-implementation.md).

Popularity is useful evidence of adoption and interoperability, not proof that a tool fits the project.

## Finish the boundary

- Cover the meaningful path across interfaces, persistence, errors, permissions, user feedback, operations, and documentation where each exists.
- Prefer deterministic validation and actionable failures over implicit behavior.
- Add observability only when it supports a concrete detection, diagnosis, or recovery decision.
- Measure representative behavior before optimizing. Include maintenance, dependency, context, inference, and operator costs in the result.
- Remove obsolete paths when compatibility permits; do not preserve accidental complexity as architecture.

Technical quality is compact sufficiency: every retained part earns its cost, and every required behavior has an accountable home.
