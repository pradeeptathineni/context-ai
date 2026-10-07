# Test-first loop

Use when a feature or bug fix has a stable public seam that a failing test can pin. Skip for exploratory spikes, pure configuration, prose, or a change whose behavior the project cannot exercise locally. [Testing](../core/testing.md) owns what evidence is sufficient; this procedure owns only the red-green loop.

Follow Matt Pocock's pinned [TDD skill](../sourced/mattpocock/tdd/instruction.md) with its [test examples](../sourced/mattpocock/tdd/tests.md) and [mocking guidance](../sourced/mattpocock/tdd/mocking.md), with these Context deltas:

- Seams come from the stated requirements, existing tests and public interfaces. Ask the user only when the seam is genuinely unresolved; never re-interview requirements already supplied.
- Where the upstream names its `codebase-design` skill, use [technical design](../overlays/technical-design.md) instead. Read a project `GLOSSARY.md` and ADRs when they exist.
- Use the project's existing test runner and file layout. Do not add a framework to perform the loop.
- Show the new test failing for the intended reason before the implementation, then passing. Report both commands and results.
- Refactoring belongs to [review](review.md), after green.
