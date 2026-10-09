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

After reviewing a local plan, the user may separately authorize the existing
delivery command:

```sh
python3 scripts/context_ai.py apply --profile home-lab --project APPROVED_PROJECT
python3 scripts/context_ai.py verify --project APPROVED_PROJECT
```

Apply is not a handoff action token. Neither a producer score nor a finding
outcome authorizes it. Existing [profile selections](library.md) and
[delivery lifecycle](loadouts.md) remain canonical.
