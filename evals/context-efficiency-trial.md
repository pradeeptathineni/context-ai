# Output and navigation efficiency trial (2026-10-07)

**Question.** Should Context make context-mode [P33], Headroom [P60] or Graphify [P34] a default, or keep the current route (bounded project logs, `rg`, native host truncation)?

## Verbose failing output

A 3,064-line, 208,250-byte pytest log: 2,399 passes, 643 deprecation warnings, one failure. The root cause (`unsupported codec 'zstd' in archive header`) appears once at line 1,416, far from the head and tail; the tail shows only the assertion symptom. Success means the representation keeps the root cause and the assertion, or recovers them on request.

| Route | Exact setup | Bytes shown | Root cause | Assertion | Notes |
| --- | --- | --- | --- | --- | --- |
| Naive tail | `tail -n 60` | ~4,000 | no | yes | Negative control |
| Current bounded log | log saved to a file, then `rg -n -C2 'FAILED\|Error\|unsupported\|WARNING '` | 1,613 | yes | yes | Pattern choice is the agent's; the full log stays on disk |
| Headroom 0.40.0 library, OpenAI tool message | `compress(messages, protect_recent=0)` | 208,250 | yes | yes | `passthrough:lossy_unrecoverable`; no reduction |
| Headroom 0.40.0 library, Anthropic `tool_result` | same, Anthropic format | 195,576 (64,935 to 59,553 tokens) | yes | yes | `lossless_search`, about 8% smaller; ML Kompress and CCR removal did not engage on this content |
| context-mode 1.0.169 MCP | `ctx_execute` (`cat verbose.log`, intent "find why test_restore_roundtrip fails") | 1,492 | **no** | **no** | Its intent match surfaced warnings and passing lines |
| context-mode, follow-up | `ctx_search` "restore_roundtrip root cause codec archive" | 2,237 more | yes | yes | Recovered with a second, well-chosen query |

All three ran project-local with an isolated `HOME`: `pip install headroom-ai==0.40.0` (Apache-2.0, upstream 278bbc8) and `npm install --ignore-scripts context-mode@1.0.169` (Elastic-2.0, upstream 2a7a92a). Both default their stores to the user's home (`~/.headroom`, `~/.claude/context-mode`). context-mode's postinstall script edits `~/.claude/plugins` and `~/.claude/settings.json`, and Headroom's `wrap` mode registers a proxy and MCP server in `~/.claude.json`; both conflict with the no-global-hooks rule and were not run. No agent end-task run was made with either, because their agent integrations are exactly those global paths.

## Structural navigation

Graphify 0.9.80 (`graphifyy`, Apache-2.0/MIT, upstream 6478eb7) built a code graph of `scripts/` in 2.4 s with no LLM (`graphify update .`: 131 nodes, 447 edges). `graphify explain "ownership"` listed the correct callers (`main`, `check`, `selected_concerns`) and callees in 1,109 bytes. `rg -n '\bownership\('` gave the same callers in three lines. `graphify path "apply" "ownership"` returned a misleading two-hop path through the file node, not the real chain `apply -> preflight -> selected_concerns -> ownership`. Its install command adds host instruction blocks and PreToolUse hooks.

## Decision

Keep the current route as the owner of tool-output efficiency: save verbose output to a file, read targeted ranges and keep exit status (see `procedures/diagnose.md`). No compressor or graph becomes a default. Reopen Headroom when a host exposes a project-local integration without a global proxy and a long-session workload shows retained correctness with material savings; reopen context-mode only if its intent retrieval finds root causes without a follow-up query; reopen Graphify for a large unfamiliar repository where `rg` cannot answer cross-module questions. Advertised reduction percentages were not reproduced on this workload and are not claimed.

Limits: one synthetic log and one small repository, deterministic tool calls, no model in the loop. Inputs, scripts and outputs are kept in the local planning folder.

## End-task comparison (independent Codex review of 1fc6f94)

One frozen 208,250-byte log (SHA-256 `b5d97b06…81fa9`), the same task and the same requested model for a native consumer and a consumer given `essentials --with context-diagnose`, one run each, under an oracle frozen beforehand. Both passed all nine checks (root cause, exact middle evidence, symptom, test, boundary repair, verification plan). Context used 293,645 input tokens against 160,866 (about 1.83x; uncached input about 1.24x), 164.6 s against 89.1 s and 17 commands (one failed) against 7. **Correct in both; no benefit shown; bounded-output adherence not demonstrated.**

The traces show a concrete cause. Both consumers began with `nl -ba verbose.log`, a 229 KB dump into the conversation (step 3 native, step 5 Context). The Context consumer opened `procedures/diagnose.md` only afterwards (step 6), and that procedure did not contain the save-then-search recipe this trial and D-025 say it owns: it said only to keep discriminating output locally. The recipe is now in `procedures/diagnose.md`. No agent run has tested whether it changes behavior, so adherence stays unproven and no savings are claimed. The raw `aggregated_output` sizes are command stdout, not model-visible context accounting; actual model-visible bytes, unique tokens and cost are unknown.

## Exact-version documentation (Context7)

For the consumer's installed urllib3 2.8.0, `GET context7.com/api/v2/libs/search?libraryName=urllib3` (no key) returned `/urllib3/urllib3` (indexed versions: 1.26.20 only) and `/websites/urllib3_readthedocs_io_en_stable`. A `context` query for `Retry status_forcelist backoff_factor` returned relevant main-branch user-guide snippets with source links, including `backoff_jitter`. Requesting `/urllib3/urllib3/2.8.0` returned HTTP 404 `version_not_found`. Inspecting the installed `urllib3.util.Retry.__init__` confirmed `backoff_jitter`, `backoff_max` and `status_forcelist` exist in 2.8.0. `procedures/current-docs.md` encodes exactly this: Context7 for discovery, the installed version as the authority, and a reported fallback when versions do not match. No query contained project code.
