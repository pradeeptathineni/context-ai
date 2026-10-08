# Retrieve bounded output

Before a verbose command or large file read, use native file/search tools with explicit limits. Keep raw bytes in a local file and retrieve numbered evidence. This procedure never installs a filter, rewrites commands or grants execution authority.

The delivered standard-library operation offers the same workflow on either host:

```sh
python3 .context-ai/resources/scripts/context_output.py run --log build-raw.log -- python3 -m unittest discover -s tests
python3 .context-ai/resources/scripts/context_output.py inspect build-raw.log --query 'Caused by' --query error
python3 .context-ai/resources/scripts/context_output.py inspect build-raw.log --start 120 --lines 20
```

`run` executes the argv once, merges stdout/stderr into a new file, reports the actual exit status and returns it. Existing files, including symlinks, are refused. No shell expansion is performed: use a reviewed script for compound commands. A missing parent directory must be created explicitly. Raw output may contain private data; keep it in the consumer's private workspace.

The view defaults to 4 KiB and 40 evidence lines. It gives raw path, SHA256, byte/line counts and numbered matching context. It is partial: literal searches inspect bounded line prefixes, so long-line suffixes, unmatched causes and omitted matches need another range or native bounded search. A short result is never proof that no error occurred. Read the cause and relevant context before proposing a fix; verify the result with the actual project test.

Native Read/Grep/Glob bypass shell filters. Bound these reads explicitly. RTK is an optional reviewed explicit filter for supported command formats; its compact view can omit causes, so use bounded recall/search. Choose one transformation owner per command. No global hooks, model or service is needed here.
