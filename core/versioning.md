# Versioning

## Repository releases

- Use [Semantic Versioning](https://semver.org/spec/v2.0.0.html) for the published context library: `MAJOR.MINOR.PATCH`.
- During `0.y.z`, compatibility may evolve quickly; still document breaking changes and practical migrations.
- Treat documented file locations, structured schemas, stable identifiers, and promised behavior as the public contract.
- Record notable user-facing changes in `CHANGELOG.md` under an Unreleased section, then move them to a dated release entry.
- Create an immutable annotated `vX.Y.Z` Git tag for each release. Do not modify a published release; issue a new version.

## Structured contracts

- Give a machine-readable format its own integer `schema_version` when consumers need compatibility guarantees.
- Keep schema version independent from the repository release. A release can change content without changing its schema.
- Increment the schema version for incompatible structural or semantic changes. Document the affected fields and migration path.
- Prefer additive evolution. Define defaults for omitted optional fields and reject ambiguous invalid data.
- Deprecate a field or identifier before removal when consumers need transition time.

## Content history

- Do not add per-document version numbers to ordinary Markdown. Git history and repository releases already identify their revisions.
- Use review dates for volatile provider or model facts; a review date is freshness metadata, not a version.
- Keep compatibility statements, changelog entries, tags, and release documentation aligned with the actual artifact.
