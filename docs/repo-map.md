# Repository map

`scripts/repo_map.py` builds an optional, read-only map for a task in an explicitly selected Git checkout. It reports relevant tracked paths, conservative symbol names and definition lines, selection reasons, each selected file's SHA-256, the observed HEAD and dirty state, and omissions. It does not read untracked files, copy source text, install guidance, invoke a model, or write to the target project.

```sh
python3 scripts/repo_map.py --project /path/to/checkout --task "change total pricing" --focus src/pricing --max-tokens 1200
python3 scripts/repo_map.py --project /path/to/checkout --task "change total pricing" --format json
```

The Python API is `build_map(project: Path, task: str, *, focus=(), max_tokens=2000) -> dict`. Focus paths are relative to the selected repository and select a file or subtree. Invalid or escaping paths fail. The map includes tracked regular files with a documented source/config/document extension allowlist; it skips binary and unsupported files, `.env`/secret/credential-like names, `.pem` and `.key` files, lockfiles, generated/vendor/cache directories, symlinks and submodules. Limits are 5,000 tracked files, 256 KB per file and 8 MB total reads. Python symbols use the standard-library AST. Other file types use declaration and identifier patterns, so the map does not resolve calls or types. Malformed Python is skipped with a diagnostic.

The token figure estimates entry lines at roughly four characters per token. It is not a provider tokenizer guarantee; headings and omission diagnostics are outside the entry budget. A file digest describes the bytes read. HEAD identifies the repository revision, while `dirty` reports whether the checkout had any tracked or untracked changes; a dirty map's file digest must not be read as proof of HEAD contents. Files detected changing during a read are omitted.

## Implementation choice and provenance

The user-visible capability is a compact, task-ranked file and symbol map. Context's existing `scripts/context_ai.py` owns pinned context selection and delivery, not repository mapping, so this remains an optional producer that consumers may pass to an agent explicitly. The implementation uses Python's standard library and deliberately avoids an index/cache or parser dependencies: bounded one-shot reads fit the current consumer contract and keep the target repository untouched.

The design was informed by Aider's `RepoMap` at [`5dc9490bb35f9729ef2c95d00a19ccd30c26339c`](https://github.com/Aider-AI/aider/tree/5dc9490bb35f9729ef2c95d00a19ccd30c26339c), specifically task-mentioned file/name personalization, weighted ranking and finite-budget selection. The inspected donor files were `aider/repomap.py` and `tests/basic/test_repomap.py`; its license was Apache-2.0. This implementation was written against the Context contract and does not copy donor source code or tests. The donor's disk cache, tree-sitter, networkx, Pygments and grep_ast stack is not needed for this bounded standard-library producer. The donor snapshot's maintenance status was not independently rechecked for this implementation.
