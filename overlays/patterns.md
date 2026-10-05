# Pattern selection

Use with [technical design](technical-design.md), [AI implementation](ai-implementation.md), and [prior art](prior-art.md) when choosing an implementation pattern. These are options to assess against a real contract, not a checklist to instantiate.

## Start from ownership

Identify who owns each fact, decision, state transition, external effect, and failure recovery. Keep one authoritative representation; other formats and views should be derived or validated. Separate a pure calculation from I/O when replay, testing, or multiple adapters actually need the boundary. Use an explicit state machine for consequential transitions or uncertain effects; a simple function suffices for a simple transform.

For durable evidence, preserve source identity, observation time, method, applicability, and revision. Corrections should supersede retained decisions when history matters. If a source fails, keep the last known good observation distinguishable from a fresh successful check. A timestamp change, repeated report, or popularity change does not automatically become a material decision change.

Place permissions, exact validation, credentials, retries, idempotency, and postconditions with the deterministic host. Give each asynchronous effect one retry owner and a way to distinguish requested, attempted, observed, and confirmed states. Choose an outbox, queue, or workflow engine only when the existing platform cannot meet the actual delivery and recovery contract. Do not build a generic agent runtime to connect a few known steps.

For a planned mutation or migration, make expected writes and typed postconditions inspectable before execution. Verify the final state independently, test a no-op replay when idempotence matters, and define rollback for the files or state the operation actually owns. A successful command exit is only one observation.

## Check the alternatives

Before introducing a new layer, compare:

1. current repository code and configuration;
2. language or platform primitives;
3. a standard or existing maintained component behind a narrow interface;
4. a small project-specific implementation;
5. a model or multi-agent step for semantic work that remains open ended.

Use a pattern because it removes a demonstrated failure or makes a needed capability simpler to operate. Do not add speculative adapters, registries, taxonomies, caches, or abstraction hierarchies for imagined consumers. Measure a proposed optimization on a representative task before accepting its maintenance cost. Record the selected boundary and revisit trigger in the project's existing decision mechanism.
