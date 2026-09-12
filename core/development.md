# Development workflow

Use the lightest version of this loop that matches the change:

`Understand -> Research when needed -> Implement -> Validate -> Inspect -> Review -> Refine -> Re-validate -> Document and version`

## Understand

- Inspect the actual repository, instructions, working tree, and relevant history before assuming structure or behavior.
- Trace the affected architecture, data flow, state transitions, interfaces, and consumers far enough to identify the real change boundary.
- Clarify observable acceptance criteria and consequential constraints. Avoid heavyweight planning for a trivial edit.

## Research and implement

- Research when current facts, unfamiliar interfaces, standards, security, licensing, or unresolved design choices can affect correctness.
- Implement the smallest complete change consistent with the existing design.
- Preserve unrelated work and avoid opportunistic scope expansion.
- Handle meaningful boundaries and failures at the layer that owns them.

## Validate and inspect

- Run checks proportional to scope and risk; follow [`testing.md`](testing.md).
- Inspect representative real outputs or runtime behavior when static checks cannot establish correctness.
- Check for bugs, regressions, security or privacy issues, leaks, edge cases, limitations, poor failure behavior, false positives, false negatives, and unnecessary complexity.

## Review and finish

- Conduct a fresh review using [`review.md`](review.md). Fix worthwhile findings rather than only listing them.
- Rerun every check affected by a fix. Broaden validation only when new evidence or risk warrants it.
- Update documentation, schemas, migrations, changelog entries, and release metadata to match actual behavior.
- Review the final diff and working tree. Report what changed, what was verified, and any intentionally deferred limitation.
