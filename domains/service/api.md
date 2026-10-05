# Service API implementation

Compose core development/testing with the current API contract. Detect the actual stack; where present use TypeScript, Fastify, TypeBox and PostgreSQL mechanisms already owned by the project. These are applicability choices, not mandatory dependencies for every API.

Validate inputs at trust boundaries; make error/status contracts explicit. Test auth/scope isolation, invalid inputs, alternate writers, persistence invariants, concurrency and failure recovery where consequential. Inspect transitive test effects and use named disposable databases for migrations/destructive checks. Never reset retained state.

Keep logging useful for diagnosis without credentials/private payloads. Define timeout/retry ownership, transaction boundaries and idempotency when writes demand them. Exercise a real route and storage boundary; fixtures cannot certify configured production behavior.

Source-supported interfaces: [Fastify validation](https://fastify.dev/docs/latest/Reference/Validation-and-Serialization/) and [PostgreSQL transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html). Reviewed 2026-10-05; match version at use.
