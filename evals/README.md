# Context evaluation

Deterministic repository validation checks structure and syntax; it cannot establish that context improves agent behavior. Behavioral evaluation should compare complete model + reasoning + context + harness combinations on representative tasks.

## Protocol

For each scenario:

1. Freeze the task, inputs, tools, permissions, harness, model snapshot when available, reasoning level, and stopping rule.
2. Run a no-context baseline, the relevant individual context, and useful context combinations.
3. Use multiple trials when model variance could change the conclusion.
4. Grade the final outcome with deterministic checks where possible and a written rubric where judgment is required.
5. Record success, failure category, latency, tokens, estimated cost, configuration, and run date.
6. Inspect representative transcripts to catch grader errors, shortcuts, and valid outcomes rejected by brittle checks.

Do not treat a single run or aggregate score as proof. Report distributions and practical effect sizes when sample size warrants them. Keep paid or nondeterministic calls out of required CI.

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

Compare engineering plus context with those files plus `custom/technical-design.md` and `custom/ai-implementation.md`.

### Context compression

Task: compress a long handoff containing requirements, decisions, exceptions, failed attempts, unresolved work, and continuation identifiers.

Rubric:

- every required item maps to the compressed result
- superseded state and raw output are removed
- uncertainty is not converted into fact
- token count is materially lower
- a follow-on agent makes the same consequential decisions from source and compressed forms

Compare no context with `core/compression.md`, then with compression plus `custom/context-efficiency.md`.

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

Compare development, testing, review, and versioning with those files plus `custom/delivery.md`.

## Growth rule

Add scenarios from real failures and decisions. Add variants only after canonical context has a measurable weakness that a small delta can address. Introduce automation when repeated manual runs justify the harness and its maintenance cost.
