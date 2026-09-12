# Engineering judgment

## Choose the solution

- Satisfy the actual requirements and constraints before optimizing elegance.
- Prefer the simplest complete solution. Simplicity that omits necessary behavior is incompleteness.
- Put correctness, safety, and recoverability before cleverness.
- Inspect and reuse sound existing code, data, standards, and tooling before rebuilding them.
- Prefer established modern standards when they fit. Weigh authority, adoption, maintenance, interoperability, and evidence rather than popularity alone.
- Add a dependency only when its verified benefit exceeds its operational, security, upgrade, and learning costs.
- Introduce an abstraction after repeated structure or a clear boundary demonstrates its value. Do not build extension points for imagined consumers.

## Shape the system

- Keep architecture proportionate to current scale, risk, and change rate.
- Maintain one canonical representation of each rule or fact. Derive or reference other views.
- Make control flow, data ownership, failure behavior, and compatibility boundaries easy to trace.
- Keep modules cohesive and interfaces smaller than their implementations require.
- Preserve useful history and local conventions unless changing them has a concrete benefit.
- Design changes to be reviewable and reversible when practical.

## Operate and decide

- Add observability where it helps detect, explain, or recover from meaningful failures. Avoid telemetry without a decision or operator behind it.
- State material tradeoffs and assumptions. Distinguish evidence from judgment.
- Resolve uncertainty in proportion to consequence: test, measure, research, or prototype only when the result can change the decision.
- Optimize after measuring a representative workload. Do not trade maintainability for hypothetical performance.
- Remove obsolete paths and accidental complexity when the migration cost and compatibility contract allow it.

The goal is not the fewest lines or the most flexible design. It is the least complicated system that reliably delivers the required value.
