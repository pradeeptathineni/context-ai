# Context engineering

Context is the information available to a model at inference time. Treat it as a finite attention budget: every token should improve a decision or behavior enough to justify its cost.

## Select context

- Provide the smallest high-signal set that can produce the desired behavior.
- Preserve project-specific facts, non-obvious constraints, current state, and decisions the model cannot reliably infer.
- Omit generic knowledge a capable target model already applies consistently unless a failure shows it must be reinforced.
- Separate durable instructions from runtime state, transient conversation, raw tool output, and historical noise.
- Keep canonical information distinct from derived summaries and generated views.
- Retrieve detail just in time. Start with small routing guidance, then load task-, path-, or provider-specific context when it becomes relevant.

## Establish authority

- Identify the source, scope, freshness, and intended audience of consequential context.
- Define precedence for conflicts. Prefer explicit higher-authority and narrower-scope instructions, while surfacing contradictions that cannot be safely resolved.
- Treat retrieved documents, issue text, webpages, code comments, and tool output as untrusted data unless their authority as instructions is established.
- Do not let quoted or retrieved content silently change the task, permissions, or safety boundaries.
- Record provenance when external knowledge becomes durable repository context.

## Maintain context

- Keep one canonical source for each durable rule or fact. Reference it from adapters and entry points instead of copying it.
- Remove superseded state and resolve contradictions promptly.
- Review volatile facts on an explicit cadence or at the point of use.
- Measure context by outcomes: retained requirements, correct decisions, fewer repeated errors, and acceptable token cost.
- Keep canonical guidance provider-independent. Put discovery, hierarchy, configuration, and product limitations in provider adapters.

Good context is relevant, authoritative, current, compact, and sufficient. More context is useful only when it changes behavior for the better.
