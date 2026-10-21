# Prior-art decisions and design reconsideration

Compose [engineering](engineering.md) and [research](research.md). This file is the single active owner of prior-art search, reuse and build-versus-adopt choices. Source-supported interfaces establish what a component does; project policy decides whether to adopt it. A local trial establishes behavior in its stated environment.

Use PACT at a consequential responsibility choice: a new dependency, service, protocol, custom subsystem, development tool or utility that may already exist. Use HRR when reopening an existing design after an unresolved risk, a failed product outcome or materially changed evidence. An ordinary edit within a settled mechanism needs no landscape review and no receipt.

## Climb the reuse ladder first

Read the task and the code it touches, and trace the real flow, before choosing. Then stop at the first rung that holds:

1. Does the behavior need to exist? A speculative need is skipped and named in one line.
2. Does this repository already own it? Search code, tests and decision records (`rg`, existing helpers, ADRs) before writing.
3. Does the language standard library or the native platform cover it?
4. Does an already-installed dependency or configured host tool solve it?
5. Does a maintained external component fit behind a narrow interface?
6. Only then build the smallest complete remainder, informed by what the search found.

A shorter solution never removes validation at trust boundaries, data-loss handling, security, accessibility or explicitly requested behavior. Non-trivial logic keeps one discriminating check.

## Search channels you can actually use

Before relying on a channel, establish the capability the decision needs, not mere presence: a package manager on PATH is not a successful registry query, and a configured MCP server is not a returned result. Use a harmless real probe (for example one registry metadata query or one documentation lookup) when the search depends on it. Report a channel you could not use instead of reporting "nothing found".

| Channel | Use | If unavailable |
| --- | --- | --- |
| Repository | `rg`, tests, existing decisions | Say only visible files were inspected |
| Installed tools and dependencies | Project manifests, lockfiles, host tool list | Name the gap |
| Registries and skill hubs | npm, PyPI, crates, the host's skill/plugin catalog | Use official documentation and say registry coverage is missing |
| Upstream source | The candidate's repository and docs at an exact version | Do not adopt from a README alone |
| Current documentation | [current docs](../procedures/current-docs.md) | Official versioned docs |

## Decide and record

1. State the needed outcome, current owner and invariants, including the status quo.
2. Read the actual candidate at an exact version: entrypoints, license, install scripts, hooks and outbound behavior. Compare fit, authority, maintenance, privacy, compatibility, cost and removal against the current mechanism and a smaller native or removal alternative. Popularity nominates; it does not settle fit.
3. Choose adopt, wrap, adapt, build narrowly, remove or defer with a concrete trigger. Several weak matches may be composed; one exact match is adopted rather than rewrapped.
4. Use the choice on actual work with a discriminating check. Preserve requirements, user edits and notices.
5. Obtain a bounded fresh challenge when consequence warrants it. Keep source authority, self-review, independent agent review and human use separate.
6. Record in the project's existing ADR, decision file or issue: the need, options actually considered, selected owner, exact version, evidence verified and still unknown, and the condition that reopens the choice. Do not invent a scoring framework for one decision.

For source reuse, name the user-facing feature, owning project and complete consumer workflow. Copy or adapt a coherent slice of code and tests when its license permits and it gives useful control; use a package or service when its maintenance value justifies it. Verify the selected revision and rights, retain required notices and record local changes. A contender list or architectural resemblance is not implemented reuse. Across cooperating projects, shared interfaces consume behavior from its owner. Add missing producer capabilities there rather than duplicating them in a client.

Offering an option does not enable it. Keep plans, installation, use, independent checks and demonstrated benefit distinct; an earlier stage does not prove a later one. Stop searching when another source is unlikely to change the decision. Recheck volatile facts immediately before adoption. An honest unresolved gap needs a next action, not a confident recommendation.

Use native skills and review controls when available. Do not create an agent runtime, mandatory receipt per small edit, unrestricted interview or peer-readiness loop.

Adapted from ECC [search-first](../sourced/ecc/search-first/instruction.md) (search channels, adopt/extend/build) and Ponytail's [reuse ladder](../sourced/ponytail/reuse/instruction.md), both MIT and pinned in `sources.lock.json`. Context replaces presence-only preflight with capability probes and keeps the ladder as a reflex inside this workflow rather than an always-on persona.
