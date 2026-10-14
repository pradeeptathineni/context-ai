# Retrieve bounded output

Before a verbose command or large file read, use native file/search tools with explicit limits. Keep raw bytes in a local file and retrieve numbered evidence. This procedure never installs a filter, rewrites commands or grants execution authority.

For discovery or migration, start at the relevant project roots and name a reason to expand. Keep detailed inventories and hash manifests on disk; return totals and a few targeted examples. Narrowing discovery or output never replaces the full integrity checks required for selected areas. Tool output estimates and caps do not measure model-token consumption.

The delivered standard-library operation offers the same workflow on either host:

```sh
python3 .context-ai/resources/scripts/context_output.py run --log build-raw.log -- python3 -m unittest discover -s tests
python3 .context-ai/resources/scripts/context_output.py inspect build-raw.log --query 'Caused by' --query error
python3 .context-ai/resources/scripts/context_output.py inspect build-raw.log --start 120 --lines 20
```

`run` executes the argv once, merges stdout/stderr into a new file, reports the actual exit status and returns it. The adjacent `NEW_LOG.status.json` durably retains running/completed/failed-to-start state and the actual status before a view is rendered. A view error returns the command’s status and a bounded retrieval cue. Existing raw or receipt files, including symlinks, are refused. No shell expansion is performed: use a reviewed script for compound commands. A missing parent directory must be created explicitly. Raw output may contain private data; keep it in the consumer's private workspace.

The view defaults to 4 KiB and 40 evidence lines. It gives raw path, SHA256, byte/line counts and numbered matching context. For a failed `run`, all decoded output is displayed when the complete report fits the byte budget, even when it exceeds the evidence-line limit or contains no search keywords. Larger failures show selected matching evidence and a labeled final tail. The tail keeps the end of an oversized line; clipped rows are marked as prefixes or suffixes. JSON escaping and metadata count toward the budget. If metadata cannot fit, the bounded recovery cue and durable receipt preserve the outcome.

`inspect` and larger failure views are partial: literal searches inspect bounded line prefixes, so long-line suffixes, unmatched causes and omitted matches need another query/range or native bounded search. A long failure's tail is not necessarily its cause. UTF-8 replacement decoding is for display only; the raw file retains exact bytes. A short result is never proof that no error occurred. Read the cause and relevant context before proposing a fix; verify the result with the actual project test.

Native Read/Grep/Glob bypass shell filters. Bound these reads explicitly. RTK is an optional reviewed explicit filter for supported command formats; its compact view can omit causes, so use bounded recall/search. Choose one transformation owner per command. No global hooks, model or service is needed here.

## Optional reviewed RTK route

For an already reviewed project-local RTK executable, choose RTK alone for a supported command and retain its printed recall ID. The exercised interface is v0.51.0, source [e001f77](https://github.com/rtk-ai/rtk/tree/e001f773f80b22b7dc4c7a79521b30e35aaef026), Apache-2.0. Confirm the local version before use. Keep `RTK_TELEMETRY_DISABLED=1`, `RTK_DB_PATH` and `RTK_RECALL_DB` explicitly project-local; do not run `init` or install hooks as part of this procedure.

`rtk test COMMAND ...` and `rtk err COMMAND ...` retain failure output and status in the exercised formats. Their compact views omitted causes in local fixtures: retrieve the printed ID with `rtk recall ID --grep 'distinctive cause|nearby diagnostic label'`. At this pin `--lines` slices before `--grep`, so combining them can hide a middle-file cause. Bound an unusually broad query with ordinary host output limits; refine it and read surrounding evidence. `--full` restores raw bytes but should be redirected to a file before further inspection. Do not rerun a stateful command merely to recover its output.

Native Read/Grep/Glob are separate paths. The trial simulated hook rewrites for Bash and observed no rewrite for those built-ins; no installed-hook or universal interception claim follows. Native capture/search remains the ordinary arbitrary-output route. Reconsider a server only after a concrete workload exceeds it.
