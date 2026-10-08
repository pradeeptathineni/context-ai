# Diagnose and fix

Use for a failing command, integration symptom or observable defect. Read the scoped project instructions and [testing guidance](../core/testing.md). For routine edits without a failure, use the normal development loop.

Reproduce the smallest meaningful failure with the project's existing command or browser. Keep the exit status and discriminating output locally; redact secrets rather than dumping environment variables. When the output is large, save it to a file before reading it, never print it whole into the conversation: search it for the failing item and error text (for example `rg -n -C3`), read only the surrounding line ranges, and report the file and ranges you relied on. The decisive line is often neither at the head nor at the tail. Separate product behavior from missing dependencies, credentials, network or hosted-runner failures. If reproduction is unavailable, state the boundary and inspect the affected path before proposing a fix.

Trace the failing input across the relevant boundary. Compare a working case and recent changes. State a testable explanation and use one discriminating check to challenge it; do not repeat a failed attempt without new evidence. A clear local defect needs no formal investigation phases. For a difficult boundary, use [orchestration](../overlays/orchestration.md) only within existing delegation authority.

Make the smallest justified fix. Add a regression check when the behavior is stable and meaningful; show that it fails before the fix and passes afterward. Keep refactoring separate when it would obscure the behavioral change. Rerun affected checks, inspect actual output, and report what remains untested. Reuse a passing result while its relevant inputs stay unchanged.

Adapted proportionally from [Systematic Debugging](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/systematic-debugging/SKILL.md); Context authors this procedure and excludes upstream environment-dump examples and mandatory ceremony.
