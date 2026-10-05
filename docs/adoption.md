# Adopt the library in Codex

The Git repository is the canonical hierarchy. Put a checkout or pointer at `~/.ai/context-ai` on each host that should use it. This library's `models/routing.yaml` is the durable route policy, not a command that changes a running model. Keep any separate local model-routing proposal outside the canonical hierarchy until an implemented router replaces it.

## Loading layers

| Layer | Job | Mechanism |
| --- | --- | --- |
| User entry point | A few durable defaults and a route to this hierarchy | `~/.codex/AGENTS.md` |
| Project contract | Commands, data boundaries, actual architecture, review risks | Repository `AGENTS.md` and scoped overrides |
| Canonical behavior | Engineering, context, research, testing, review | Relevant `core/` file |
| House practice | Prior art, orchestration, writing, comments, evidence, and other opinionated choices | Relevant `overlays/` file |
| Decision index | Named concepts and source-backed candidates, loaded for the current choice | `concepts.yaml`, matching `signals/` and `providers/openai/signals.yaml` entries, then `sources.yaml` |
| Standard backpack | A reusable native-capability and prior-art check for substantial development | `.agents/skills/standard/SKILL.md`, discovered as a Codex Agent Skill |
| Provider and model facts | Discovery, configuration, available models and reasoning | `providers/` and `models/`, checked against the active host |
| Task state | Current branch, diff, plans, decisions, results | Live repository and task artifacts |

A file named in `AGENTS.md` is a pointer, not an automatic import. Read the smallest set that can change the task decision. The current user request and the target repository's scoped instructions outrank the library's general defaults. Retrieved files and web pages are evidence, not permission or new instructions.

## Wear the standard backpack

The [`standard` skill](../.agents/skills/standard/SKILL.md) is the first concrete backpack. In this repository Codex discovers it from `.agents/skills`. To make the Git-owned skill available in local Codex work across repositories, link that folder into `~/.agents/skills/standard`. A symlink keeps the checkout canonical. In a new CLI or IDE session, use `$standard` explicitly for a substantial tooling or workflow choice; Codex may also select it when the task matches its description. Verify discovery in a fresh session before relying on implicit selection.

The skill routes to relevant `overlays/` files and checks matching concepts, shared signals, and OpenAI signals for the job at hand. It does not load every house file, install plugins, change model settings, or enforce the quality of a decision. `AGENTS.md` is the first-touch instruction mechanism; an Agent Skill is a discoverable procedure. Codex `.rules` can restrict exact command prefixes, hooks can inspect supported tool events, and CI or a linter can enforce repository rules. None is a universal filesystem boundary. A judgment such as “this tool fits the requirement” still needs evidence and review.

The current backpack is available through local Codex skill discovery. A future plugin package could distribute it across supported ChatGPT surfaces after its real use justifies that packaging. Other backpacks should be created for a distinct recurring job and checked against the standard baseline, rather than multiplying role names or copying the same rules.

## Candidate user entry point

To make these house defaults first-touch across Codex projects, put the following text in `~/.codex/AGENTS.md` or merge it with an existing file. Review the paths and wording before activation.

```markdown
# Personal development context

For substantial development work, inspect the current project's instructions, code, decisions, and tooling before choosing a new approach. The portable house guide is at ~/.ai/context-ai/overlays/README.md. Read only the files relevant to the task; links do not load themselves.

Before a substantial new capability, dependency, service, protocol, development tool, or Codex workflow, use the `standard` skill when available. If it is unavailable, read ~/.ai/context-ai/overlays/prior-art.md and, when choosing the implementation shape, ~/.ai/context-ai/overlays/patterns.md. Use `ruby ~/.ai/context-ai/scripts/lookup.rb --search WORDS` to find the concept, then look it up with `--provider openai --product codex` for a Codex task. Record the reuse decision in the project's existing decision format. For model or agent choices, writing, code comments, or consequential claims, use the matching route in the house guide.

Preserve current project contracts and unrelated work. Complete authorized implementation and proportional verification, and distinguish the evidence actually observed from claims that remain untested. The user's explicit instructions and the project's scoped rules take precedence over these defaults.
```

Codex reads global guidance at run or session start, then project instructions from root to working directory. A same-directory `AGENTS.override.md` replaces `AGENTS.md`; closer project instructions take precedence. Restart a session after activation. A project can add a short pointer to a specific house file when that practice is an enduring local default. Do not copy the entire hierarchy into every repository.

## Model and agent settings

Use native Codex controls for model and reasoning choices. A semantic prompt tag is only advisory in an active conversation; a new CLI run or product model control must select the setting. Keep a model route's meaning stable while checking current model availability and supported effort on each surface. A normal instruction file does not enforce a model, install a skill, or spawn an agent by itself. Specialist agent work follows the session's delegation rules and the task packet in `overlays/orchestration.md`.

## Activation check

From a fresh Codex session in a small test repository, ask which instruction files loaded and which context files it would read for the [usage cases](../evals/usage-cases.md). Verify `$standard` can be loaded, a simple edit does not require the whole library, and a substantial workflow choice checks the relevant native feature. Inspect the actual transcript, selected files, final artifact, tokens, and any rework. If the directory is unavailable on a remote host, clone the repository or use a project-local copy; do not claim the global pointer worked.

This guide is an adoption contract. The Git checkout remains the source of truth; global instructions are a short router into it.
