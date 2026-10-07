# Markdown compatibility

A neoma note must remain usable outside neoma — in a plain text editor, VS Code,
Obsidian, Logseq, Joplin (after import), GitHub, and other Markdown applications.

## Base syntax

CommonMark plus GitHub Flavored Markdown (GFM): headings, bold, italic,
strikethrough, ordered/unordered lists, task lists, blockquotes, inline code, fenced
code blocks, tables, horizontal rules, footnotes, links and images.

## Extensions neoma understands

| Syntax                                      | Meaning             | Compatibility notes                                                 |
| ------------------------------------------- | ------------------- | ------------------------------------------------------------------- |
| `[[Note Name]]`                             | Wiki link           | Understood by Obsidian, Logseq, and most PKM tools                  |
| `[[Note Name\|Shown text]]`                 | Aliased wiki link   | Same                                                                |
| `[[Note Name#Heading]]`                     | Heading link        | Same                                                                |
| `![[file.png]]`                             | Embed               | Obsidian-style; falls back to visible text elsewhere                |
| `#tag`                                      | Tag                 | Common convention; plain text elsewhere                             |
| `==text==`                                  | Highlight (yellow)  | Obsidian/Typora convention                                          |
| `<mark data-color="blue">…</mark>`          | Coloured highlight  | Documented HTML subset; shows as normal text elsewhere              |
| `> [!note] Title`                           | Callout             | Obsidian/GitHub alert convention; renders as a blockquote elsewhere |
| `> [!toggle]- Title`                        | Collapsible section | Renders as a blockquote elsewhere (content stays visible)           |
| `> [!theorem]`, `[!definition]`, `[!proof]` | Academic blocks     | Blockquote fallback elsewhere                                       |
| `Question:: …` / `Answer:: …`               | Flashcard           | Plain text elsewhere (LogSeq-compatible field syntax)               |
| `$…$`, `$$…$$`                              | Math (KaTeX)        | Pandoc/Obsidian convention                                          |
| `[@citekey]`                                | Pandoc citation     | Preserved verbatim; searchable in neoma                             |

Everything degrades gracefully: in tools that don't know an extension, the note is still
readable plain text.

## Frontmatter

Standard YAML between `---` fences:

```yaml
---
title: Transformer Experiment 01
created: 2026-07-20
modified: 2026-07-20
type: experiment
status: active
tags:
  - transformers
  - experiments
aliases:
  - Attention Experiment
---
```

Fields neoma reads: `title`, `created`, `tags`, `aliases`, `type`. **Unknown fields are
preserved, never deleted.** If a frontmatter block cannot be parsed, neoma treats it as
opaque text and refuses to rewrite it.

Academic-workflow fields recognised as note properties: `doi`, `bibtex-key`,
`zotero-uri`. Pasting BibTeX into a fenced code block is preserved without alteration.

A page's colour is stored as a `color:` frontmatter field (one of yellow, green, blue,
purple, red, orange, grey) — portable, and ignored by tools that don't use it. Attachment
colours are a neoma-only convenience stored per-vault in the browser, not in the files.

## Coloured highlights

Yellow highlights use the portable `==text==` syntax. Other colours use a **documented,
minimal HTML subset** — `<mark data-color="green">…</mark>` with one of seven named colours
(yellow, green, blue, purple, red, orange, grey) and no other attributes. neoma's renderer
recognises exactly this shape; any other raw HTML in a note is dropped for safety. In tools
that don't style it, the text still shows normally. Highlights are preserved on export.

## Page hierarchy (folder notes)

A page that has subpages is stored as a folder plus an index note of the same name:

```text
Machine Learning/
├── Machine Learning.md     ← the page itself
├── Regression.md           ← a subpage
└── Neural Networks.md      ← a subpage
```

This is an ordinary folder layout — no database, no hidden index. Other Markdown tools see
plain folders and files.

## What neoma never writes into your files

- No random IDs or hidden markers
- No proprietary syntax (page hierarchy is plain folders; highlights are documented HTML)
- No rewriting of notes you didn't edit (except the explicit, user-approved link update
  after a rename — and then only the link targets change)

## Importing from other tools

- **Obsidian**: a vault folder is already compatible — open it directly (folder vault)
  or ZIP it and import. `.obsidian/` config folders are ignored.
- **Logseq**: Markdown graphs open fine; journal files map to daily notes if you set the
  daily-note folder/format to match.
- **Joplin**: use Joplin's "Export → MD" and import the resulting folder/ZIP.
