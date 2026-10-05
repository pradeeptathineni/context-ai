# Model and reasoning deliberation

Use with [benchmarking](../core/benchmarking.md) and [model routing](../models/routing.yaml) when a task, automation, or new session needs a model and reasoning setting. This is decision guidance; the active host controls which settings can actually be selected.

## Choose the work profile first

Describe the task by consequence, ambiguity, scope, autonomy, interactivity, and whether acceptance criteria are explicit. Prefer deterministic tooling for exact work. For model work, start with the least capable profile likely to finish correctly, then check the currently available provider binding and reasoning levels. Do not treat a dated model catalog as proof of access on this client or account.

| Work | Starting point | Raise when |
| --- | --- | --- |
| Extraction, formatting, narrow edit | efficient model; low effort | correctness fails on representative input |
| Normal implementation or researched writing | balanced model; medium effort | architecture, evidence, or requirements remain unsettled |
| Cross-cutting design, hard debugging, high-consequence review | strongest suitable model; high effort | multiple hard tradeoffs remain after evidence gathering |
| Exceptional single hard problem | strongest suitable model; extra high or max where supported | a cheaper setting demonstrably misses necessary reasoning |
| Independent parallel work | separate agents only when [orchestration](orchestration.md) fits | the work divides into bounded independent tasks |

Task length alone does not justify high reasoning. A long run of clear edits may need persistence and checks more than deeper deliberation. Conversely, a short data-loss or security decision can warrant high effort. After isolating the difficult part, lower effort for bounded implementation or validation. After two unproductive attempts, stop, inspect the failure, and reframe before spending more compute.

Treat Ultra, where a host offers it, as parallel subagent work rather than a deeper setting for one thinker. Use it only when the work genuinely divides and the session permits delegation.

## Keep selection honest

The task's model, reasoning, tools, context, and harness form one evaluated configuration. Compare representative outcomes, retries, latency, token use, and cost per successful task before making a permanent default. Keep route meaning stable while provider IDs change. Explicit user choices and current session settings take precedence over an advisory route. Never claim that a prompt tag changed an active conversation's model or effort; use the product's actual control or a new session. Do not silently escalate cost, autonomy, or reasoning on behalf of an ambiguous recommendation.
