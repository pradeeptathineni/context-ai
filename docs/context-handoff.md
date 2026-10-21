# Local Context plan and status

`scripts/context_handoff.py` lets a trusted local caller request the existing
Context engine's plan or fresh installation status. Signals can use the private
result in its local AI setup panel. Context remains the installer and lifecycle
owner. This module adds no server, dependency, tool router or browser shell.

The version 1 request has exactly these fields:

```json
{
  "schema_version": 1,
  "request_id": "lab-output-1",
  "method": "plan",
  "profile_id": "home-lab",
  "project_ref": {
    "id": "lab",
    "source_ref": "https://github.com/example/lab"
  },
  "constraints": ["Preserve project instructions"],
  "findings": [{
    "id": "output-1",
    "outcome": "Inspect retained command output",
    "evidence_refs": ["README.md"]
  }]
}
```

`method` accepts only `plan` and `status`. All fields are required; empty
constraints/findings lists are valid. Unknown fields, duplicate JSON fields,
duplicate finding IDs, local paths and control characters are rejected. Requests
are limited to 32 KiB, 16 constraints, 16 findings and 16 references per finding.
The file reader takes one bounded buffer and checks its actual length before
parsing it; a file growing after a size observation cannot bypass the limit.
Finding outcomes and constraints provide context for the caller; they never add
capabilities, dependencies, command arguments or execution permission. Structured
findings are not independently verified facts. Only approved public findings
belong in a portable request; text validation cannot detect arbitrary secrets.

The trusted caller must supply a separate registration:

```python
bindings = {"lab": {
    "path": "/approved/checkout",
    "allow_root": "/approved",
    "profile_id": "home-lab",
    "source_ref": "https://github.com/example/lab"
}}
result = handle_request(request, bindings=bindings, provider="codex")
```

The registration is local configuration, never remote request data. The request's
project ID, profile and source reference must match it. A source reference is a
public HTTPS URL without credentials/query or a named interest such as
`interest:simulation` when there is no repository. Both directories must already
exist; the project must be within the approved root. Home/root bindings,
symlinks in either path and traversal components are rejected. Engine reads stay
within the explicitly selected project and its existing instruction-routing
scope; this wrapper does not scan accounts, source environment files, execute
repository instructions or inspect credentials. Binding does not prove that the
checkout matches the public source snapshot: the public profile records its
assessment snapshot separately, and the trusted caller owns source registration.

The normal Context CLI exposes the same read-only contract:

```sh
python3 scripts/context_ai.py handoff --input REQUEST.json \
  --project APPROVED_PROJECT --allow-root APPROVED_ROOT \
  --project-id lab --profile home-lab \
  --source-ref https://github.com/example/lab --provider codex
```

Use `--public` only for the static portable selection. `--execute`, installation,
trial and selection mutation flags are rejected. Invalid inputs return a nonzero
exit: the normal CLI retains its existing code 1 convention; the standalone
adapter uses code 2. A valid blocked result returns code 2 in both routes.
Finding IDs accept stable namespaced migration IDs, including colons, up to
192 characters; they remain data and never enter commands.

Local callers may instead invoke the standalone CLI with explicit trusted
arguments:

```sh
python3 scripts/context_handoff.py --request REQUEST.json \
  --project APPROVED_PROJECT --allow-root APPROVED_ROOT \
  --project-id lab --profile home-lab \
  --source-ref https://github.com/example/lab --provider codex
```

`scope: local` results are private even when their paths are relative. A plan
returns the canonical preview under `_local.engine_plan`, the exact selected
resource hashes, library revision, catalog upstream pins, prerequisites, conflicts
and change counts. Its `plan_id` hashes the request, profile, selected option pins,
canonical plan and existing target bytes. Changing managed or unmanaged target
bytes changes that identity. Plans do not write files or call apply. Direct
upstream selections retain `native-installer-required`; their installers are
never invoked. Profiles also work when Signals is absent.

Status reads the installation afresh on every request. It returns `not-installed`
when absent, `verified` after the real engine check, or `blocked` when integrity,
routing or a required capability fails. The engine's existing verify operation
may run its reviewed required Python/Git/Node version probes. It does not run
project checks, trials, installers or a consumer task. Raw failures and runtime
locations remain under `_local`; readiness does not establish activation, use or
human usefulness. Invalid requests/bindings are rejected before engine access.

`public_result(result)` or `--public` produces `scope: portable-selection` with
static public profile/options/resource pins and a command template using
`APPROVED_PROJECT`. It omits the target-bound plan ID, observation time,
installation status, conflict counts, filenames, raw preview and private errors.
Its local state is always `unknown`. A public page cannot use this export to
inspect private state or invoke programs. Do not publish the default local
result. Export failure is explicit if trusted metadata contains a machine path.
`selection_pins` describes the static selected profile using the caller's explicit
provider, or `both` by default. It is not the local preview's `pins`: the local
engine plan preserves an existing installation's provider when none is supplied.
The portable command template includes its static provider explicitly.

After reviewing a local plan, the user may separately authorize the existing
delivery command:

```sh
python3 scripts/context_ai.py apply --profile home-lab --project APPROVED_PROJECT
python3 scripts/context_ai.py verify --project APPROVED_PROJECT
```

Apply is not a handoff action token. Neither a producer score nor a finding
outcome authorizes it. Existing [profile selections](library.md) and
[delivery lifecycle](loadouts.md) remain canonical.

## Trusted Principles v2 input

`handle_request(request, bindings=..., principles=SPEC)` accepts an optional **trusted local** Principles specification, never a new field in the remote v1 request. SPEC uses `export`, `sha256`, `revision`, `source_root`, optional `intent` (`operational` or `inspect`), and optional matching `full_export` / `full_sha256` for minimal references. The same dedicated reader and delivery lifecycle described in [loadouts](loadouts.md#explicit-native-principles-selection) validate it.

A plan exposes full selected lifecycle, applicability, exceptions and source identity under the private canonical engine preview. The ordinary handoff remains read-only; it does not apply or mint an action token. Status compares freshly supplied bound source/selection observations with the installed snapshot and reports `principles-repreview-required` when they differ. Without SPEC, status checks only installed integrity. Portable public exports omit the private Principles payload and continue to describe the static catalog selection with local state unknown. Explicit apply uses the Context CLI's current-source preview and exact plan ID, separately authorized by the user.
