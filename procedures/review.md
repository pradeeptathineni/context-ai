# Review a consequential change

Use for an intended behavior and scoped diff or responsibility. Establish whether the task authorizes review only or also corrections. Read the project constraints and [review criteria](../core/review.md); inspect callers, compatibility, error paths, trust boundaries and tests that can distinguish the claimed behavior. Prefer the existing tools and preserved interfaces over speculative abstractions.

Review on separate axes and report them separately so one cannot mask the other:

- **Spec**: requirements missing or partial, behavior nobody asked for, and requirements that look implemented but are wrong. Quote the requirement. When the change has a feature ledger, express each requirement as a scenario (given/when/then) and each change as added, modified or removed behavior, so a dropped requirement is visible.
- **Standards**: documented project standards first; Fowler smells only as labelled judgement calls the project can override.
- **Complexity**: one line per removable item tagged `delete`, `stdlib`, `native`, `reuse`, `yagni` or `shrink`, naming the replacement. Never flag a single smoke test or required safety behavior.

The two-axis separation and smell baseline come from Matt Pocock's pinned [code review](../sourced/mattpocock/code-review/instruction.md); the complexity tags come from Ponytail's pinned [review](../sourced/ponytail/reuse/review.md). Context deltas: one agent may run the axes sequentially; parallel readers need host support and existing delegation authority ([fresh review](review-fresh.md)). Locate the spec from the task, linked issue or repository files; do not require a particular tracker setup skill.

A finding names its trigger, consequence, location and justified action. Trace or reproduce consequential suspicions before calling them confirmed. Separate actionable defects from preferences and unresolved questions; no actionable finding is a valid result. Inspect test discrimination, not just green status. Google's [review criteria](https://google.github.io/eng-practices/review/reviewer/looking-for.html) inform behavior, complexity and test review; project conventions settle style.

If fixes are authorized, accept or reject findings from evidence, implement supported corrections and rerun affected checks. Review-only authority stops at findings. Report tests and uncertainty separately from the judgment. Agent review is not independent human acceptance.
