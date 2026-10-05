# Code comments and API documentation

Use with [development](../core/development.md) and the target repository's language conventions when changing code comments or public documentation. Repository policy can choose no new comments for a scoped task; preserve existing comments unless the requested change makes them wrong.

## Document meaning, not syntax

Comment non-obvious intent, invariants, tradeoffs, safety and permission boundaries, edge cases, surprising side effects, and caller-visible contracts. A comment should answer a question a future maintainer cannot settle quickly from the code. Prefer clearer names and structure when those remove the need for explanation. Delete stale or redundant comments while changing the affected code.

Do not comment every declaration, paraphrase a method name, narrate a loop, repeat a type signature, or use a target comment count. A request for thorough documentation means inspect the full surface for justified gaps, not add a line to each method. Prefer one short semantic thought per line. For ordinary internal comments, use the repository's compact style; the user's preferred default is simple, lowercase wording without terminal punctuation.

Language-native API rules win where they carry contract value. For example, exported Go symbols require symbol-leading complete-sentence documentation when the project exposes them; relevant parameters, results, errors, and side effects should be clear without generic tag boilerplate. Python docstrings or another language's conventions should similarly follow the existing public API style. Do not force the informal internal-comment style into formal API documentation.

Before accepting a comment, ask whether it remains true under the important failure path and whether a test, type, schema, or ADR is the better authority for an exact rule. Comments can explain *why* an invariant exists; executable checks should enforce it.
