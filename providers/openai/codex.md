# OpenAI Codex adapter

Reviewed: 2026-10-05

This file describes how Codex receives repository context. It does not replace the provider-independent guidance in [`../../core/`](../../core/).

## Instruction discovery

Codex builds its repository instruction chain once when a run starts.

1. In the Codex home directory, it reads `AGENTS.override.md` when present; otherwise it reads `AGENTS.md`.
2. From the project root, normally the Git root, through the current working directory, it selects at most one instruction file per directory: `AGENTS.override.md`, then `AGENTS.md`, then configured fallback filenames.
3. It concatenates selected files from broadest to narrowest scope. Guidance closer to the working directory appears later and takes precedence when instructions conflict.

An override replaces the regular file in the same directory; it does not supplement it. Empty files are skipped. The combined project-instruction limit defaults to 32 KiB and is configurable with `project_doc_max_bytes`.

`AGENTS.md` is ordinary Markdown. Codex does not define an import directive that expands arbitrary referenced files into the instruction chain. A repository file can tell Codex to read another file when relevant, as this repository's root [`AGENTS.md`](../../AGENTS.md) does, but the referenced content is loaded only when the agent reads it.

## Using context-ai

- Keep the consuming project's `AGENTS.md` short and route tasks to the relevant `core/` files.
- Make referenced context available inside the workspace through copied files, a submodule, or another explicit retrieval mechanism the project controls.
- Load provider-independent files for the task first. Load this adapter only when Codex discovery or configuration affects the work.
- For a tooling decision, use [`../../concepts.yaml`](../../concepts.yaml) to find the job, then inspect matching [shared signals](../../signals/common.yaml) and [OpenAI signals](signals.yaml). Follow source IDs in [`../../sources.yaml`](../../sources.yaml); signals nominate candidates and do not activate capabilities.
- Use nested `AGENTS.md` files only for genuinely narrower path-specific guidance; do not copy the root instructions into them.
- Restart the run after changing instruction files when the active session must receive the new chain.
- For a user-level entry point across repositories, use the short candidate router in [`../../docs/adoption.md`](../../docs/adoption.md). Keep the canonical hierarchy in the Git repository; a local `~/.ai/context-ai` checkout or pointer can make it reachable without copying its contents into each project.

## Codex configuration boundaries

Personal defaults live in `~/.codex/config.toml`. Trusted repositories may add scoped `.codex/config.toml` files; project layers are applied from the root toward the working directory, with the closest layer winning. CLI flags override configuration files.

Model access depends on the Codex surface, client version, authentication method, plan or workspace controls, and rollout. Treat [`../../models/routing.yaml`](../../models/routing.yaml) as a reviewed policy, then verify that the selected binding and reasoning level are available in the active host.

`model_reasoning_effort` is a native configuration setting. An instruction file or prompt tag does not change the current run's model or effort. Use the product control or start a new session with a supported configuration; follow [`../../custom/model-deliberation.md`](../../custom/model-deliberation.md) for the task-level choice.

Do not place copied `AGENTS.md`, `AGENTS.override.md`, or other active instruction filenames under `sourced/`. Rename any qualifying archival snapshot and record its original name and provenance.

## v1 project delivery

The supported adapter is `python3 scripts/context_ai.py`, with an explicitly identified project and `--provider codex`; see [the command contract](../../docs/loadouts.md). It creates project-local `.agents/skills/context-*` routers and one concise AGENTS block over pinned resources. It preserves the preexisting standard skill and user/global settings. Do not equate writing these files with discovery in a running desktop chat. This run used explicit-read and validated materialization; a refreshed client's skill metadata is a separate observation. No exposed in-session skill-list reload mechanism was available here, and no unbounded model run or trust bypass was used to simulate one.

Upstream source snapshots use inactive names outside auto-discovery paths. Selected Impeccable documentation works through the instruction-only adapter; native binary/hooks/extensions are not supported or activated. Required resources fail clearly; optional runtime commands are presence checks followed by project recipes, not entitlement or configured-live proof.
