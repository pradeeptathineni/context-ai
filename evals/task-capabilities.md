# Task capability checks

Reviewed: 2026-10-05. Starting product commit: `66ff224d42ea5175c66f80ac14cb0f4747cbcd3a`. These are diagnostic task trials, not a benchmark of universal advantage or stable-release readiness.

## Method

Four fresh native executions ran sequentially in isolated, ignored source copies, with one child active at a time and no grandchildren. Each pair had identical starting implementation files, ordinary project instructions, task, permitted tools and intended budget (8 minutes, approximately 12 tool calls). Workers could change only their scoped implementation/tests, without installs, network, commits or access to sibling results. Model and reasoning settings were inherited without overrides; the active IDs, tokens and cost were not exposed by the host, so they are not reported.

The Context arms additionally read the task procedure: diagnosis + core testing for code; browser verification + lightweight design for web. Both retained normal project/user instructions. Evaluator assertions and worker outputs remained outside worker input. The coordinator designed the tasks and knew the acceptance criteria; these are not blind independent evaluations. A separate evaluator exercised supported/unsupported protocols and note state/preservation on built output, without accepting a worker's green tests as the grade. No extra fresh executions or reruns were hidden behind evaluation labels.

Reproduce with two source copies per task, the same runtime/tools/settings, and the prompts below. Keep grader assertions outside those copies. Run the current evidence and browser regression suites against resulting artifacts; also inspect diffs, state sequences and screenshots. Raw transcripts, logs and screenshots remain private/ignored rather than becoming permanent product records.

## Tasks and observed outcomes

**Code task:** strengthen evidence-bundle admission so an incompatible producer protocol cannot become supported peer evidence. Preserve supported real-export replay, fixture-only admission, uncertainty and exact-byte checks. This was an actual compatibility defect; no fault was injected. Allowed scope: evidence reader and its tests, with schemas/fixtures/export read-only.

**Web task:** clear obsolete saved/error status and invalid indication when a review note is edited, until another submission. Preserve typed text, visual identity, filter/palette/reset behavior and zero server requests. This was a constrained improvement in the existing synthetic local web fixture; it is not a production website observation. Allowed scope: its app and browser verifier.

| Arm | Artifact and discriminating checks | Useful work / extra friction | Observed elapsed |
| --- | --- | --- | --- |
| Code baseline | Protocol guard; red/green regressions; supported replay and four incompatible protocol evaluator cases passed | 6 files read; 10 underlying tool calls. Covered three real modes and campaign checkpoints. | 48 s |
| Code + Context | Same protocol guard; red/green regressions; same evaluator cases passed | 9 files read; 9 underlying tool operations. Additionally covered both checkpoint formats. | 44 s |
| Web baseline | State fix; four viewport/two palette browser checks, axe, screenshot inspection; evaluator passed at 320/1440 in both palettes | 8 source files and 4 screenshots inspected. 12 orchestration / 27 underlying calls; a missing screenshot lookup and caret-test correction. | 2 min 03 s |
| Web + Context | Same state fix; same acceptance floor and evaluator pass; trim/retry/preservation checks | 11 guidance/source files plus results and 4 screenshots inspected. 12 execution calls plus coordination; a missing screenshot lookup and caret-test correction. | 2 min 21 s |

Both pairs are correctness ties. No meaningful false finding was observed in the completed artifacts. Broader checkpoint/validation-boundary tests are useful additional coverage, not proof of guidance-caused advantage. Extra reads and coordination are visible costs. Times are worker-observed elapsed values, with inconsistent underlying-call reporting; one sample per arm cannot establish savings or a causal latency difference.

Both web arms first encountered unsupported default Node 16, then used the already installed host Node 24.19.0. The Context arm requested clarification and received a pointer to the same read-only host runtime lookup available to baseline. That intervention and platform-specific caret corrections limit the comparison. No dependencies or global configuration changed. Native automatic skill activation was not observed: treatment reads were explicit. Axe does not certify accessibility; screenshots were agent-inspected, without assistive-technology users or human approval.

## Implementation use and transfer review

The coordinator used the option resolver/discovery on Context's real `.venv`, package-lock and local Playwright 1.58.2 setup without a global Playwright CLI. Static reports kept declaration, installation and untested launch separate; a missing-browser-path negative control produced an actual missing-executable launch failure without installation. The existing selected source pins and notices remained intact.

A stronger keyboard assertion failed on the existing unfocusable skip destination. Adding `tabindex="-1"` made destination focus and the next Tab target pass without changing the visual identity. The note fix and stronger checks were incorporated into the fixture. The current build was 11,776 bytes against a 24,000-byte budget; four viewport/two palette checks passed and mobile/desktop saved/edited screenshots were inspected. `evals/web-exercise.json` retains the earlier attributed snapshot rather than overwriting its provenance. This is procedure dogfooding and an actual product correction, not an additional matched arm or independent usefulness proof.

The fifth fresh execution reviewed actual option/discovery artifacts read-only. It found one P2 boundary defect: Python `*` admitted nested nonmembers under `packages/*`. The writer reproduced the failure and replaced whole-path matching with supported segment matching; positive, exclusion and unsupported-syntax regressions passed. Selected router inventories resolved in the fresh review. The final clean-archive test also materialized selected routers and required procedure/source notices without private inputs. No additional fresh task or rerun was needed. No live Signals interface is claimed. The current supported entry is exact-byte `scripts/evidence.py` admission of `signals-evidence-v1`; a future stable interface must identify producer protocol/version, candidate, claims/sources, applicability, uncertainties, observation/source dates and producer assessment meaning. Context owns project fit and a reviewed selection. Imported results never supply commands, permission or precedence.
