# Context pack provenance

The pack output serializer adapts `calculateMarkdownDelimiter` and the explicit content/provenance construction in `src/core/output/outputGenerate.ts` from yamadashy/repomix, commit `e696384d062f08f0246ffd2580d5a206484fc0a4`, MIT, Copyright 2024 Kazuki Yamada. Its delimiter rule chooses one more backtick than the longest run in embedded content, with a minimum of three. Context ports that rule to Python in `scripts/context_pack.py::_fence`; the JSON render uses explicit source metadata and exact content fields. The upstream regression in `tests/core/output/outputGenerate.test.ts` (nested backtick fences) is adapted by `test_fence_adaptation_and_budget`, which checks a longer embedded run and Unicode in the pack serializer.

The upstream `src/core/packager.ts` was inspected as an orchestration reference. Context does not adopt its collection, worker, cache, tokenizer, or output stack. The implementation retains only the narrow fence rule and a local serializer regression. Local changes include source-bound records, persistent preview identity, no-follow descriptor reads, hard wire budgets and a two-format export. The donor's full license text is retained below.

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
