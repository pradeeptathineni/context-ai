---
name: standard
description: Use for substantial development, AI workflow design, or tooling choices where existing code, standards, maintained tools, or native Codex and ChatGPT capabilities may own the job. Skip trivial edits and settled repository workflows.
---

# Standard backpack

Use the current task, repository instructions, and actual environment as the authority for what is needed. This skill supplies a decision habit, not permission or a fixed tool stack.

## Before choosing a mechanism

For a substantial new capability, dependency, service, protocol, agent workflow, or development tool, **check prior art before building**. Name the job and its observable contract. Inspect the repository's current owner and decisions, then the relevant standard, native facility, maintained implementation, and smallest custom remainder. Read [prior-art](../../../custom/prior-art.md); use [patterns](../../../custom/patterns.md) when deciding ownership or architecture. A small edit within an established path needs no landscape review.

For an unfamiliar or consequential choice, use the [lookup script](../../../scripts/lookup.rb) from the context-ai checkout. Search a word such as `ruby scripts/lookup.rb --search "review"`, then retrieve a single ID such as `ruby scripts/lookup.rb quality.review --provider openai --product codex`. The command reads [concepts](../../../concepts.yaml), matching [common signals](../../../signals/common.yaml) and [OpenAI signals](../../../providers/openai/signals.yaml), and resolves [sources](../../../sources.yaml). Read the original source for the deciding claim. Do not open the full YAML files when the lookup supplies the relevant entries. The index is a candidate list, not a required stack; if no signal covers the job, research directly.

For Codex or ChatGPT, verify the chosen capability on the **active surface**, including model and reasoning controls, instruction discovery, skill or plugin availability, MCP permissions, hook coverage, command behavior, and worktree or subagent support when relevant. Installed or documented does not mean available or fitting in this host. Use first-party documentation for volatile product behavior. Do not add a hook, plugin, agent, or custom runtime merely because it exists.

## Make and finish the choice

Compare serious candidates on exact fit, authority, maintenance, license, privacy, cost, overlap, and removal. Use the project's existing decision artifact to record the chosen owner, tested evidence, unknowns, small residual, and revisit trigger. A repository screen supplies candidates; it is not a contextual assessment. Complete the authorized task and verify the behavior that matters.

Load only the relevant house guidance from [custom/README](../../../custom/README.md): AI mechanisms, orchestration, model deliberation, writing, comments, and evidence claims have separate files. Do not imply that reading this skill changed the active model, activated a plugin, installed a hook, or delegated work.
