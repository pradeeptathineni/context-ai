# Benchmarking

Benchmark only when the result will inform a choice. State that decision before designing the comparison.

## Design

- Define an explicit baseline and the alternatives being tested.
- Use representative workloads, including important boundaries and failure cases.
- Hold prompts, tools, data, permissions, environment, and stopping rules constant when fairness requires it.
- Record model, provider, version or snapshot, reasoning level, context set, harness, hardware where relevant, and run date.
- Make inputs, scoring, and procedures reproducible without exposing protected data.

## Measure

- Choose quality metrics tied to observable task success: correctness, requirement retention, valid outputs, defect detection, or calibrated human judgment.
- Include latency, token use, monetary cost, compute, or other resource metrics when they affect the decision.
- Use repeated samples and report distributions or uncertainty when run-to-run variation matters.
- Predefine scoring and exclusions. Do not cherry-pick scenarios, outputs, or stopping points.
- Separate model failures from harness, tool, evaluator, and infrastructure failures.

## Interpret

- Compare effect size and practical consequence, not only averages or a single best run.
- Distinguish statistically supported results from anecdotes and exploratory observations.
- Inspect surprising outcomes and representative failures; aggregate scores can hide unacceptable behavior.
- State limitations, missing populations, and conditions under which the result may not generalize.

For context evaluation, compare no context, individual files, and useful combinations before adding variants. The unit of evidence is the full model + reasoning + context + harness combination.
