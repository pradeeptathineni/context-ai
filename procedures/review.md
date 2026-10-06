# Review a consequential change

Use for an intended behavior and scoped diff or responsibility. Establish whether the task authorizes review only or also corrections. Read the project constraints and [review criteria](../core/review.md); inspect callers, compatibility, error paths, trust boundaries and tests that can distinguish the claimed behavior. Prefer the existing tools and preserved interfaces over speculative abstractions.

A finding names its trigger, consequence, location and justified action. Trace or reproduce consequential suspicions before calling them confirmed. Separate actionable defects from preferences and unresolved questions; no actionable finding is a valid result. Inspect test discrimination, not just green status. Google's [review criteria](https://google.github.io/eng-practices/review/reviewer/looking-for.html) inform behavior, complexity and test review; project conventions settle style.

If fixes are authorized, accept or reject findings from evidence, implement supported corrections and rerun affected checks. Review-only authority stops at findings. Report tests and uncertainty separately from the judgment. Agent review is not independent human acceptance.
