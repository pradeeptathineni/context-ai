# Hypothesis for preservation testing

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
