# Session context delivery (candidate)

`scripts/context_delivery.py` reads an existing `plan`/`apply` installation. It
uses the nearest equipped ancestor of a session's working directory. At session
start it delivers private user guidance first when a private root was explicitly
configured, followed by the checked project instructions and managed route. A
caller that knows the task may request an installed stage and explicit private
task resources. The same `prepare()` function is the prelaunch entrypoint for a
Maestro adapter; it has no model or filesystem writes.

Known task files select project and private writing guidance through the same
entrypoint; see [task guidance](task-guidance.md) for manifests, precedence,
CLI output and the offline demo. Generic session start does not infer a task.

The command adapter accepts a Codex or Claude Code `SessionStart` JSON payload
on stdin and emits their documented `hookSpecificOutput.additionalContext` JSON.
It handles `startup`, `resume`, `clear`, `compact`, and `fork`. A missing required
file, changed pin, unsafe path, unsupported event, or output beyond 9,500
characters yields `continue: false` without partial guidance. The in-memory
`local_identity` binds exact delivered bytes for a trusted local consumer;
`public_receipt` excludes private text, paths and hashes. Its status is
`prepared_unverified`, not proof that a hook ran or a model followed guidance.

For a **reviewed, project-local** qualification, point a synchronous command
hook at an absolute path to this script and pass `--provider codex` or
`--provider claude`. A private root may be passed only in local, non-shared
configuration. The proposed reversible entries are:

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "startup|resume|clear|compact|fork",
      "hooks": [{"type": "command", "command": "/ABSOLUTE/CONTEXT_AI/.venv/bin/python -B /ABSOLUTE/CONTEXT_AI/scripts/context_delivery.py --provider codex --private-root /ABSOLUTE/PRIVATE_CUSTOM_AI", "timeout": 30, "additionalContextLimit": 0}]
    }]
  }
}
```

Codex location: `.codex/hooks.json`. Claude location:
`.claude/settings.local.json`, using the same structure with
`--provider claude` and omitting `additionalContextLimit`. Replace the absolute
paths only after reviewing the intended checkout and Python environment. Merge
with existing hooks; do not replace other configuration. These entries have
**not** been installed. Provider trust/disabled-hook states and cloud sessions
can skip local hooks. A skipped hook has no verified delivery. Real-session
delivery and any semantic effect require separate observation.

Protocol references: [Codex hooks](https://developers.openai.com/codex/hooks)
and [Claude Code hooks](https://code.claude.com/docs/en/hooks).
