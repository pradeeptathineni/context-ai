# Evidence and claim discipline

Use with [research](../core/research.md), [testing](../core/testing.md), and [review](../core/review.md) when reporting a capability, audit, benchmark, release, or recommendation.

## Name the evidence class

Keep these observations separate:

- **Fixture or deterministic:** a controlled input and local check establish exact behavior under declared conditions.
- **Configured live:** the actual provider, credentials, data path, and environment were exercised and observed.
- **Builder proxy:** the implementer ran a plausible representative task; it can find defects but is not independent validation.
- **Independent review:** a reviewer checked the artifact against requirements and evidence without simply trusting the builder's summary.
- **Visual or browser:** a rendered or interactive surface was inspected; static source checks do not substitute for this.
- **Human usefulness:** people in the intended role tried the workflow and their behavior or judgment was recorded.

A green CI run proves its configured checks passed. It does not prove live integration, hostile-code isolation, usefulness, or absence of vulnerabilities. A mock or synthetic fixture can establish a mechanism without establishing deployment conditions. If a check was unavailable, state the precise gap; do not imply success or invent a fallback.

Keep planned, imported, drafted, implemented, verified, and published states distinct. A researched option is not an adopted tool; an imported exercise is not a completed lab. Do not let generated catalogs or polished prose silently promote either one.

## Trace consequential claims

For each consequential assertion, preserve the source or receipt, version or revision, inputs, method, date, relevant configuration, and result. Distinguish direct observation, source claim, inference, and recommendation. Report negative controls and failure paths when they could overturn the conclusion. For benchmarks, state the baseline, workload, exclusions, all attempted runs, and practical uncertainty. For an external write, verify the destination state instead of relying on the command exit status.

Protect existing data and provenance during verification. Use named disposable databases, fixtures, and isolated state for destructive checks. Inspect transitive scripts before running them against retained data. Preserve migrations, immutable receipts, old replay semantics, and unrelated work. Never reset, clean, stash, or rewrite retained history merely to make a test easier.

Make the human summary smaller than the evidence, but keep the evidence reachable. Prefer a plain action and its limit over an internal score or implementation inventory on the first screen.
