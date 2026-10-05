# Code comments

Source-supported practice: [Google review guidance](https://google.github.io/eng-practices/review/reviewer/comments.html) and [Python style guidance](https://google.github.io/styleguide/pyguide.html#s3.8-comments-and-docstrings) distinguish explanatory comments from readable implementation and public API documentation. Reviewed 2026-10-05.

Explain intent, invariants, units, surprising constraints and why a reasonable alternative fails. Prefer clear names and structure for obvious mechanics. A comment cannot compensate for incorrect code. Public API documentation should explain contract, arguments, results, exceptions and meaningful examples according to the target language; implementation comments belong at the non-obvious decision.

For a workaround, name the upstream issue or constraint and removal condition when known. Do not invent an expiry date; use a verified version or recheck trigger. Update or remove stale comments in the same change as behavior. Preserve useful user voice and attribution. Avoid restating every line or adding generic assurances. A needed invariant comment can be longer than the code it protects.

Local policy: choose comment density in proportion to future misunderstanding. The [house comments overlay](../overlays/code-comments.md) supplies presentation preferences without changing these principles.
