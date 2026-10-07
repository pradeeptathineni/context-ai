# Essentials route: same-task consumer trial (2026-10-07)

**Question.** Does the refreshed essentials route change how an agent handles a feature that an installed dependency could solve, compared with no Context and the pre-reset `standard` loadout, without losing correctness?

**Task.** A disposable Python consumer (`feeds`, Requests 2.32.3 with urllib3 2.8.0 installed transitively) whose `TASK.md` asks for retries of 502/503/504 and connection errors with backoff, no retry on 404, and tests. The task never names a library, so reuse of the installed urllib3 `Retry` versus a local loop versus a new dependency is a genuine decision.

**Arms.** Identical commit, prompt and host: Codex CLI 0.160.0, `codex exec --ignore-user-config -m gpt-6.1-sol -c model_reasoning_effort="medium" -s workspace-write`, ChatGPT subscription sign-in, one run per arm.

| Arm | Context | Wall time | Input tokens (cached) | Output tokens | Shell commands | Context files read | Tests after (unsandboxed) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| native | none in project | 64 s | 102,633 (89,216) | 2,373 | 8 | 1 (user-level `standard` skill) | 13 passed |
| old | pre-reset `standard` at 7e81443 | 164 s | 208,373 (178,304) | 2,895 | 8 | 17 | 15 passed |
| essentials | `essentials` at 0bc013e | 309 s | 393,439 (360,192) | 5,467 | 16 | 13 | 16 passed |

All three implemented a bounded local loop, retried 502/503/504 and connection errors, failed 404 immediately and kept tests green; the one existing socket test fails only inside the Codex sandbox (`PermissionError` binding localhost) and passes outside it. Correctness did not differ.

**What changed with essentials.** It was the only arm that inspected the installed alternative before deciding: it read Requests' `adapters.py` and urllib3's `util/retry.py`, then recorded the need, three alternatives (one attempt, urllib3 `Retry` via `HTTPAdapter`, a new dependency), the reason for rejecting adapter ownership (it would replace caller-supplied session policy), evidence and a reopening condition in `DECISIONS.md`. It showed each new test failing before implementation. The native and old arms named the same alternatives in one sentence without inspecting them.

**Cost.** Essentials used about 1.9x the input tokens of the old route and 3.8x native, and about twice the wall time of old. Most extra reads were the pinned TDD helper files and both review sources. This is the price of the evidence above, not a saving; no token reduction is claimed.

**Limits.** One run per arm, builder-designed task, builder grading. The user's global `~/.agents/skills/standard` skill (which routes to this library) was visible to every arm, so "native" is not Context-free. Human usefulness is unmeasured. Raw JSONL, diffs and the decision record are kept in the local planning folder, not this repository.

**Consequence.** Essentials stays the default feature route because it produced the prior-art inspection and record that CTX04 requires and the other arms skipped. Revisit if a second task shows the extra reads without a better-evidenced decision.
