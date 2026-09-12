# Testing

Testing exists to establish confidence in behavior that matters, not to maximize test count.

## Select checks

- Validate externally meaningful behavior and contracts.
- Make depth and breadth proportional to change scope, consequence, reversibility, and uncertainty.
- Prefer deterministic, fast, local checks when they provide the required evidence.
- Cover important boundaries, failure paths, invalid inputs, state transitions, and integration seams.
- Add regression coverage for a fixed failure when it is stable, discriminating, and likely to recur.
- Validate generated artifacts and configuration when they are the product.

## Avoid weak evidence

- Do not test private implementation trivia that can change without affecting behavior.
- Do not write tests that only prove mocks return their configured values.
- Do not mock away the integration or failure mode under examination.
- Do not add a framework or dependency solely to claim the project has tests.
- Do not treat a passing command as proof of behavior it did not exercise.

## Inspect and finish

- Inspect representative real outputs when formatting, usability, rendering, generated files, or runtime interaction matters.
- Confirm that a check can fail for the defect it is meant to catch; avoid vacuous assertions and false positives.
- Record the environment, inputs, and versions needed to reproduce consequential results.
- Rerun affected checks after every relevant fix. Run the full suite when shared behavior or release risk warrants it.
- Report skipped or unavailable checks and the confidence gap they leave.

A small discriminating check is more valuable than a large suite disconnected from user-visible risk.
