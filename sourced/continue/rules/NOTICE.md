# Continue rule selection

Copyright 2023 Continue Dev, Inc. Apache-2.0; see LICENSE.

Source: https://github.com/continuedev/continue at
`5522c6f44ca0ac3528b37244818fbfa39b5af470`, reviewed 2026-10-22.
The two `*.upstream.ts` files are unchanged snapshots of
`core/llm/rules/getSystemMessageWithRules.ts` and
`core/llm/rules/nestedDirectoryRules.vitest.ts`. The pinned root NOTICE URL
returned 404; the retained LICENSE includes the copyright notice.

`scripts/context_guidance.py` and `tests/test_task_guidance.py` adapt the
off/global/known-files/colocation/glob decision tree and nested-rule controls
to Python. Context uses segment-safe project containment, declared topic
precedence, per-file reasons, bounded private-safe delivery and a documented
glob subset. It accepts explicit task paths, without parsing messages or
reading file contents for regex matching. No upstream runtime is executed.
