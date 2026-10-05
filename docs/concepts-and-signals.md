# Concepts and signals

[`concepts.yaml`](../concepts.yaml) names the AI and software engineering decisions this library should recognize. Its IDs are provider neutral and its descriptions state the job, not a preferred solution. The list covers the main decision areas this repository currently needs across product, research, context, models, agents, integration, architecture, implementation, data, security, quality, delivery, operations, and communication. Extend it when a real decision does not fit; it is a maintained index, not a claim that every future concept is known.

[`signals/common.yaml`](../signals/common.yaml) links some concepts to established standards and practice that can apply across providers. [`providers/openai/signals.yaml`](../providers/openai/signals.yaml) links concepts to OpenAI product capabilities and names the applicable products. A signal is a candidate worth checking, with a use case and a boundary. Its `source_refs` resolve to original publishers and dated URLs in [`sources.yaml`](../sources.yaml). Source entries acknowledge the origin and provide the detailed reference; they do not imply that the signal is installed, enabled, or the right choice for a specific project.

## How the layers fit

| Location | Role |
| --- | --- |
| `core/*.md` | Concise, durable behavior shared across providers. It is selective, not an exhaustive encyclopedia. |
| `overlays/*.md` | The maintainer's optional house practice, also provider neutral. Old `custom/` paths are compatibility routers. |
| `concepts.yaml` | Stable names for decision areas. It carries no executable or behavioral instruction. |
| `signals/common.yaml` | Provider-neutral standards, tools, and practices worth considering for a named concept. |
| `providers/<provider>/signals.yaml` | Provider-specific candidates, each scoped to the products it applies to. |
| `providers/<provider>/<product>.md` | Actual product discovery, precedence, configuration, and consumption behavior. |
| `sources.yaml` | Original source for each signal. |

There is no provider copy of `core/` or `overlays/`. A provider-specific exception belongs in its product adapter; a provider-specific candidate belongs in its signals file. Add a provider directory when its first verified consumer needs one. Keep product availability and model bindings current at use time. [`models/routing.yaml`](../models/routing.yaml) remains the separate policy for selecting model profiles; its own sources document volatile bindings.

## Use a signal

1. Read the current task, repository contract, and the smallest relevant `core/` or `overlays/` guidance.
2. Identify the decision in `concepts.yaml`. Use `ruby scripts/lookup.rb --search WORDS` to find an ID, then `ruby scripts/lookup.rb CONCEPT_ID --provider openai --product codex` for a Codex task. The [lookup script](../scripts/lookup.rb) prints matching common and provider signals with their source links. A missing signal means there is no endorsed candidate in this index yet.
3. Open each relevant `source_refs` entry in `sources.yaml`, check the current product and environment, and assess fit against the project's requirements. Read the original source for detail rather than treating the short signal as complete documentation.
4. Make the choice using [`overlays/prior-art.md`](../overlays/prior-art.md) when consequential. Record the selected owner, evidence, unknowns, and revisit trigger in the project's existing decision artifact.

For example, `context.skills` points to the open Agent Skills specification and Codex's implementation. This makes a skill a serious option for a repeatable procedure. The actual procedure, client support, and available tools determine whether it works. `research.prior_art` points to ShouldaUsedThat and Maestro AI decisions as useful practice; their source evidence does not turn their implementation choices into universal mandates.

## Maintaining the index

- Add a concept ID for a distinct job, not for a product name or a favored tool. Use lowercase dotted IDs and a one-line definition.
- Add a signal only when a primary source or pinned project artifact directly supports what it does and its limitation can be stated plainly. Keep an unassessed possibility out of the high-confidence list.
- Put a cross-provider standard or practice in `signals/common.yaml`. Put a product capability in its provider file, with explicit `products`. Do not make empty provider files to reserve names.
- Keep source entries at original publishers or pinned project revisions; update `reviewed_on` after a real check. A source review date is not a promise of runtime availability.
- Run `ruby scripts/validate.rb` to check YAML shape, concept references, signal IDs, source references, review dates, and required repository files.

## Research needs and coverage

`concepts.yaml` schema 2 is the canonical catalog. Each row defines its job and applicable modules; shared defaults mark unassessed concepts as gaps. Claims bind the exact producer bundle and original sources. Run `.venv/bin/python scripts/concepts.py needs` for grouped questions, `coverage` for every disposition, and `definitions` for the earlier string map. Views are generated rather than maintained as parallel tables.
