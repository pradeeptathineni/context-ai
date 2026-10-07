# Research a decision with evidence

Use [research](../core/research.md) when a project decision needs current sources or comparative options. Context owns the final project-specific adoption decision; no external score grants install or execution authority.

## Choose the route

Pick the first route that can answer the actual question, and record which one was used:

1. **Official source**: current versioned documentation, specification, changelog or the candidate's source at an exact revision. Use [current docs](current-docs.md) for library/API versions.
2. **Already-verified resource**: an existing decision record, a pinned upstream in this library, or a project ADR whose evidence still applies.
3. **Direct investigation**: the host's own web/search tools against primary sources. Matt Pocock's pinned [research skill](../sourced/mattpocock/research/instruction.md) supplies the output shape: primary sources only, each claim cited, one Markdown file where the project already keeps notes. A background reader is optional and needs host support and existing delegation authority.
4. **Approved external research**: a configured research provider the user already authorized. Its candidates are inputs; failed or blocked sources stay visible gaps.
5. **Signals**: a completed Signals schema-v1 exchange artifact, when one exists for this need (below).

Signals being absent, stale or failing never blocks a decision: continue with routes 1-4 and say so. A grouped question keeps which capability each option addresses.

## Keep evidence honest

Preserve the need and constraints, stable candidate/source IDs, exact supported claims, observation dates and source classes. Use a focused follow-up for a material coverage or freshness gap; stop when more sources are unlikely to change the choice. Never convert popularity or a high intrinsic score into project fit. Organize options around the decision with gaps and uncertainty, then apply [prior art](../core/prior-art.md) to choose.

## Signals exchange

The supported input is the frozen `signals-evidence-v1` bundle (`schemas/evidence-bundle-v1.schema.json`), read with `scripts/evidence.py` against an exact-byte digest and pinned producer repository/commit. Optional contextual recommendation data is advisory and keeps its own version; unsupported versions fail. Do not assume a sibling checkout or service is available; a completed exchange artifact is the integration input. No candidate execution is authorized by a recommendation. Fixtures are test inputs only.
