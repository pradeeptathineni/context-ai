# Public portal appearance checks — 2026-11-03

This is a local builder check of the checked-in public catalog, profiles and trials. It is not an installed-guidance trial, a private consumer read, UAT or evidence of task benefit. The authored HTML/CSS/controller and static build manifest changed; `scripts/build_catalog.py` and generated catalog content did not.

The existing MIT `@deep/theme` candidate owns the six palettes, semantic tokens and validation. Context adapts Monitoring's browser controller and owns its CSS mapping and `context-ai.appearance.v1` storage key. [Exact archive, source, license and adaptation hashes](portal-appearance-source.json) preserve the distinction between the declared candidate revision and locally verified bytes. No navigation shell is needed by the portal's existing tabs.

## Results

- The built portal passed at 320, 390, 768 and 1440 pixels, with all six shared presets. Across Appearance and the three existing views, 96 axe scans reported zero violations. There were no detected horizontal overflows or browser errors.
- Existing filter/empty/reset, inert source markup, public profile choices, canonical protected conflict, profile request download, command preview, negative trial, skip link, tab arrows/Home/End and reduced-motion checks passed. Profile export sent zero requests and still installed nothing.
- Appearance followed system changes; explicit choices survived reload; valid compact density persisted; unsafe white-on-light overrides were refused without replacing the current value. A second tab changed/reset the first tab. A separate Deep preference key remained unchanged.
- Invalid saved preference versions fell back visibly without overwriting the saved bytes. Throwing Storage methods and a throwing `localStorage` getter retained page-local choices and a usable populated Signals profile, with an explanatory status. The shortcut reveals Appearance when a failure message would otherwise be hidden.
- The existing shortcut responded to Enter and Space; the native preset select accepted focus and Tab advanced to the next control. Headless macOS did not change the native select menu with Arrow/Home probes. Native menu selection is therefore unverified; no custom keyboard handler was introduced to work around that environment limitation.
- The builder inspected all six phone profile captures, the desktop Sand Light reading view and open Matrix Dark Appearance. Other desktop/phone preset and existing workflow captures are retained under `.examples-output/web-evidence/`. These are viewport captures, not a human-usefulness evaluation.
- An altered shared-module byte was rejected by the build checksum check; restoring the source allowed the build. Two repeat builds produced identical manifests. Catalog and product generation checks, Ruby repository validation, Ruff and whitespace checks passed.

The delivered files total **112,940 bytes**, up **25,037 bytes** from **87,903 bytes**. The former 90,000-byte limit was raised to 120,000 to retain the unchanged shared module, MIT license and existing validated browser controller rather than fork or strip the package. Only `theme/index.js` and `theme/LICENSE` from the upstream package enter the distribution; its README, declarations and standalone example remain source-only. No remote runtime, font, registry installation or paid request is required.

The old temporary quiet/expressive color button now chooses shared Neon 1 Light/Matrix Dark presets in the same persisted preference as Appearance. System is the default. This is the explicit compatibility change; public catalog selections, routes and installation authority remain unchanged.

## Broader repository check

Python 3.12.10 discovery ran all 425 tests in 644.102 seconds with 9 skips, 3 errors and 1 failure. The initial shell selected unsupported Node 16.20.0: the two `react-web` host subtests and one advertised-loadout subtest raised `Node 20+ is required`. The affected host test and advertised-loadout test passed with the existing Node 24.19.0 runtime (27.633 and 9.591 seconds respectively). Additional explicit capability/refresh cases also passed. A second complete Python discovery under Node 24 was not run.

`test_trials.ControlledTrials.test_real_native_boundary_and_both_trusted_recipes` remains blocked by the execution environment: native `sandbox-exec` returned exit 71, with stderr SHA-256 `d34a4e4359a4dc36526cf5b363da32f7b7594a3a09eea17cbdfd6425b052d93e` matching `sandbox-exec: sandbox_apply: Operation not permitted\n`. The isolation check remained unverified and no recipe executed. The trial implementation/tests are unchanged, and their source snapshot excludes the portal. That boundary was not relaxed or retried with broader permissions. This is a remaining full-suite environment limitation, not a passing native trial or installed-guidance result.

## Reproduce

Use the existing source development dependencies and supported Node runtime (this run used Node 24.19.0 and Playwright 1.58.2 with axe 4.11.1). No dependencies were installed during this task.

```sh
node examples/web/build.mjs
node examples/web/verify.mjs
APPEARANCE_ONLY=1 WEB_EVIDENCE_DIR=.examples-output/appearance-evidence node examples/web/verify.mjs
ruby scripts/validate.rb
.venv/bin/python scripts/build_catalog.py --check
.venv/bin/python scripts/build_product.py --check
.venv/bin/ruff check scripts tests
git diff --check
```

The browser verifier uses only an ephemeral loopback HTTP server and headless Chromium. `results.json`, captures and `build-evidence.json` under `.examples-output/` contain the measured local outputs. `build-integrity.json` records the bounded negative/determinism check. Axe does not certify WCAG conformance. There was no assistive-technology user test, deployed field measurement, cross-browser run or independent human-usefulness assessment.
