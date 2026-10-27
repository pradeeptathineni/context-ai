# Static diagnostics

`scripts/static_diagnostics.py` exposes one bounded, read-only check for tracked
TS/JS syntax and Python syntax. It reuses the existing TypeScript LanguageService
worker and import-impact safe reader/AST parser. The check does not read project
`tsconfig`, load plugins, packages, external dependencies or standard-library
types, and never executes project code. It is not a type checker or a whole
project correctness claim.

The host supplies the exact repository root and installed runtimes:

```sh
python scripts/static_diagnostics.py \
  --project /absolute/configured/project/root \
  --node /absolute/configured/node \
  --typescript /absolute/installed/typescript/lib/typescript.js
```

The host must configure those paths; the request must not come from project
source or a browser. The command emits JSON on stdout and a non-zero exit with
`{schema, schema_version, error:{kind,message}}` if safe bounded analysis could
not complete. It is a single capture/analyze/recheck operation. `stable: true`
means the Git head/index/status, TypeScript snapshot, Python source hashes,
analyzer files and runtime identities agreed across the checks. Capture is
non-atomic; an edit and revert between checks can escape detection.

Success uses `context.static-diagnostics.v1`. `status` is `complete` only when
the captured syntax profile has no omitted or unsupported files, uncited
diagnostics, or file-level unknown reasons; otherwise it is `partial`. Every
tracked source candidate in scope has a file row with relative `path`,
`language`, `status` (`analyzed`, `unsupported`, or `omitted`), `sha256` when
bytes were captured, parser diagnostic count, bounded diagnostics, and any
reason/unknown qualification. Unsupported language rows are never presented as
clean. Non-source, untracked, generated, vendor, cache, secret-style, symlinked
and submodule paths remain outside source parsing and are reflected in the
coverage qualifications/counts where path disclosure is safe.

TS/JS rows contain TypeScript syntactic diagnostics only. Python rows use
`ast.parse`; Python syntax error offsets are converted from code-point offsets.
Each diagnostic contains a stable `diagnosticId`, parser `code`, `message`,
`severity` (`error`, `warning`, `suggestion`, or `info`), `path`,
`fileSha256`, and `range`. `diagnosticId` is lowercase hex SHA-256 over compact
UTF-8 JSON with ordinally sorted keys for exactly `{path,fileSha256,code,
severity,range}`; the message is excluded. JSON uses UTF-8 scalar strings,
`ensure_ascii=false`, and no whitespace. Positions use 1-based lines and
1-based UTF-16 code-unit columns, with an end-exclusive endpoint. No source
excerpt is returned.

`files[].diagnostic_total` is the parser-reported count before location and
response filtering. `coverage.diagnostics.total` is the sum of those per-file
totals; `returned` is the number of serialized diagnostic rows; and `omitted`
is `total - returned`, including findings without valid locations and findings
outside the response cap. Thus `returned` equals the sum of per-file diagnostic
array lengths, and each array length is at most its `diagnostic_total`.

`source_digest` is Context-local: sort captured `{path,sha256}` rows by UTF-8
path bytes, then SHA-256 the concatenation of `path_utf8`, NUL, and the raw
32-byte file hash for each row. `snapshot.id` is SHA-256 of compact UTF-8 JSON
with sorted keys over the schema/policy, Git head/index/status hash, this source
digest, the existing code-navigation snapshot identity, analyzer file
path/hash rows, and configured Python/Node/TypeScript identity. Consumers must
validate each analyzed relative path and SHA against their own before/after
inventory; they must not compare `source_digest` to an unrelated aggregate
snapshot digest.

The response publishes file, byte, total-byte, diagnostic, and worker timeout
limits. Exceeding a hard read/engine limit returns a bounded error instead of a
partial parse claim. Dynamic imports and runtime-dependent behavior remain
unknown. No diagnostic establishes type correctness, runtime correctness,
security, or absence of defects.
