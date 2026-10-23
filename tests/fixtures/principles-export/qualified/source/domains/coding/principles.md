---
schema_version: 5
id: coding.principles
title: Coding Principles
domain: coding
type: principles
status: active
last_reviewed: '2026-09-02'
reviewed_content_sha256: 906c9069300bbc9b1bede38f27c2c6eb5285f614de59721137821854f7aeca2b
---

# Coding Principles

These principles govern the highest-order choices involved in writing and changing code; narrower files develop their application to particular concerns.

## Principles

### PRN-000010 — Make intent easy to recover

Write code so another person can recover its purpose, behavior, and constraints without reconstructing avoidable complexity. [1], [2]

#### Why

Code is repeatedly read, reviewed, tested, debugged, and changed. Simple structure, meaningful names, and explicit boundaries reduce the mental context required for those activities and make defects easier to notice. [1], [2]

#### Practices

- Prefer direct control flow, domain-meaningful names, and cohesive units over clever compression. [1], [2]
- Put non-obvious reasons and constraints where future readers will encounter the affected code. [2]

### PRN-000011 — Build evidence into every change

Make each change produce proportionate evidence that it behaves as intended and preserves relevant existing behavior. [1], [3]

#### Why

Testing can reveal defects and reduce operational risk, but it cannot prove that none remain. Combining executable checks, review, and risk-focused analysis provides different forms of evidence without overstating certainty. [1], [3]

#### Practices

- Define observable acceptance conditions before or while coding, then test normal, boundary, failure, and interaction behavior according to risk. [1], [3]
- Keep tests and other verification artifacts with the change so reviewers can judge both the implementation and its evidence. [2], [3]

### PRN-000012 — Separate independent engineering decisions

Separate decisions that can be understood, verified, and reversed independently; combine work only when separation would leave an incomplete change. [4], [5]

#### Why

Isolating one decision preserves causal information and limits the work that must be reconsidered when evidence fails. The useful unit is a complete idea, not an arbitrary line count. [4], [5]

#### Practices

- Split work into self-contained outcomes that reviewers can understand and verify without relying on unfinished future work. [4]
- For dependent outcomes, order the steps so each completed step keeps the system working and carries the context needed to understand the next. [4]

#### Applicability

A complete change may be large when its parts cannot work or be evaluated independently; splitting must not create misleading or broken intermediate states. [4]

### PRN-000013 — Correctness includes adverse conditions

Define security, failure behavior, resource limits, and other quality constraints as part of expected behavior before implementation. [1], [6]

#### Why

Nominal output is not correct when the same code bypasses controls, corrupts state after failure, or violates required operating limits. Treating those conditions as requirements lets design and verification address them before release. [1], [6]

#### Practices

- State the adverse inputs, failure modes, protected data, and operating limits that can change whether the result is acceptable. [1], [6]
- Choose construction and verification controls that exercise those constraints in proportion to their consequences. [1], [6]

## References

1. [Guide to the Software Engineering Body of Knowledge (SWEBOK Guide), Version 4.0a][1] — `SRC-000001`
2. [What to look for in a code review][2] — `SRC-000003`
3. [ISTQB Certified Tester Foundation Level Syllabus v4.0.1][3] — `SRC-000013`
4. [Small CLs][4] — `SRC-000027`
5. [gitworkflows — An overview of recommended workflows with Git][5] — `SRC-000021`
6. [NIST SP 800-218, Secure Software Development Framework Version 1.1][6] — `SRC-000014`

[1]: https://ieeecs-media.computer.org/media/education/swebok/swebok-v4.pdf
[2]: https://google.github.io/eng-practices/review/reviewer/looking-for.html
[3]: https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf
[4]: https://google.github.io/eng-practices/review/developer/small-cls.html
[5]: https://git-scm.com/docs/gitworkflows/2.35.0
[6]: https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-218.pdf
