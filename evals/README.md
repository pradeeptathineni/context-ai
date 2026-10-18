# Context evaluation

The [usage cases](usage-cases.md) check selective loading with structural examples and record one limited fresh-session proxy. The protocol below is for broader behavioral comparisons.

Deterministic repository validation checks structure and syntax; it cannot establish that context improves agent behavior. Behavioral evaluation should compare complete model + reasoning + context + harness combinations on representative tasks.

[Task profile evidence](task-profiles.md) records explicit resolution/effect checks and builder use on real Context development. It does not claim that an uncoached consumer selected those profiles or that native skill discovery occurred.

[Selective-value evidence](selective-value.md) records the current native-sufficient default, focused output/TDD comparisons, retained losses and lifecycle checks. Functional delivery, measured advantage and human value are separate outcomes.

## Protocol

For each scenario:

1. Freeze the task, inputs, tools, permissions, harness, model snapshot when available, reasoning level, and stopping rule.
2. Run a no-context baseline, the relevant individual context, and useful context combinations.
3. Use multiple trials when model variance could change the conclusion.
4. Grade the final outcome with deterministic checks where possible and a written rubric where judgment is required.
5. Record success, failure category, latency, tokens, estimated cost, configuration, and run date.
6. Inspect representative transcripts to catch grader errors, shortcuts, and valid outcomes rejected by brittle checks.

Do not treat a single run or aggregate score as proof. Report distributions and practical effect sizes when sample size warrants them. Keep paid or nondeterministic calls out of required CI.

## Explicit output constraints

Freeze the constraint and counting scope with the task: for example, whole UTF-8 Markdown including headings/code, at most 250 words versus strictly under 120. Check the actual saved deliverable, not a plan, claimed count, intermediate draft or model self-report. [The word-limit check](../scripts/check_word_limit.py) uses Python Unicode whitespace splitting; choose a different task-defined method when required.

```sh
python3 scripts/check_word_limit.py README.md --max-words 250
python3 scripts/check_word_limit.py final-answer.md --under-words 120
```

Exit 0 passes that bound, 1 fails it, and 2 means the input/arguments could not be checked. Use that exit status to gate the existing delivery step; a failed or unavailable check cannot authorize delivery as compliant. The JSON records the artifact SHA-256, bytes, count and exact comparison, without copying its text. A pass applies only to those bytes; any edit requires a fresh check. For readiness claims, tie every cited check to the artifact version it exercised: passes before the last relevant edit are historical, including syntax checks. Use exact check/version receipts when available; judging whether free prose misstates those facts still needs an explicit source review.

When the ordinary workflow supports commands, save the final draft, run the relevant checks, and repair failures within the original task/permission/budget limits before delivery. Preserve required facts, voice, citations and formats; do not auto-truncate. Recheck the repaired artifact and its semantic requirements, then deliver that exact file or final-answer text. If the check is unavailable or the repair budget expires, report the gap instead of claiming compliance. No hook, model retry loop or automatic publication is installed by this example.

A synthetic fail/pass/fail fixture establishes detection and invalidation after edits; it does not explain why generation missed a limit or demonstrate better model behavior. Word-count success alone is not task success. Keep personal styles and samples private; retain scoped trial evidence with its trial owner.

## Initial scenarios

### Complexity restraint

Task: give an agent a small feature request in a realistic repository where a local implementation is sufficient and optional frameworks or abstractions are tempting.

Rubric:

- all stated behavior and constraints are satisfied
- no unjustified dependency or speculative extension layer is added
- existing interfaces and utilities are reused when sound
- the result remains maintainable and validation is proportionate

Compare no context with `core/engineering.md`, then with engineering plus development.

### Mechanism discipline

Task: design an AI-oriented feature where an adopted standard covers interoperability, deterministic code can own exact processing, and a model adds value only for one semantic decision.

Rubric:

- relevant repository patterns, standards, and maintained tools are inspected before new machinery is proposed
- deterministic processing owns exact rules, state, permissions, and acceptance checks
- the model's semantic role, inputs, outputs, authority, budget, and failure behavior are bounded
- unnecessary dependencies, model calls, and agent orchestration are rejected
- the resulting design has a measurable advantage over a non-model or simpler-model baseline

Compare engineering plus context with those files plus `overlays/technical-design.md` and `overlays/ai-implementation.md`.

### Context compression

Task: compress a long handoff containing requirements, decisions, exceptions, failed attempts, unresolved work, and continuation identifiers.

Rubric:

- every required item maps to the compressed result
- superseded state and raw output are removed
- uncertainty is not converted into fact
- token count is materially lower
- a follow-on agent makes the same consequential decisions from source and compressed forms

Compare no context with `core/compression.md`, then with compression plus `overlays/context-efficiency.md`.

### Research grounding

Task: answer a current provider-specific implementation question containing a plausible but stale assumption.

Rubric:

- current first-party evidence is consulted when available
- source statements are distinguished from inference
- dates, versions, and product scope are recorded
- unsupported or stale claims are rejected
- research stops after the decision reaches the required confidence

Compare no context with `core/research.md`, then with research plus context.

### Development completeness

Task: implement a bounded defect fix in a repository where the first plausible patch leaves an edge-case regression.

Rubric:

- actual repository state and affected flow are inspected
- the smallest complete fix is implemented
- a meaningful check detects the original failure and important boundary
- real output is inspected when static tests are insufficient
- independent review finds and resolves the seeded regression
- affected validation is rerun and documentation matches behavior

Compare no context with `core/development.md`, then with development, testing, and review.

### Delivery closure

Task: complete an authorized repository change through review, refinement, commit, push, and a release tag when the public contract warrants one; seed a defect in the first patch and expose verifiable remote state.

Rubric:

- the agent distinguishes authorized external writes from implementation work
- review identifies and fixes the seeded defect, and affected validation is rerun
- documentation, changelog, compatibility notes, and version metadata match the result
- the final commit is cohesive, the intended branch is pushed without rewriting history, and the destination ref is verified
- an annotated immutable tag is created only for an intended release, targets the correct commit, and is verified remotely
- unavailable hosted evidence is reported as a limitation rather than inferred as success

Compare development, testing, review, and versioning with those files plus `overlays/delivery.md`.

### Prior-art decision

Task: add a substantial capability to a repository that already has a partial native mechanism, an established standard, a popular but mismatched package, and a small genuine residual.

Rubric:

- the repository's current owner and the standard are inspected before custom work
- candidate fit is checked against actual contract, license, privacy, maintenance, and removal cost
- a concise disposition names the selected roles, residual build, unknowns, and revisit trigger
- popularity does not become proof of fit and the task is completed rather than ending at research

Compare engineering and research with those files plus `overlays/prior-art.md` and `overlays/patterns.md`.

### Native workflow choice

Task: in a small Codex repository, add a repeatable cross-repository development procedure and one deterministic pre-write rule. The fixture should make a custom prompt loader and blanket hook seem plausible while providing no evidence that either is necessary.

Rubric:

- the agent checks current Codex skill discovery, `AGENTS.md` loading, rules and hook coverage, and installed capabilities relevant to the two jobs
- it chooses a skill or scoped instruction for the procedure and a command rule, narrow hook, CI gate, or filesystem boundary only when its actual coverage matches the required guard
- it confirms the active surface and permissions rather than assuming another Codex or ChatGPT surface has the same tools
- the implementation is complete, with a meaningful load or behavior check and no unsupported claim of universal enforcement

Compare the same model and host with and without `$standard`; record actual tool calls and artifact differences, not merely whether native features were named.

### Voice and comments

Task: revise a first-person project README that contains a useful humorous aside and an unverified capability claim; also document one exported Go API and one obvious internal branch.

Rubric:

- the README leads with a useful capability, preserves the author's voice, and qualifies the claim
- generic marketing, tautological process prose, and repetitive section shapes are removed
- the exported API follows Go documentation conventions and explains the caller contract
- the internal branch receives a comment only if its non-obvious meaning needs one

Compare core-only context with the relevant `overlays/writing.md`, `overlays/evidence-claims.md`, and `overlays/code-comments.md` files. Grade the rendered prose and actual code, not style-tool scores alone.

### Agent and effort choice

Task: choose a work shape for two cases: three independent failure hypotheses, then one shared database migration with ordered steps. Include a current host model list and a session rule that constrains delegation.

Rubric:

- agents are used only where the session permits and independent work earns the cost
- each delegated task has bounded evidence, authority, output, and stop condition
- shared mutable state is isolated or handled serially
- model and effort follow ambiguity, consequence, and observed difficulty, not task length alone
- the agent reports the actual active model and limitations without pretending an instruction changed it

Compare core-only context with `overlays/orchestration.md` and `overlays/model-deliberation.md` under the same host and permission settings.

## Growth rule

Add scenarios from real failures and decisions. Add variants only after canonical context has a measurable weakness that a small delta can address. Introduce automation when repeated manual runs justify the harness and its maintenance cost.
