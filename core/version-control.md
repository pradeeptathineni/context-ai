# Version control

Source-supported fundamentals: [Git staging](https://git-scm.com/docs/git-add), [history](https://git-scm.com/docs/git-log), and [tags](https://git-scm.com/docs/git-tag), reviewed 2026-10-05. Local convention: [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) names intent; Git does not require it.

Inspect status, branch, remotes and the affected diff before changing history. Preserve tracked and untracked work. Stage explicit paths or reviewed hunks; verify the staged diff contains one coherent change. Write a message that explains the resulting behavior. Do not reset, clean, stash, force-push or rewrite retained history to make validation convenient.

A commit records a change, a branch names a moving line of work, a PR requests review/integration, an annotated tag identifies an immutable release point, and a release publishes notes/artifacts. Use each only when its role is needed. Fetch and inspect divergent remote history before ordinary pushes; resolve it without losing another contributor's commits. Push only with task authority.

Review comments should identify the trigger, consequence and justified fix. Separate blockers from advisory preference and acknowledge uncertainty. Before publishing a release, verify the tested commit at the intended remote, CI, tag target and release destination. See [versioning](versioning.md) and [review](review.md).
