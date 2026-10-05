# Prior art before build

Use with [engineering](../core/engineering.md), [research](../core/research.md), and [technical design](technical-design.md) when choosing a substantial dependency, service, protocol, custom subsystem, or development tool. A small edit that follows an established repository choice needs no new landscape review.

## Make the decision concrete

Name the required job, observable contract, constraints, and cost of a wrong choice. Include the status quo. Search the current repository and its decisions first; an existing implementation may already own the role. Use the [concept lookup](../scripts/lookup.rb) to find source-backed candidates for a matching decision area, then inspect native platform or language facilities, relevant standards, maintained software, composition or a narrow adapter, and an upstream change before building the residual yourself. The signal index is a starting shortlist; its gaps do not end the search. A model or agent framework is an option only if the remaining job needs its capabilities.

For each plausible option, check its actual versioned behavior, fit, license, maintenance, security and privacy boundary, compatibility, operational cost, overlap with selected tools, and removal cost. Inspect primary documentation or source for the deciding claim. A README, search rank, star count, or another project's adoption can nominate a candidate; none proves fit. Do not install a candidate merely to compare it if source inspection or a disposable trial will answer the question.

## Record a useful disposition

For a consequential choice, leave a short receipt in the project's existing ADR, reuse register, decision brief, or issue. Record:

- the need and the options actually considered, including the status quo;
- the selected owner of each responsibility and the smallest custom remainder;
- dated evidence, version or revision, what was directly verified, and what remains unknown;
- reasons to use, trial, learn from, defer, or reject each serious contender;
- the condition that would reopen the choice.

Use the project's current artifact format. Do not create a new scoring framework or receipt system for one decision. A candidate can be excellent in general and still fail this project's exact boundary. Do not convert metadata screening into a contextual assessment or treat several reports citing the same upstream source as independent confirmation.

Stop searching when credible alternatives have been checked enough that another source is unlikely to change the decision. Recheck volatile facts immediately before adoption or release. Review the prior-art choice again if a hard requirement, interface, license, maintenance state, or observed behavior changes materially.
