# Hypothesis for preservation testing

Consumer adaptations need their own reviewed closed recipe and runtime declaration; `hypothesis-undo` authorizes only Context preservation work. Generated operation data must never become executable commands. A consumer may inspect and copy an already approved Node/Git runtime into its destination, preserving hashes and denial probes. On macOS `/usr/bin/git` can be a developer-tool launcher; declare the actual bounded runtime instead of widening reads to a developer-tool tree. Set `GIT_CONFIG_NOSYSTEM=1` and `GIT_CONFIG_GLOBAL=/dev/null` when ambient Git configuration is outside the trial. Failed real version probes remain failures.

The native backend permits literal metadata on runtime and destination ancestors for path resolution. Ancestor contents and writes remain denied; every recipe still requires outside-read/write, personal-HOME and network denial probes. Signals supplied the reproducible Node/Python startup finding and a narrow proposed fix; Context rechecked the current backend and integrated that metadata-only change.

Signals' `project-equipment-evidence-v1.json` supplied a specific need: generate Context delivery/edit/undo sequences and check that unmanaged instructions and edited managed files survive. The executable candidate is [Hypothesis 6.168.5](https://pypi.org/project/hypothesis/6.168.5/), MPL-2.0, with [sortedcontainers 2.4.0](https://pypi.org/project/sortedcontainers/2.4.0/), Apache-2.0. It supplements the existing deterministic unittest/RNG baseline. It is not a normal Context runtime dependency or an automatically adopted recommendation.

## Use

Acquisition and execution are separate opt-in commands. Preparation accepts only the reviewed wheel set and never imports or installs its code:

```sh
python3 scripts/context_trial_wheels.py --cache /absolute/owned/trial-wheels
python3 scripts/context_trials.py hypothesis-undo --destination /absolute/new/consumer --cache /absolute/owned/trial-wheels
python3 scripts/context_trials.py hypothesis-undo --destination /absolute/new/consumer --cache /absolute/owned/trial-wheels --execute
```

The second command is a read-only plan. Missing or changed wheels block execution; there is no automatic download. Existing consumer data is refused. Each explicit acquisition attempt retains its own requirements and raw log, so retrying does not discard an earlier failure. A verified cache is reused without another download. Stop an owned running CLI process with Ctrl-C; native trials also have CPU and wall-clock limits.

The reviewed wheel set currently supports macOS CPython 3.12 x86_64. Other hosts remain untested and trial-blocked until a corresponding artifact set and isolation boundary have been reviewed. The generic-platform wheel acquisition route for 6.168.5 failed with no matching distribution; the reviewed platform wheel was then acquired. This is a portability limitation, not a reason to hide the candidate.

## Boundary and provenance

`scripts/context_trial_wheels.py` is the exact artifact authority: nine official PyPI filenames, URLs, versions and SHA-256 hashes. Seven are already required by Context and retain its `requirements.txt` pins. Hypothesis's wheel SHA-256 is `ddee1ef4bab47e315b705e42d2f4354e789973d11f9620d2df242aef4cfa42b2`; sortedcontainers' is `a163dcaede0f1c021485e957a39245190e74249897e2ae4b2aa38595db237ee0`. Metadata, licenses, dependencies, archive paths, startup hooks, entrypoint metadata and native extensions were inspected without importing candidate code. Licenses are retained when wheels are expanded. Native binary contents are pinned, not independently audited.

No source distribution, build hook, wheel installer, `.pth` file, CLI entrypoint or pytest plugin is executed. Hypothesis has optional import-time plugin loading; `HYPOTHESIS_NO_PLUGINS=1` disables it. Its optional GitHub artifact database has outbound code; this recipe uses `database=None`, disables unrelated installed packages with `-I -S`, and adds only the inspected destination-local vendor directory. These controls follow the inspected wheel entrypoints and [Hypothesis settings](https://hypothesis.readthedocs.io/en/latest/settings.html).

Before importing Hypothesis, the native `sandbox-exec` denial probe must establish that a child cannot read an outside canary, write outside the destination, enumerate personal HOME, or connect to the network. The policy permits system/runtime reads and destination-only writes. The candidate, dependencies, complete Context source/configuration snapshot, minimal HOME/TMPDIR, logs and consumer projects all live inside that destination. A missing or failed sandbox is retained as `blocked`; the recipe never falls back to unsandboxed execution.

The trial snapshots actual working-tree file bytes, not an inferred execution commit. `snapshot.json` lists every input file and hash; `source_snapshot_sha256` and a manifest hash in the planned resources invalidate reuse when the implementation changes. `trial.json` records driver/runner/runtime/wheel/resource identities, policy, environment, actual commands, elapsed time, raw output hashes, failures and result. This is first-party execution evidence, not independent review.

## Observed scope

The preserved first Hypothesis attempt exceeded the former generic 10 CPU-second budget before its baseline completed (SIGXCPU, 11.91 seconds wall); it had no passing result. The recipe now names its own 60 CPU-second / 60 wall-second bound. Both arms share one portable selection setup while exercising real plan/apply/verify, unchanged refresh, unmanaged prefix/suffix edits, managed script edits, and undo. Expected results require exact unmanaged UTF-8 bytes, retained edited managed bytes and reported conflicts, and removal of unedited delivery files.

The corrected-source run passed 24 deterministic fixed/seeded baseline cases (14.75 seconds) and 32 Hypothesis-generated cases (21.94 seconds including import), with 0.35 seconds shared selection setup. Snapshot identity was `52bc7ef19c0be5f21ad8aeb7ad93df84d09953640a08673e0a3a95c014bc4c7b`; raw case records, baseline output and the receipt were retained in `/private/tmp/context-hypothesis-undo-second`. The earlier failing attempt remains in `/private/tmp/context-hypothesis-undo-first`.

The CRLF preservation defect was reproduced and fixed before this corrected-source run; the parent's `greenfield-results/newline-before.log` and corresponding regression retain that boundary failure. It is not a new discovery credited to Hypothesis. Both current arms passed the same acceptance criteria. Their case counts and generated inputs differ, so their durations do not establish a controlled performance ratio. Keep the deterministic baseline as the ordinary route; Hypothesis is an optional adversarial generation capability. No human usefulness, productivity or general superiority claim is supported by this controlled trial.

The final repaired input snapshot `3253cb7d7bdb4734ea8c3c70d847a244286a16333df954b2fea8ea969bce51cd` passed again through `context_ai.py trial`: 24 deterministic cases in 22.00 seconds and 32 generated cases in 25.11 seconds, with 0.57 seconds shared setup. All input manifest files match committed `c323bb18c65c2781cc8a734a43a785af8a8270e4`; acquisition/extraction now use the same inspected byte buffers. Results and earlier failed attempts are copied durably into the local planning `greenfield-results` package. Concurrent local validation/research may affect elapsed times; these observations are not causal comparisons.

## Reciprocal Signals operation (2026-10-08)

Signals `6453cf6f7682922edaee96982a1d76d92b8ec474` executed Context `895c86cd68e970eb0f83adbcce3f9996f6ea3b18` through normal select/plan/apply/verify/refresh/undo and a closed consumer-owned property recipe. All 20 indexed artifacts were digest-verified and retained in Context's normal first-party assessment. Four attempts failed before candidate import; the fifth passed with approved destination-local Node/Git runtime declarations. The later immutable `02d4061` source was inspected only. Current-source execution must not be inferred from that inspection.

The final consumer passed four outside-read/write, personal-HOME and network denial probes. Actual `saveEntities`/refresh merges, withdrawn score credit, immutable observations, private notes/feedback and retained original run bytes passed 24 deterministic sequences (9.52 seconds) and 32 generated sequences (13.04 seconds). These unequal cases and concurrent setup do not support a speed comparison. A reader found the semantic correction before this property; Hypothesis did not discover it. Normal undo preserved the deliberately edited helper with `undone: false` and explicit pending ownership while retaining unmanaged instructions. This is practical first-party operation, not independent acceptance or human benefit.

The peer returned a narrow destination-ancestor metadata contribution. A real Node24 reproduction failed before the fix with `EPERM` resolving `/Users`, then passed after literal metadata permissions for destination ancestors. Contents and writes outside the destination remain denied. Commit `e12fbb1ac97e12b998c6da594ae2702c6c6b7ea8` includes that correction and an actual Node regression checking an outside-read canary. The consumer-specific Signals recipe remains owned by Signals; it is not silently installed as a trusted generic Context recipe.

Final Context boundary revalidation at `e12fbb1ac97e12b998c6da594ae2702c6c6b7ea8` passed all four denial probes, 24 deterministic preservation cases (16.78 seconds) and 32 generated cases (21.64 seconds), with 0.42 seconds shared setup. The 228-file snapshot and runner hashes match that commit. This run overlapped the full unittest process and supplies functional boundary evidence only. Earlier successful and failed attempts remain retained.
