# Browser verification

Source-supported tooling: [Playwright](https://playwright.dev/docs/test-snapshots) and [axe integration](https://playwright.dev/docs/accessibility-testing), reviewed 2026-10-05. Use the project's existing browser facilities or explicit scoped test dependencies; record unavailable tools rather than inventing results.

Build and serve the distributed output. Test real navigation, focus, forms or relevant states, failure recovery, reduced motion and responsive widths. Capture and inspect desktop/mobile full-page screenshots. Review hierarchy, typography, density, overflow, footer and interaction states. Run a deliberate critique/revision pass and confirm affected checks. Fix relevant console/network errors and serious accessibility defects.

Keep screenshots, interaction/axe findings, build/asset observations and changes attributable to review. Distinguish visual judgment, deterministic results, builder proxy and human approval. No screenshot-diff baseline is visual approval; no fixture proves a private production website.
