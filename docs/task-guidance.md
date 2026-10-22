# Guidance for task files

Give Context the files a task will touch. A docs task can receive reader and
voice guidance while a Python task receives API guidance. Selection reads no
task file contents, calls no model, and adds no hook installation.

Add an optional `.context-ai/guidance.yaml` to an equipped project:

```yaml
schema_version: 1
rules:
  - id: docs
    path: guidance/docs.md
    directory: docs
    globs: ["**/*.md", "!generated/**"]
    topic: writing.voice
  - id: python
    path: guidance/python.md
    globs: "**/*.py"
```

`path` identifies guidance relative to its owner root. `directory` and `globs`
select files relative to the **target project**, even in a private manifest.
Globs inside a directory rule are relative to that directory. Supported patterns
are `*`, `?`, character classes and whole-segment `**`; `!` excludes matches.
Positive patterns are alternatives; any matching exclusion wins. Brace/extended
globs and content regex are rejected rather than silently approximated. Files
may be new or existing, relative to the equipped root or absolute within it.
Symlink paths and escapes are refused. No recursive file discovery occurs.

A root rule without selectors applies by default. `always_apply: true` explicitly
applies globally; `always_apply: false` without selectors needs an explicit
private resource/stage selection instead. `policy: off` always omits the rule.
Without known task files, only globals apply. Selected missing/oversized guidance
stops delivery; an irrelevant missing file is not read. Limits are 64 files,
64 rules per owner, 64 KiB per manifest and the existing 9,500-character output
bound. Omission never truncates a selected instruction to fit.

Keep personal voice rules and permissioned writing examples in Custom. An
explicit `--private-root` may contain a private `guidance.yaml` in the same
format, pointing to its own Markdown files. Context never copies these into the
project. Do not put a private root in shared hook configuration.

## Precedence and explanations

Host constraints and explicit user decisions remain authoritative. Existing
project instructions and installed stages are preserved. For rules declaring
the same `topic`, project rules override private defaults; within an owner,
narrower directories override broader ones. Resolve separately for each task
file, so two packages can retain different guidance. Equally ranked different
text stops delivery; identical alternatives deduplicate. Topics are explicit
mutually exclusive slots, not an attempt to infer contradictions in prose.
Rules without a topic compose. Conflicts with free-form AGENTS/stage text still
require human or model judgment under the stated authority order.

```sh
.venv/bin/python scripts/context_delivery.py --provider codex --project /PATH/PROJECT --task-file docs/guide.md
.venv/bin/python scripts/context_delivery.py --provider codex --project /PATH/PROJECT --task-file docs/guide.md --private-root /PATH/PRIVATE_CUSTOM --format context
```

The default output is a private-safe receipt with project rule inclusion,
omission and shadowing reasons. `--format context` prints the selected guidance;
`--format local` includes full decisions, matched paths and source hashes. Both
can expose private material: keep them in memory or private local files. Public
receipts exclude private rule identities, topics, paths, text and hashes.
An unresolved topic returns `guidance_conflict` without partial context;
`--format local` also identifies the conflicting rules and affected file.

`prepare(project, provider, task_files=(...), private_root=...)` is the same
read-only pre-execution entrypoint used by Maestro. It returns `context`,
`local_identity`, `local_sources`, `task_guidance` and `public_receipt`.
The local identity binds known paths, decisions and exact consulted guidance
bytes; reprepare under the worker lock to catch drift. A Maestro campaign must
derive these paths from its approved task, not model guesses. Deep can display
the receipt and consumes this owner contract; it needs no second resolver.

Run the synthetic two-scope demo with
`.venv/bin/python examples/task-guidance/demo.py`. It proves selection and
consumer plumbing, not model obedience or improved writing quality.

The decision tree and nested-rule controls adapt [pinned Continue source](../sourced/continue/rules/NOTICE.md).
Context uses its existing strict YAML/path checks and Python's segment matching;
adding a Node/minimatch runtime would serve no current consumer. Broader code
maps, semantic routing and automatic personal-profile updates remain outside
this path-based capability.
