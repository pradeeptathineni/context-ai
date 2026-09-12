# Context compression

Compression reduces context cost while preserving the information needed to continue correctly. Reduce wording before reducing meaning.

## Preserve

- requirements and acceptance criteria
- decisions and rationale that constrain future choices
- invariants, risks, exceptions, and safety boundaries
- verified facts and material provenance
- current state, completed work, and unresolved work
- failures, attempted remedies, and evidence needed to avoid repeating them
- identifiers, paths, commands, versions, links, and owners needed to continue

When loss would be costly, favor recall first. Remove additional noise only after required information is demonstrably retained.

## Remove

- repetition and restatements
- obsolete intermediate reasoning
- superseded plans or state, while preserving why a consequential decision changed
- irrelevant conversation and social filler
- raw tool output after its useful evidence has been extracted
- detail the next actor can reproduce cheaply and reliably

## Workflow

1. Identify the next decisions and actions the compressed context must support.
2. Inventory requirements, decisions, exceptions, unresolved items, and continuation references.
3. Group related facts and replace repeated narrative with direct statements.
4. Mark uncertainty instead of converting it into fact.
5. Compare the result with the source, then remove remaining wording that does not affect behavior.

## Fidelity check

Build a lightweight retention table with one row per source requirement, decision, exception, unresolved item, or critical identifier. Mark where each appears in the compressed result. Any missing item is either restored or explicitly judged irrelevant to continuation.

For high-consequence compression, give the same representative continuation question or task to the source and compressed contexts. Compare required actions, constraints, decisions, and failure handling—not stylistic similarity. Record intentional differences. A shorter summary is not successful if it changes the behavior that matters.
