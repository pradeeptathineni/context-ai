# Project loadouts

A manifest selects resources; a resolved lock pins their bytes; a use receipt records what was actually read or run. These have separate files and purposes.

Run `python3 scripts/context_ai.py list` or `explain standard`. Use Python 3.10+ with the pinned dependencies in `requirements.txt`; installation is explicit, for example in a project-local virtual environment. No global installer or inference call is needed.

`plan standard context-authoring --project /absolute/project --provider codex` prints a proposed lock without writing. `apply` with the same arguments copies selected resources into `.context-ai/resources/`, installs only selected skill routers in `.agents/skills/`, and appends one managed routing block to root AGENTS.md. Read the plan first. Existing project instructions and explicit user requirements remain authoritative. The manifest never authorizes commands or network access.

`verify --project /absolute/project` checks managed bytes and required capabilities. `undo --project /absolute/project` removes owned files only if unchanged; edited files remain with a conflict report. `refresh` produces a proposed new lock and file diff on stdout without activating it. Run apply separately at a checkpoint after review. Checks are recipes for the agent to execute with existing authority, never arbitrary commands run by the composer.

The bootstrap supports `standard`, `context-authoring`, and `research-evidence`. Native discovery in this active desktop session is not inferred from filesystem installation: explicitly read the selected instruction files and record `explicit-read` until the supported client shows discovery. Reopen the project in a fresh trusted session for metadata discovery.
