# Independent review

Review the completed change from a fresh perspective. Use the requirements and actual diff as inputs; do not assume the implementation approach was correct because it is already present.

## Inspect

- correctness defects and incomplete behavior
- missing or misread requirements
- security, privacy, permission, and data-loss risks
- regressions and compatibility breaks
- hidden assumptions and unhandled boundaries
- inconsistent or poor failure behavior
- false positives and false negatives
- stale documentation or claims that exceed the implementation
- duplication, misplaced responsibilities, and contradictory rules
- unnecessary complexity, fragile coupling, and maintainability problems
- scope creep and unrelated changes

For context or configuration, also inspect authority, provenance, freshness, precedence, token cost, schema compatibility, and whether provider-specific facts leaked into canonical guidance.

## Resolve

- Rank findings by consequence and evidence, not stylistic preference.
- Reproduce or trace suspected defects before expanding the change.
- Fix justified findings within scope. Remove speculative recommendations that do not improve the release.
- Add or adjust a discriminating check when it prevents a meaningful recurrence.
- Re-run every validation affected by the revisions and inspect the final diff again.

A review is complete when material findings are resolved or explicitly accepted with rationale—not when a checklist has merely been read.
