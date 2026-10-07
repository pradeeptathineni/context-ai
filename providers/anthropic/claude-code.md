# Anthropic Claude Code adapter

Reviewed: 2026-10-07

This file describes how Claude Code receives a Context selection. It does not replace the provider-independent guidance in [`../../core/`](../../core/), and it shares one canonical copy of every instruction with the [Codex adapter](../openai/codex.md).

## Instruction discovery

Claude Code v2.1.277 and later read `AGENTS.md` as project instructions when no `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` exists in the working directory or above it. When one exists, Claude reads the `CLAUDE.md` files instead, unless a `CLAUDE.md` imports `AGENTS.md` with an `@AGENTS.md` line ([memory documentation](https://code.claude.com/docs/en/memory)). Files load at session start; `/context` lists the memory files actually loaded.

Context therefore uses the native route first:

| Project state | What Context writes for Claude |
| --- | --- |
| No CLAUDE.md anywhere above the project | Nothing extra; Claude reads the managed `AGENTS.md` block natively |
| A project CLAUDE.md that imports `@AGENTS.md` | Nothing extra |
| A CLAUDE.md that does not import `AGENTS.md`, or only `CLAUDE.local.md`/an ancestor CLAUDE.md | One owned block in the project `CLAUDE.md` (or the existing `.claude/CLAUDE.md`) with the same router text |

Context never adds `@AGENTS.md` to a user's CLAUDE.md, because that would pull the user's whole AGENTS.md into Claude sessions that deliberately excluded it. `plan` reports the chosen mode under `host_routing.claude`; `verify` fails if a CLAUDE.md later shadows AGENTS.md without a managed route, so `refresh` can add one.

## Skills

Claude Code discovers project skills in `.claude/skills/<name>/SKILL.md` from the start directory up to the repository root and watches those directories for changes within a session ([skills documentation](https://code.claude.com/docs/en/skills)). It does not read `.agents/skills`. With `--provider claude` or `--provider both`, Context writes thin routers there with the same `name` and `description` frontmatter as the Codex routers. Each router links to the single pinned copy under `.context-ai/resources/`; no instruction text is duplicated per host. Claude may load a skill automatically from its description or by `/name`; the `Skill` tool call in a session transcript is the activation evidence, not the file on disk.

## Native ownership and coexistence

Claude Code owns plugins (`enabledPlugins` in `.claude/settings*.json`), hooks, MCP servers, permissions, authentication, model and effort. Context never writes those paths. `plan` lists project-local native skills and enabled plugins under `native_managed` and refuses a selection whose concern is already routed by an existing project skill with a duplicating name (for example a user `tdd` skill and Context's `context-tdd`). Plugin skills are namespaced by the plugin and cannot collide with Context router paths; their concern overlap is reported, not changed.

## Headless use and billing

Print mode (`claude -p`) is programmatic execution. Ordinary print mode can load ambient hooks, plugins and MCP configuration; `--bare` skips them but uses API/provider credentials rather than subscription sign-in ([headless](https://code.claude.com/docs/en/headless), [costs](https://code.claude.com/docs/en/costs)). The October 7, 2026 notice withdrew the Agent SDK monthly credit for Pro; a Pro subscription is not API funding. Record the actual authentication class and model before treating a run as covered, and do not borrow credentials to force a subscription into another client. Use [`../../models/routing.yaml`](../../models/routing.yaml) as advice; host settings decide the model.
