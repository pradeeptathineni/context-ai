# Task context packs

Context can collect a task's exact source excerpts and explicitly selected Context guidance into a persistent preview. The operator chooses the Git project and task, reviews ranked candidates, adjusts by item ID, then exports a frozen text or JSON render. A preview ID can be reopened after process restart. Export checks the current source observations and rereads each bound tracked file; changed sources fail with `source_drift` and need a new scan.

Run the CLI from this checkout. The private store must be outside both the project and Context checkout:

```sh
python scripts/context_pack.py candidates --project /path/to/project --store /private/context-packs --task "change total pricing" --guidance guidance:core/testing.md
python scripts/context_pack.py preview --project /path/to/project --store /private/context-packs --candidates CANDIDATE_SET_ID --max-tokens 2000
python scripts/context_pack.py export --project /path/to/project --store /private/context-packs --preview PREVIEW_ID --format json
```

The Python entry point is `ContextPackService(project, *, store, context_root=..., project_id=...)`. Its `candidates(task, focus=(), guidance_ids=())`, `preview(candidate_set_id, include_ids=None, exclude_ids=(), max_tokens=2000)`, and `export(preview_id, format="text")` methods accept configured source roots and saved IDs. `ContextPackError` exposes stable `code` and bounded `message` values.

Source excerpts are exact UTF-8 bytes from tracked regular files allowed by the repository map's path policy. One deterministic window contains up to 40 complete `splitlines(keepends=True)` lines, beginning at the first ranked symbol line or line 1 for a focused file without symbols, and is omitted whole if it exceeds 4,096 bytes. CRLF and missing final newlines are retained. Guidance IDs use `guidance:<registered-resource-path>` and resolve through Context's active dependency registry. Guidance, dependencies, support data and required source notices are carried as full bytes; guidance is advisory and never changes native instructions or permissions.

The store contains private, mode-0600 immutable JSON records inside a mode-0700 directory. It is bound to configured roots and project ID. Both complete wire formats are capped at four UTF-8 bytes per requested token; estimates are `ceil(bytes/4)`, not provider token counts. `--output` only creates a new file, outside both source trees. The filename/path exclusion policy is not secret detection; inspect any export before external delivery. No installation, model call, clipboard, upload or automatic agent delivery occurs.

Unknown languages use the repository map's lexical declaration/reference scan; malformed/deep Python and unsupported/binary files are omitted with bounded diagnostics. See [provenance](context-pack-provenance.md) for the serializer adaptation.
