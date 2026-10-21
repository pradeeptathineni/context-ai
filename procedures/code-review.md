# Focused code review

Use to review a change since a fixed point on two separate axes. Follow the pinned [Matt Pocock code-review skill](../sourced/mattpocock/code-review/instruction.md) for its process. Pin the fixed point and find the spec and standards sources. Apply its smell baseline, then report `## Standards` and `## Spec` separately with the one-line per-axis summary.

These Context deltas take precedence over the upstream prose:

- Run the two axes one after the other in this session. Use parallel sub-agents only when the host supports them and the task already authorizes delegation; this file grants neither.
- No tracker setup skill is needed. Take the spec from the task, issue text you were given, or repository files. If none exists, report "no spec available" for the Spec axis.
- When the task already identifies the change, such as a commit range or the working tree, use it as the fixed point instead of asking.
- The review is review-only unless the task authorizes corrections.

Upstream: mattpocock/skills, MIT. The exact pin, equivalent later revision and license are recorded in `sources.lock.json`.
