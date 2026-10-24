# Context pack provenance

The pack output serializer adapts `calculateMarkdownDelimiter` and the explicit content/provenance construction in `src/core/output/outputGenerate.ts` from yamadashy/repomix, commit `e696384d062f08f0246ffd2580d5a206484fc0a4`, MIT, Copyright 2024 Kazuki Yamada. Its delimiter rule chooses one more backtick than the longest run in embedded content, with a minimum of three. Context ports that rule to Python in `scripts/context_pack.py::_fence`; the JSON render uses explicit source metadata and exact content fields. The upstream regression in `tests/core/output/outputGenerate.test.ts` (nested backtick fences) is adapted by `test_fence_adaptation_and_budget`, which checks a longer embedded run and Unicode in the pack serializer.

The upstream `src/core/packager.ts` was inspected as an orchestration reference. Context does not adopt its collection, worker, cache, tokenizer, or output stack. The implementation retains only the narrow fence rule and a local serializer regression. Local changes include source-bound records, persistent preview identity, no-follow descriptor reads, hard wire budgets and a two-format export. The donor's full license text is retained below.

## Structural source selection

Repomix was inspected at the same pinned revision for the structural source-selection boundary: `src/core/file/fileProcessContent.ts` uses best-effort compression with exact-content fallback; `src/core/treeSitter/parseFile.ts` orders captured chunks by original source position and returns fallback on parser failure; `src/core/treeSitter/parseStrategies/PythonParseStrategy.ts` selects Python decorators, class/function signatures and docstrings; `src/core/treeSitter/queries/queryPython.ts` identifies comments, docstrings, imports, declarations and type aliases. `tests/core/file/fileProcessContent.test.ts` exercises exact fallback when parsing is unavailable or throws; `tests/core/treeSitter/parseFile.test.ts` checks retained chunk order. These files are MIT licensed under the copyright notice below. Context does not copy their implementation or add Tree-sitter; it reproduces the relevant extraction and fallback principles with Python's standard-library AST and exact tracked byte spans, then adds source-hash replay and explicit omitted ranges. The Python query's import/type-alias/documentation coverage informed the selected AST cases. No code from these files is vendored.

MIT License

Copyright 2024 Kazuki Yamada

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Fresh-session reconstruction

The session reconstruction boundary was informed by Pi's `packages/coding-agent/src/core/session-manager.ts`: `buildContextEntries` follows the selected leaf branch and treats the latest compaction as a summary boundary, while `buildSessionProjection` retains source entries separately from projected messages. The cached source's actual `MANIFEST.json` identifies pin `8a2ebd38549c3521a02db0e5d758a24320e97f94` and its file URL; an earlier task packet named `8c03fef4d3b7ecf7a9e8cc5b1312ff60ec2be149`, so the packet pin is not represented as inspected. The selected snapshot was retrieved at `2026-10-23T12:39:48.193163+00:00`. Its MIT license and copyright were inspected. Context reproduces only the separation of exact historical records from user-authored synthesis and fresh-session context; no Pi code or runtime was copied, so no additional donor notice is required. This handoff does not implement Pi session resume, branch traversal, compaction, provider delivery, or model obedience.
