# Agent orchestration

Use with [development](../core/development.md), [context](../core/context.md), and [review](../core/review.md) when deciding whether work needs separate agents or specialist reviews. Session instructions, tool availability, and the user's request govern whether delegation is allowed.

## Choose the lightest shape

- **One agent:** use for small tasks, ordered chains, one shared edit surface, or work where a handoff costs more than it saves.
- **Separate investigations:** use when independent sources, hypotheses, or subsystems can be inspected concurrently and compared afterward.
- **Separate implementation:** use only with nonoverlapping files or explicit ownership and an integration point; coordinate shared state before writes.
- **Fresh review:** use a separate reader when the consequence and defect risk warrant the cost. Give it the requirement and diff; disclose shared context or authorship that limits independence.

Native task and subagent facilities come before a custom orchestrator. Do not add agents for role names, theatrical personas, artificial debate, or a workflow graph that a short sequence can express. More agents can increase tokens and conflicting work. Measure completed-task quality, elapsed time, cost, and integration effort when repeated use would justify a standing pattern.

## Give every agent a bounded task

Specify the question or deliverable, relevant files and evidence, exact authority and allowed effects, file or state ownership, expected output, checks, and stop condition. Supply only the context it needs. Keep one coordinator responsible for reconciling conflicting findings, inspecting the merged result, running integration checks, and reporting evidence classes honestly. A subagent's assertion is a lead until the coordinator traces or verifies it.

Carry current authority changes and unresolved stops in an authorized handoff. Retain standing user authorization unless superseded; an old pending marker is not a new gate. A current denial still stops the affected action until valid new approval or an authorized route resolves it. For work others depend on, report a changed start, blocked or termination state with its receipt before a long analysis when that update affects coordination. Final verification remains necessary.

Before an allocated run, check that required actions, exposed tools and exact target permissions agree, including path anchoring and the execution surface. UI controls, file reads and shell/process checks have different permissions and evidence. A denied check leaves the state unverified; it proves neither presence, absence nor cleanup. Retain partial output for the appropriate checks rather than blaming a harness mismatch on the model or silently widening access.

Do not call a review independent merely because a second agent repeated the first agent's summary. For consequential findings, use separate evidence or a fresh artifact and show which conclusions were reproduced. If all branches need the same mutable database, checkout, or service, serialize them or isolate each branch explicitly.

Use a specialist role only when its narrow responsibility changes the work: for example, database integrity, source-policy security, retrieval evaluation, accessibility, or release verification. The role is a task contract, not a new persona.
