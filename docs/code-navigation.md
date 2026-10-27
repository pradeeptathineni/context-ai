# TypeScript and JavaScript code navigation

`scripts/code_navigation.py` answers four questions about tracked TS/JS source in an explicitly selected Git checkout: where is this symbol defined, where is it referenced, who calls it, and what does it call. The installed TypeScript LanguageService resolves the relationships. Context captures the source, bounds the request and validates every returned location against the captured bytes. The [repository map](repo-map.md) remains a lexical ranking and [import impact](import-impact.md) remains Python-only; neither resolves TS/JS symbols.

## Engine configuration

The trusted host supplies two absolute paths: a Node executable and an installed TypeScript 6.x `typescript/lib/typescript.js`. They never come from a query, a selector or the target project. Context does not install, download or update either; a missing or relative path is an `engine_unavailable` error. Only `scripts/code_navigation.mjs` loads the module.

## Search, inspect, open

```sh
NODE=/absolute/path/bin/node
TS=/absolute/path/node_modules/typescript/lib/typescript.js
python -m scripts.code_navigation search /absolute/checkout add --node "$NODE" --typescript "$TS"
python -m scripts.code_navigation inspect /absolute/checkout \
  --selector-json '{"file":"src/a.ts","sha256":"<file sha256>","line":1,"column":17,"endLine":1,"endColumn":20}' \
  --expected-snapshot "<snapshot.id from search>" --node "$NODE" --typescript "$TS"
```

1. `search` returns matching declarations, each with a `location`.
2. Pass one whole `location` as the selector and the search's `snapshot.id` as the expected snapshot. `{file, line, column, sha256}` also works; `selected` is then a zero-length span at that position.
3. `inspect` returns `selected`, `definitions`, `references`, `incoming` and `outgoing`.
4. To open a location, confirm the file still has `sha256`, then go to `line` and `column`.

A `Location` is `{file, sha256, line, column, endLine, endColumn}`. `file` is repository-relative and `sha256` covers the complete captured file bytes. Lines are 1-based and split at LF, CRLF and CR. Columns are 1-based and count UTF-16 code units, as in LSP; the end is exclusive. A UTF-8 byte-order mark counts as one column on line 1.

The same flow from Python:

```python
from scripts.code_navigation import inspect_symbol, search_symbols

found = search_symbols(project, "add", node_executable=NODE, typescript_path=TS, max_results=50)
detail = inspect_symbol(project, found["symbols"][0]["location"], expected_snapshot=found["snapshot"]["id"],
                        node_executable=NODE, typescript_path=TS, max_results=100)
```

Both functions are synchronous. They raise `NavigationError`, a `ValueError` whose `kind` is one of `invalid_request`, `project`, `limits`, `stale_snapshot`, `engine_unavailable`, `engine_unsupported`, `engine_failed`, `engine_timeout` or `engine_reply`. The CLI prints only JSON on stdout. On error it prints `{schema, schema_version, error: {kind, message}}` and exits 2. Neither writes to the project or runs its code.

## Output

Every response has schema `context-ai/code-navigation/v1`, `schema_version` 1, `engine` (`name`, `version` and the `sha256` of the loaded `typescript.js`), `snapshot` (`id`, `head`, `dirty` and `files` with `path` and `sha256`), `limits`, `diagnostics` (`kind`, `message`) and `qualifications`.

- Search adds `query`, `symbols` (`name`, `kind`, `container`, `location`) and `omitted.symbols`. Matching is TypeScript navigate-to: exact names first, then prefix, substring and camel-case matches.
- Inspect adds `selected`, `definitions` (`name`, `kind`, `location`), `references` (`location`, `isDefinition`, `isWriteAccess`), `incoming` and `outgoing` (`name`, `kind`, `location`, `sites`), and `omitted` counts for those four lists. Incoming `sites` are in the caller's file; outgoing `sites` are in the selected function's file.

Lists are sorted by file, position and name, and exact duplicate locations are merged. `kind` values are the engine's strings, such as `function`, `const` or `alias`. Location hashes and the snapshot come from Context's capture, not from the worker.

## What is read

Tracked regular files ending in `.ts`, `.tsx`, `.mts`, `.cts`, `.js`, `.jsx`, `.mjs` or `.cjs`, including declaration files, must also pass the [repository map](repo-map.md) path policy. Symlinks, submodules, secret-like names and directories, and generated, vendor or cache directories such as `node_modules` and `dist` are excluded. `.mts` and `.cts` are added to that policy's extension list. Untracked files, `tsconfig.json`, `jsconfig.json`, `package.json` and other configuration are never read. Reads use the existing descriptor-relative, no-follow reader.

Limits are 5,000 tracked files, 256,000 bytes per file and 8,000,000 bytes in total. An admitted file over a limit, or any unsafe read, refuses the request instead of indexing part of the project. Files that are not UTF-8 or contain NUL are excluded with a diagnostic. Each result list holds 1–200 entries (default 50 for search, 100 for inspect). A call shows at most 20 sites. Responses show at most 20 diagnostics plus a count of the rest. The worker reply is capped at 4 MiB and its run at 60 seconds.

## Snapshot and staleness

The snapshot id hashes HEAD, the index records, porcelain status, the bytes of every captured file (including excluded non-text files), the TypeScript and worker file hashes, the Node path and the fixed compiler policy. `inspect` recaptures and refuses a different `expected_snapshot`. A second edit to an already-dirty file is therefore refused even though `git status` prints the same text. After every engine run, Context captures again and refuses to return if anything changed. Capture is still non-atomic: a change reverted between the two reads is not observed. `dirty` reports Git status; it does not show which bytes match HEAD.

## Engine boundary and fidelity

The Node worker receives the captured text on stdin and serves it from an in-memory file map rooted at `/project`. Every LanguageService host callback — file and directory existence, reads, listings, `realpath` and script snapshots — answers from that map only. Module resolution is hooked so that only `./` and `../` specifiers resolve, and only to captured files. Node runs from the Context `scripts/` directory with only a default `PATH` in its environment, so `NODE_OPTIONS` cannot inject code, and the worker emits locations, names and bounded diagnostics, not source text. This isolation comes from the host implementation, not an OS sandbox: the trusted TypeScript module runs with Node's normal permissions.

The compiler options are fixed: `allowJs`, `checkJs`, `jsx: preserve`, `module: esnext`, `moduleResolution: bundler`, `noLib`, `noEmit` and `types: []`. This has consequences:

- Path aliases, `baseUrl`, packages, `@types` and the standard library are not loaded. A non-relative import is an `unresolved_module` diagnostic, so `import { helper } from "@app/helper"` stays unresolved even when the project's tsconfig maps it.
- Without library types, relationships that depend on inferred or built-in types, such as some method calls, can be missing. Direct identifiers, relative imports and renamed imports do not need them.
- Definitions follow TypeScript go-to-definition, which skips an import alias to the original declaration when the import resolves.
- References follow TypeScript find-all-references and flatten its groups. References to `add` include a renamed local `sum` and its uses. `isDefinition` is true for each group's own declaration, so an import alias can appear as a definition.
- Calls are one hop. If the selected position is not a callable declaration or a call target, `incoming` and `outgoing` are empty and a qualification says so.
- Syntax errors are reported per file, and results in that file may be incomplete.

## Implementation choice and provenance

Deep needs compiler-resolved TS/JS locations. Context's existing producers are lexical or Python-only. The TypeScript LanguageService is TypeScript's own maintained implementation of these editor queries, and the host already has it installed. Context reimplements no parsing or resolution. It adds the safe capture, the in-memory host, bounds and reply validation. The worker calls `getNavigateToItems`, `getDefinitionAtPosition`, `findReferences`, `prepareCallHierarchy`, `provideCallHierarchyIncomingCalls`, `provideCallHierarchyOutgoingCalls`, `resolveModuleName` and `getNameOfDeclaration`.

TypeScript 6.0.3 is Apache-2.0. Context loads the installed package at runtime and copies none of its source, so the license and third-party notices stay with that package and Context adds no notice file. Each response's `engine.sha256` records the exact file that was loaded.

[Graphify](https://github.com/Graphify-Labs/graphify/tree/92741d162b2094ffc2fed58cfbd8ee823e9da62c) builds broader multi-language tree-sitter graphs with impact views and a cache. Its code-only CLI was inspected, but its runtime and grammar closure are not qualified. It remains the stronger future multilingual option and is not folded into this TypeScript path. Aider already informed the lexical repository map.

`tests/test_code_navigation.py` runs the real compiler named by `CONTEXT_TYPESCRIPT_PATH` and `CONTEXT_CODE_NAV_NODE` (Node falls back to `PATH`) against disposable synthetic Git repositories. Without them, the compiler tests skip with a configuration hint. These tests establish behavior on synthetic fixtures. They do not establish completeness on real projects or usefulness to people.


### Exact source excerpt

`inspect_symbol` also returns `excerpt: {location, text, truncatedBefore,
truncatedAfter}` from the same captured source and snapshot. Its `location`
uses the normal relative file, SHA-256 and exact 1-based UTF-16 range. `text`
is exactly that slice, with up to four nearby lines on either side and at most
4,096 UTF-16 units. A long or minified line can be sliced mid-line; flags state
whether content before or after the excerpt was omitted. A surrogate pair or
CRLF is never split. The selected start position is included; a longer selected
span may extend beyond the excerpt. `limits.max_excerpt_utf16_units` reports the
cap. To read a returned reference or call site, inspect that exact `location`
with the same `snapshot.id`; clients need no independent filesystem reader.
