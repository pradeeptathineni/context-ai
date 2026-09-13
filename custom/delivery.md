# Complete delivery

Use with [`core/development.md`](../core/development.md), [`core/testing.md`](../core/testing.md), [`core/review.md`](../core/review.md), and [`core/versioning.md`](../core/versioning.md).

When implementation and delivery are authorized, own the path from repository inspection through verified destination state. A plausible first patch is the midpoint, not the finish.

`Inspect -> Define -> Implement -> Validate -> Inspect output -> Review -> Refine -> Re-validate -> Document and version -> Commit -> Push -> Verify -> Release when required`

## Establish the boundary

- Read scoped instructions; inspect the working tree, branch, remotes, relevant history, release metadata, and affected system before editing.
- Translate the request into observable acceptance criteria and identify which external writes—commit, push, tag, release, deployment, or message—are actually authorized.
- Preserve unrelated work. Resolve remote divergence safely and never rewrite shared history or move a published tag by default.
- Research only when current facts or unresolved design choices can change the implementation.

## Implement, review, and refine

- Deliver the smallest complete vertical change, including meaningful boundaries, failures, documentation, and compatibility work.
- Run the most discriminating deterministic checks first, then broader checks proportional to shared behavior and release risk. Inspect representative real output when static checks are insufficient.
- Review the completed diff from a fresh perspective for missed requirements, defects, regressions, unsafe behavior, weak claims, and unnecessary complexity.
- Fix justified findings within scope and rerun every affected check. Apply the same full loop to later fixes, enhancements, and change requests; prior success does not lower the standard.
- Stop only when material in-scope findings are resolved or explicitly accepted with rationale.

## Integrate and release

- Align documentation, changelog, schema, compatibility notes, and version metadata with actual behavior. Do not version unrelated machine-readable schemas merely because the repository is released.
- Inspect the final diff and status, then create a cohesive commit containing only verified intended work. Avoid no-op and unrelated commits.
- Push only when authorized. Push the intended branch without force, then verify the destination ref and required hosted checks rather than inferring success from a local command alone.
- Tag only for an intended release or an explicit project policy. Choose the Semantic Versioning level from the public contract, ensure the release commit is on the intended branch, create an immutable annotated `vX.Y.Z` tag, push it, and verify the remote tag target.
- Complete any authorized release or deployment steps and verify their actual external state. If credentials, service health, policy, or another external condition blocks proof, report the exact boundary without fabricating completion.

Report the delivered behavior, validation, review-driven refinements, commit, destination, tag or release when applicable, and any remaining limitation. Completion means the requested result exists where it was meant to exist and the evidence supports that claim.
