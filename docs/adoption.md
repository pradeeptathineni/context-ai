# Adopt Context AI

Start with the [direct-read example](../README.md#use-one-context). Supply an exact Context checkout or archive path and read only what the task needs. A direct read requires no installation or environment. Project instructions and the user's request take precedence.

For recurring project use, choose a [catalog profile](library.md) or an [explicit loadout](loadouts.md). The library guide owns source-environment setup and the delivery sequence; the loadout guide owns the command and runtime contract. Run Context commands from its source environment and task checks from the consumer project. Installation makes resources available; it does not prove discovery, invocation or benefit.

## Reusable library and custom consumers

- `core/` owns provider-independent principles. `overlays/` contains reusable optional custom variants, while `domains/` contains concern-specific guidance. These are different functions, not three copies of one rule. Keep their existing paths and select only what the task needs.
- A custom consumer owns its current operating preferences, hardware and account observations, model choices, budgets and concurrency policy. Keep credentials, private work and live usage outside the public library. Native hosts own actual authentication, permissions, hooks, tools, models and delegation.
- The six committed `library/profiles/*.yaml` files are compatibility examples. Five are unbound from their former project/runtime metadata; `simulation` remains unchanged. IDs, schemas, ordered option/concern selections, recipe policies and historical snapshots remain usable for legacy selection and replay. They are not authoritative observations of a person's current setup, access or acceptance. Recheck their fit before applying them to a real consumer.
- Historical snapshots and legacy selection/policy defaults remain public compatibility exceptions. Snapshot plus policy participates in trial-history identity, so changing those values can repeat prior work. This is partial metadata separation, not complete personal-policy migration or privacy erasure.
- Private effective selections, assessments and ownership receipts stay in the caller's explicitly chosen local state. This does not move installation data or create a new profile parser. Catalog `--profile` selects an existing ID or basename; `packet --profile FILE` separately reads a task-profile declaration.
- Keep project-specific guidance locally available, with references to selected Context resources and small owned exceptions. A personal setup does not require a Context fork. A change to shared behavior needs a reviewed generic extension, rather than another copy of the engine.
- Retain an exact source checkout or archive and its pin. A moving pointer is not a frozen revision. Existing installed resources remain pinned until an explicit refresh preview and apply; undo preserves unmanaged instructions and edited managed files.
- Treat local lessons as candidates for upstream generalization only after scoped evidence and useful transfer. Preserve failed trials and uncertainty. Personal preference, installation and passing tests do not establish a universal default.

## Optional use across repositories

Keep a checkout or pointer at `~/.ai/context-ai` on each host where it is needed. To expose the Git-owned [standard skill](../.agents/skills/standard/SKILL.md) across local Codex projects, link that folder into `~/.agents/skills/standard`. Verify discovery in a fresh session before relying on implicit selection. Neither this guide nor a project profile changes global settings.

A small user entry point can be merged into an existing `~/.codex/AGENTS.md` under explicit user authority:

```markdown
For substantial development, inspect the current project's instructions, code, decisions and tools. The Context source is at ~/.ai/context-ai; read only relevant guidance from overlays/README.md. Links do not load themselves.

At a consequential tooling or workflow choice, use the standard skill when available; otherwise read core/prior-art.md from that source. Preserve project contracts and unrelated work, complete authorized implementation and verification, and report what was actually read, invoked and checked. User and project instructions take precedence.
```

[Codex](../providers/openai/codex.md) and [Claude Code](../providers/anthropic/claude-code.md) describe host-specific discovery and precedence. Model routing is advice; native host controls select the actual model and reasoning. A referenced file is loaded only when read. Restart or refresh the host's instruction discovery when necessary.

## Check adoption

In a disposable project, exercise a [usage case](../evals/usage-cases.md) and inspect its transcript and final artifact. Check that a simple task uses no unnecessary library context, selected procedures are reachable, project instructions remain authoritative, and task checks actually ran. Report explicit reads separately from observed native discovery. If a source pointer is unavailable on another host, make the exact source available there before claiming it worked.
