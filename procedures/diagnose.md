# Diagnose and fix

Use for a failing command, integration symptom or observable defect. Read the scoped project instructions and [testing guidance](../core/testing.md). For routine edits without a failure, use the normal development loop.

Reproduce the smallest meaningful failure with the project's existing command or browser. Keep the exit status and discriminating output locally; redact secrets rather than dumping environment variables. Separate product behavior from missing dependencies, credentials, network or hosted-runner failures. If reproduction is unavailable, state the boundary and inspect the affected path before proposing a fix.

Trace the failing input across the relevant boundary. Compare a working case and recent changes. State a testable explanation and use one discriminating check to challenge it; do not repeat a failed attempt without new evidence. A clear local defect needs no formal investigation phases. For a difficult boundary, use [orchestration](../overlays/orchestration.md) only within existing delegation authority.

Make the smallest justified fix. Add a regression check when the behavior is stable and meaningful; show that it fails before the fix and passes afterward. Keep refactoring separate when it would obscure the behavioral change. Rerun affected checks, inspect actual output, and report what remains untested. Reuse a passing result while its relevant inputs stay unchanged.

Adapted proportionally from [Systematic Debugging](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/systematic-debugging/SKILL.md); Context authors this procedure and excludes upstream environment-dump examples and mandatory ceremony.
