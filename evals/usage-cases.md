# Context selection cases

The table contains routing and judgment probes, not measured model outcomes. A dry run checks whether a reader can select the right files and reach the stated decision. A small fresh-session proxy follows; broader behavioral evaluation must use comparable sessions as described in [README](README.md).

| Task | Files to load beyond project instructions | Decision the context should change |
| --- | --- | --- |
| Fix one misspelled README word | Target file; perhaps `custom/writing.md` if voice is affected | Make the exact correction. No landscape search, agent team, release plan, or broad test suite. |
| Add canonical hashing for durable receipts | `custom/prior-art.md`, `custom/patterns.md`, `core/research.md`, relevant project contract | Compare the existing implementation with RFC 8785 and maintained libraries; test published vectors; record the narrow selected owner and migration boundary. |
| Answer an unseen-domain research need with citations | `custom/ai-implementation.md`, `custom/patterns.md`, `custom/evidence-claims.md` | Allow bounded model interpretation and synthesis, while host code validates sources, candidate IDs, budgets, privacy, and replay. Do not grow a query-specific keyword grammar. |
| Document an exported Go API and internal branch | `custom/code-comments.md` and repository conventions | Write native exported docs for the caller contract; leave obvious internal code uncommented; explain a non-obvious invariant in compact local style. |
| Rewrite a personal project README | `custom/writing.md`, `custom/evidence-claims.md`, current README and verified behavior | Keep first-person voice and useful personality; lead with what works; preserve limits; remove process prose and unsupported claims. |
| Audit a retained development database | `custom/evidence-claims.md`, `core/testing.md`, repository safety instructions | Inspect transitive scripts and use named disposable targets for destructive checks; report fixture, live, and human evidence separately. |
| Investigate three independent failure hypotheses | `custom/orchestration.md`, `custom/model-deliberation.md`, current session rules | Use separate bounded investigations only if allowed and useful; assign distinct evidence, then reconcile. One shared database or edit path requires isolation or serial work. |
| Choose a reasoning level for a clear but long edit | `custom/model-deliberation.md`, current model availability | Start from task ambiguity and consequence, not length alone; use medium or lower if a strong specification and checks exist, then escalate on observed difficulty. |

## Structural dry-run review, 2026-10-05

1. **Selection:** each case has a limited context set; the typo case does not pull the whole hierarchy. This checks routing structure only.
2. **Authority:** project instructions and current host settings remain decisive. A semantic tag cannot change an active model; a referenced file must be read. This checks the proposed adoption boundary.
3. **Expected contrasts:** the hashing case favors a standard and verified library; the open-ended research case leaves semantic judgment to a bounded model; the Go comment case distinguishes formal API docs from sparse internal comments. These are policy expectations, not empirical agent results.

The YAML route check selected `gpt-6-astra/xhigh` for consequential architecture, `gpt-6-luna/low` for coding from a settled specification and mechanical work, and `gpt-6-sol/medium` for the wildcard fallback. It verified route order and supported effort without making a model call. It did not establish task success, model availability on every Codex surface, or a better outcome than another route.

## Fresh-session proxy, 2026-10-05

Two ephemeral, read-only Codex CLI sessions used GPT-5.6 Sol at low effort on copies of the same small Ruby receipt-digest fixture. Both saw a README asking for matching Ruby/Python hashes across key order and a `Digest::SHA256.hexdigest(JSON.generate(receipt))` implementation. The prompt asked for the next design decision, options, evidence, and unknowns; it prohibited edits. The house copy alone had an `AGENTS.md` pointer to `custom/prior-art.md` and `custom/patterns.md`.

The house session visibly read both pointed-to files. Both answers preferred RFC 8785 canonical JSON, rejected simple key sorting, and called for cross-language vectors and migration checks. The house answer also named the status quo and bespoke canonicalization, specified a narrow protocol owner, and cited the guidance. The baseline answer proposed centralizing digest generation as another option and suggested randomized equivalence tests. The CLI reported 7,104 tokens for the house run and 4,341 for baseline. This one proxy establishes loading and a different decision record; it does **not** establish better task success or cost effectiveness. The fixture README itself preferred a maintained standard, so both runs had a strong cue.

The same CLI, version 0.147.0, rejected GPT-6 Luna before the probe and GPT-6 Sol in a separate one-line startup check for this ChatGPT login. That is an observed access limit on this CLI, not a claim about other Codex surfaces. The static route policy therefore remains advisory until the active host confirms its binding; the successful comparison used GPT-5.6 Sol on both sides.

A future fresh-session comparison should run no-context, core-only, and relevant custom-file variants on the same task and tool set. Record actual artifacts and failures, not merely whether the agent says it used a file.
