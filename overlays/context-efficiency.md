# Context efficiency

Use with [`core/context.md`](../core/context.md), [`core/compression.md`](../core/compression.md), and [`core/benchmarking.md`](../core/benchmarking.md).

Minimize the total tokens needed to reach a correct, verified outcome without lowering the quality bar. The smallest prompt is not efficient when it causes wrong decisions, repeated discovery, retries, or avoidable review.

## Spend attention deliberately

- Always preserve the objective, acceptance criteria, authority, non-obvious constraints, current state, unresolved work, material risks, and continuation identifiers.
- Remove generic knowledge, duplicated rules, narrative history, stale state, and raw output after its useful evidence has been extracted.
- Use progressive disclosure: a small router first, task context next, target files and evidence only when a decision needs them.
- Search narrowly and bound excerpts. Prefer precise paths, symbols, structured summaries, and references to canonical sources over large undifferentiated inputs.
- Keep requests and responses direct. Put exact reusable facts in structure; reserve prose for meaning, rationale, ambiguity, and tradeoffs.

## Optimize the whole task

1. Establish a quality baseline and measure tokens, latency, cost, retries, and outcome when the decision warrants measurement.
2. Remove repetition and boilerplate while retaining the items protected by the compression fidelity check.
3. Move stable, exact, repeated work into deterministic routing, retrieval, validation, or transformation.
4. Match model capability and reasoning to the hardest unresolved part, then de-escalate for bounded mechanical work.
5. Reuse stable context or verified intermediate artifacts when freshness, privacy, and cache semantics allow it.
6. Compress at natural phase boundaries and stop when the requested outcome and evidence are complete.

## Protect quality

- Do not trade away correctness, security, provenance, required nuance, or failure handling to hit a token target.
- Test reduced context on representative work; compare requirement retention and decisions, not merely output style.
- Restore context when failures show that a removed detail changes behavior materially.
- Treat token count as one system metric alongside success rate, latency, monetary cost, maintainability, and human review effort.

Efficient context contains no token that fails to help, and lacks no token whose absence would predictably compromise the result.
