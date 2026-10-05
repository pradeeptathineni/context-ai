---
name: standard
description: Use for substantial development, AI workflow design, or tooling choices where existing code, standards, maintained tools, or native Codex and ChatGPT capabilities may own the job. Skip trivial edits and settled repository workflows.
---

# Standard backpack

Use the current task, repository instructions, and actual environment as the authority for what is needed. This skill supplies a decision habit, not permission or a fixed tool stack.

## Before choosing a mechanism

For a substantial new capability, dependency, service, protocol, agent workflow, or development tool, **check prior art before building**. Name the job and its observable contract. Inspect the repository's current owner and decisions, then the relevant standard, native facility, maintained implementation, and smallest custom remainder. Read [prior-art](../../../custom/prior-art.md); use [patterns](../../../custom/patterns.md) when deciding ownership or architecture. A small edit within an established path needs no landscape review.

For Codex or ChatGPT workflow decisions, check the relevant native owner on the **active surface** before inventing a wrapper:

| Job | First native option to inspect |
| --- | --- |
| Durable repository or personal instructions | Codex scoped `AGENTS.md`; ChatGPT Personalization or project instructions on a supported surface. Memory is recall, not a required-rule store |
| Repeatable task procedure or role | Agent Skill; Record & Replay when capturing a demonstrated workflow; plugin when cross-surface distribution is needed |
| External application, account, or data | Installed plugin or MCP connection and its actual permissions |
| Command restriction or file invariant | `.rules` for exact command prefixes, a hook for covered tool events, CI for repository gates, or sandbox/OS permissions for a filesystem boundary; test the selected coverage |
| Model and reasoning level | Native model/effort controls and current availability |
| Independent parallel work | Native subagent/task and worktree facilities, when allowed and worthwhile |
| Review, diff, status, or scheduled work | Built-in command or automation for that surface |

Inspect only the categories relevant to the task. Verify availability and behavior in the current app, CLI, or host; an installed capability is not proof of access or fit. Use first-party documentation for volatile product behavior. Do not add a hook, plugin, agent, or custom runtime merely because it exists.

## Make and finish the choice

Compare serious candidates on exact fit, authority, maintenance, license, privacy, cost, overlap, and removal. Use the project's existing decision artifact to record the chosen owner, tested evidence, unknowns, small residual, and revisit trigger. A repository screen supplies candidates; it is not a contextual assessment. Complete the authorized task and verify the behavior that matters.

Load only the relevant house guidance from [custom/README](../../../custom/README.md): AI mechanisms, orchestration, model deliberation, writing, comments, and evidence claims have separate files. Do not imply that reading this skill changed the active model, activated a plugin, installed a hook, or delegated work.
