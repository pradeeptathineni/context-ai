# Read native usage

For an authorized ordinary run, prefer the host's reported token counters. This opt-in
reader parses an already supplied local receipt; it starts no agent, reads no session
directory, installs no hook and changes no model, policy or configuration. Keep raw
events private: they can contain prompts, tool arguments and source text. The normalized
output retains metrics and opaque run/thread IDs, never those contents.

```sh
python3 .context-ai/resources/scripts/context_usage.py supplied-events.jsonl --format codex-exec
python3 .context-ai/resources/scripts/context_usage.py supplied-events.jsonl --format app-server
python3 .context-ai/resources/scripts/context_usage.py supplied-metrics.json --format native-metrics
```

The first two formats accept the documented Codex JSONL completion stream and App Server
`thread/tokenUsage/updated` notifications. Native-metrics is an explicit version-1
projection: `schema_version: 1`, `runId`, `status`, and `usage` with `elapsedMs`, optional
`stages`, and `providerUsage` containing `provider` snake-case counters, requested `model`
and `effort`, optional `servedModel`, stage times and process `termination`. Produce that
projection from the existing runner's allowed metrics, rather than passing a private
research record. Schema-1 output is advisory evidence, independent of installation locks.

`input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens`,
`cache_write_input_tokens`, and `total_tokens` remain separate reported fields. Missing
fields are null, including a missing total; the reader does not invent them or add cached
input/reasoning breakdowns again. It rejects negative, boolean, fractional and oversized
counters. Source-specific semantics matter: a CLI terminal counter is not proven to be
one provider call or a delta from a resumed session. It is never summed with another
terminal event. Identical terminal observations within the same turn are deduplicated;
an intervening turn start is a different observation even if counts match. A later
interrupted turn has missing current usage, with earlier observations retained separately.

App Server `total` is a thread-cumulative snapshot and `last` is retained separately.
Repeated thread/turn/counter snapshots are deduplicated. The difference between the first
and final observed total is labeled `between_snapshots`; it excludes work before the first
snapshot and is not a whole-run or per-stage measurement. Any decreasing observed counter
marks a discontinuity (reset or reordering is not distinguished) and makes this difference
null. Multiple threads refuse aggregation. CLI decreases can also reflect per-turn semantics;
they are not proof of a counter reset.
Missing fields leave their difference null. Completion status is separate from usage;
interrupted/failed work can have reported counters or missing counters.

Requested identity is not served identity. CLI `--requested-model`/`--requested-effort`
only annotate the receipt; they do not change a session or prove service routing. Missing
served identity stays null. Durations are reported measurements, never token estimates;
stage timers can overlap and are not summed. Native search/document/action/read counts retain
their original distinct meanings; reads are not relabeled as admitted documents. Stage tokens, monetary cost and account quota
conversion remain unavailable. A quota percentage is a separate account measure.

The parser writes only JSON to stdout. Inputs are bounded to 4 MB; the command refuses
direct symlink inputs, malformed/version-incompatible data and mixed thread scopes.
Do not use a missing usage receipt as evidence that an aborted run was free. Record the
source digest, result status and limitation beside any comparison. No token-saving,
confidence or task-quality conclusion follows from a lower count alone.

Reviewed 2026-10-12: [Codex non-interactive output](https://learn.chatgpt.com/docs/non-interactive-mode)
and [App Server notifications](https://learn.chatgpt.com/docs/app-server). The locally
inspected CLI 0.160.0 schema names `ThreadTokenUsage.total`, `last` and token breakdown
fields; a schema is not runtime evidence. [Reasoning usage](https://developers.openai.com/api/docs/guides/reasoning)
documents reasoning as an output breakdown, including incomplete responses.
