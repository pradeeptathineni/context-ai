# OpenAI Codex adapter

Reviewed: 2026-09-12

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
- Use nested `AGENTS.md` files only for genuinely narrower path-specific guidance; do not copy the root instructions into them.
- Restart the run after changing instruction files when the active session must receive the new chain.

## Codex configuration boundaries

Personal defaults live in `~/.codex/config.toml`. Trusted repositories may add scoped `.codex/config.toml` files; project layers are applied from the root toward the working directory, with the closest layer winning. CLI flags override configuration files.

Model access depends on the Codex surface, client version, authentication method, plan or workspace controls, and rollout. Treat [`../../models/routing.yaml`](../../models/routing.yaml) as a reviewed policy, then verify that the selected binding and reasoning level are available in the active host.

Do not place copied `AGENTS.md`, `AGENTS.override.md`, or other active instruction filenames under `sourced/`. Rename any qualifying archival snapshot and record its original name and provenance.
