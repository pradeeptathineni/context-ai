# Session context delivery (candidate)

`scripts/context_delivery.py` reads an existing `plan`/`apply` installation. It
uses the nearest equipped ancestor for a session hook's working directory. Direct
`prepare(project, ...)` calls and CLI `--project` require that exact project's
complete installation. An unequipped nested project cannot borrow its parent's
instructions. Callers that deliberately need the earlier ancestor lookup must
pass `discover_ancestor=True`. Hook delivery opts into that lookup explicitly.
Known task paths are relative to the selected equipped root, or absolute within
it. At session
start it delivers private user guidance first when a private root was explicitly
configured, followed by the checked project instructions and managed route.
A private root must contain `README.md`, which is always delivered first. If a
writing-kit directory is the root, its README must be written as guidance.
A caller that knows the task may request an installed stage and explicit private
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
`local_identity` binds delivered text and the original bytes of consulted
instructions, stage files, private resources, guidance manifests and rules.
It also binds the installed library revision, selected loadouts, resource tree
and owned native skill pins. Every owned native skill must match its pin before
delivery, even when the short rendered route is unchanged. This identity change
requires a new preview for outstanding context-bound approvals; it grants no
new approval or installation authority.
A refusal prints stable, path-free JSON: `continue: false`, a `reason` code and a
short next step in `stopReason`. Codes cover an unequipped or unavailable project,
provider or stage outside the installed selection, installation or route drift,
a shadowing Claude route, private-root and guidance-file problems, oversized
context, invalid task files or guidance manifests, and invalid hook input. An
equal-precedence guidance conflict keeps `guidance_conflict`; its details stay in local
`--project --format local` output only. Only exact, known static messages map to
a code. Any other error, including one that names a path, returns the generic
failure with no `reason` and no exception text. Hook success is ASCII-escaped
JSON, so it parses to the same Unicode under any stdout encoding. A direct
call without `--project` exits 2 with a usage error when stdin is a terminal
instead of waiting for a hook payload.
Rendering normalizes line endings to LF, while hashes use the original bytes.
A newline-only source change therefore changes local identity even if the
rendered text is unchanged. A correctly pinned CRLF stage remains valid.
This exact identity is for a trusted local consumer only. The
`public_receipt` excludes private text, paths and hashes. Its status is
`prepared_unverified`, not proof that a hook ran or a model followed guidance.
Its `source_digest` is a public selection fingerprint, not an exact hash of
private text or proof that two private preparations match.

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
