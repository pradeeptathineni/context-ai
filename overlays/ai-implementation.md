# AI implementation

Use with [`core/engineering.md`](../core/engineering.md), [`core/context.md`](../core/context.md), [`core/testing.md`](../core/testing.md), and [`core/benchmarking.md`](../core/benchmarking.md).

## Use the mechanism ladder

Choose the lowest layer that reliably solves each part of the problem:

1. Reuse a fitting standard, protocol, maintained tool, or established project pattern.
2. Use deterministic code for exact, repeatable, enumerable, policy-bound, or mechanically verifiable work.
3. Retrieve current evidence when the needed fact is missing or volatile.
4. Use a model for semantic interpretation, synthesis, generation, ranking, or judgment that materially benefits from learned behavior.
5. Add multi-step agents, orchestration, or model-to-model delegation only when a simpler bounded model call cannot deliver the required outcome.

Do not use a model to imitate a parser, database constraint, state machine, permission check, checksum, schema validator, or other reliable mechanism already available.

## Bound the model's role

- Give the model a clear objective, authoritative context, typed or otherwise verifiable inputs and outputs, available actions, budget, and stopping condition.
- Keep credentials, permissions, durable state, exact transformations, retries, idempotency, and acceptance checks under deterministic host control.
- Treat model output as untrusted until the owning layer validates it. Constrain effects separately from the freedom to reason.
- Separate orchestration from intelligence so model, provider, prompt, and tool choices can change without rewriting the system contract.
- Provide a deterministic fallback or a clear failure when the model is unavailable, uncertain, invalid, or outside its authority.

## Establish evidence

- Start with a non-model or simpler-model baseline when practical. Prove that the model improves an outcome that matters.
- Evaluate representative successes, boundaries, and failures with deterministic graders where possible and bounded human or model judgment where necessary.
- Record the model and provider surface, reasoning level, context, tools, inputs, date, latency, tokens, cost, and relevant variability for consequential claims.
- Monitor decisions and failures that can drive an action. Do not collect traces without a retention, privacy, or operational purpose.
- Never present a mocked, cached, local-only, or single-run result as live production evidence.

The preferred AI system is mostly understandable software with a narrow, explicit place for model judgment.
