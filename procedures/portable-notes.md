# Portable research notes for Neoma

Use when a project keeps research notes as Markdown in Git and has chosen to open them in Neoma (or another linked-note tool) as well. Plain Markdown in Git stays the canonical owner; Neoma is a reader and editor of the same files, never a second store.

Follow Neoma's pinned [Markdown compatibility reference](../sourced/neoma/markdown-compatibility.md) (AGPL-3.0-or-later, read as documentation; no Neoma code is installed by this procedure), with these rules:

- One note per source. YAML frontmatter with `title`, `tags` and the project's source fields (for example `source:` with the canonical URL and `accessed:` with the date); unknown fields are preserved by Neoma.
- Link notes with `[[Note Name]]` wiki links that resolve to existing note file names, and keep the original source as a normal Markdown link so it survives outside Neoma.
- Use only syntax the reference lists; everything else must degrade to readable text.
- Do not add Neoma app files, vault databases or exported ZIPs to the repository.

Check the result with the project's own checks. When a pinned Neoma build is available for a trial, its link graph and ZIP round trip are the external check: no broken links, every new note reachable, and byte-identical export and re-import.
