"""Bounded, read-only delivery of an equipped Context selection to command hooks."""

import argparse
import json
import sys
from pathlib import Path

from context_ai import Invalid, digest, inside, installed
from context_guidance import GuidanceConflict, read_guidance, select

SCHEMA_VERSION = 1
MAX_CONTEXT_CHARS = 9500  # Below Claude's documented 10k hook context limit.
MAX_INPUT_BYTES = 65536
SOURCES = {'startup', 'resume', 'clear', 'compact', 'fork'}
GENERIC_FAILURE = 'Context delivery failed; inspect local installation.'


# Group exact static messages under one safe next step
def _refusals(code, step, *messages):
    return {message: (code, step) for message in messages}


# Exact static Invalid messages only. Path-bearing or unknown errors stay generic.
REFUSALS = {
    **_refusals('project_unavailable', 'Check that the project directory exists, then retry.',
                'project unavailable'),
    **_refusals('project_not_equipped',
                'Run Context plan/apply in this project, or finish or undo its pending change.',
                'project has no complete Context installation'),
    **_refusals('provider_not_installed',
                'Use an installed provider, or re-apply the selection with this one.',
                'provider outside installed selection'),
    **_refusals('installation_drift',
                'Installed Context files differ from their pins; review them and re-run apply.',
                'installed resource drift', 'stage resource drift', 'stage resource has no source pin'),
    **_refusals('routing_drift',
                'The managed route in project instructions changed; restore it or re-run apply.',
                'project routing block drift', 'Claude routing block drift'),
    **_refusals('claude_route_shadowed',
                'Review the unmanaged CLAUDE.md and re-apply Claude routing, then retry.',
                'unmanaged Claude route shadows project instructions'),
    **_refusals('stage_unavailable', 'Choose a stage from the installed selection.',
                'stage is not installed'),
    **_refusals('private_root_required', 'Pass --private-root with private resources.',
                'private source root required'),
    **_refusals('private_root_unavailable', 'Check that the private root directory exists.',
                'private source root unavailable'),
    **_refusals('guidance_unavailable',
                'Check that each selected guidance file exists and is within the size bound.',
                'selected guidance missing or oversized'),
    **_refusals('context_too_large', 'Narrow the selection or shorten its guidance.',
                'selected context exceeds hook delivery bound'),
    **_refusals('hook_input_invalid',
                'Send one SessionStart JSON payload with a supported source and cwd.',
                'unsupported hook event', 'unsupported session source',
                'missing hook project directory', 'hook payload exceeds bound',
                'hook payload is not valid JSON'),
    **_refusals('task_file_invalid', 'Pass known task files inside the equipped project.',
                'too many task files', 'task file must be a path', 'task file outside project'),
    **_refusals('guidance_manifest_invalid', 'Fix the guidance manifest, then retry.',
                'invalid task guidance manifest', 'duplicate guidance id',
                'unsafe guidance directory', 'unsupported guidance glob'),
}


def prepare(project, provider, *, private_root=None, stage=None,
            private_resources=(), optional_private_resources=(),
            max_chars=MAX_CONTEXT_CHARS, task_files=(), discover_ancestor=False):
    """Resolve this installed project and optional task guidance without writes or model calls.

    Hook callers may explicitly discover an equipped ancestor. Task paths are
    relative to the selected equipped root. Only public_receipt belongs in artifacts.
    """
    # The installation binds the caller's project spelling; resolving /var
    # aliases here would turn a valid equipped checkout into another identity.
    project = Path(project).absolute()
    if not isinstance(discover_ancestor, bool):
        raise Invalid('ancestor discovery must be explicit')
    if discover_ancestor:
        # Session hooks may start below the root; explicit project selection does not
        for candidate in (project, *project.parents):
            if (candidate / '.context-ai/lock.json').is_file():
                project = candidate
                break
    if provider not in ('codex', 'claude'):
        raise Invalid('unsupported provider')
    if not project.is_dir():
        raise Invalid('project unavailable')
    lock = installed(project)
    if not lock or lock.get('undo_pending'):
        raise Invalid('project has no complete Context installation')
    resolution = lock['resolution']
    if resolution['provider'] not in (provider, 'both'):
        raise Invalid('provider outside installed selection')
    # The route advertises the complete pinned selection. Verify every managed
    # resource before handing even the short route to a session.
    for name, sha in resolution['resources'].items():
        path = inside(project, '.context-ai/resources/' + name)
        if not path.is_file() or digest(path.read_bytes()) != sha:
            raise Invalid('installed resource drift')
    # Native skill entrypoints must match the advertised installation too
    for name, sha in lock['owned'].items():
        if name.startswith('.context-ai/resources/'):
            continue
        path = inside(project, name)
        if not path.is_file() or digest(path.read_bytes()) != sha:
            raise Invalid('installed resource drift')
    route = lock['routing_block']
    route_path = inside(project, 'AGENTS.md')
    project_text, project_sha = read_guidance(route_path, MAX_CONTEXT_CHARS)
    if project_text.count(route) != 1:
        raise Invalid('project routing block drift')
    claude_text = ''
    claude_sha = None
    if provider == 'claude' and lock.get('claude_routing'):
        entry = lock['claude_routing']
        claude_text, claude_sha = read_guidance(inside(project, entry['path']), MAX_CONTEXT_CHARS)
        if claude_text.count(entry['block']) != 1:
            raise Invalid('Claude routing block drift')
        claude_text = claude_text.replace(entry['block'], '', 1).strip()
    elif provider == 'claude' and (project / 'CLAUDE.md').exists() and not (
            (project / 'CLAUDE.md').is_symlink() and
            (project / 'CLAUDE.md').resolve() == route_path.resolve()):
        raise Invalid('unmanaged Claude route shadows project instructions')
    entries = []
    # Project-authored text can be private; keep its byte identity local only.
    selected = [{'scope': 'project', 'name': 'AGENTS.md',
                 'reason': 'checked project instructions'}]
    local_sources = [{'scope': 'project', 'name': 'AGENTS.md',
                      'sha256': project_sha}]
    if claude_sha is not None:
        local_sources.append({'scope': 'project', 'name': entry['path'], 'sha256': claude_sha})
    project_user = project_text.replace(route, '', 1).strip()
    if project_user:
        entries.append(('project instructions', project_user))
    if claude_text:
        entries.append(('Claude project instructions', claude_text))
        selected.append({'scope': 'project', 'name': 'Claude project instructions',
                         'reason': 'provider project instructions'})
    entries.append(('project route', route))
    omissions = []
    if stage is not None:
        stages = resolution['stages']
        if stage not in stages:
            raise Invalid('stage is not installed')
        for name in dict.fromkeys(stages[stage]):
            sha = resolution['resources'].get(name)
            if not sha:
                raise Invalid('stage resource has no source pin')
            path = inside(project, '.context-ai/resources/' + name)
            body, source_sha = read_guidance(path, MAX_CONTEXT_CHARS)
            if source_sha != sha:
                raise Invalid('stage resource drift')
            entries.append((name, body))
            selected.append({'scope': 'project', 'name': name,
                             'reason': 'explicit installed stage'})
            local_sources.append({'scope': 'project', 'name': name, 'sha256': sha})
    if private_resources and private_root is None:
        raise Invalid('private source root required')
    private_parts = []
    private_entries = []
    if private_root is not None:
        root = Path(private_root).resolve()
        if not root.is_dir():
            raise Invalid('private source root unavailable')
        all_private = ('README.md', *private_resources, *optional_private_resources)
        required = {'README.md', *private_resources}
        for name in dict.fromkeys(all_private):
            if all_private.count(name) > 1:
                omissions.append({'scope': 'private', 'reason': 'duplicate'})
            path = inside(root, name)
            if name not in required and not path.is_file():
                omissions.append({'scope': 'private', 'reason': 'optional missing'})
                continue
            body, source_sha = read_guidance(path, MAX_CONTEXT_CHARS)
            private_parts.append((name, body))
            local_sources.append({'scope': 'private', 'name': name,
                                  'sha256': source_sha})
            private_entries.append(('private guidance', body))
    elif optional_private_resources:
        omissions.append({'scope': 'private', 'reason': 'optional root unavailable'})
    guidance = select(project, private_root, task_files, MAX_CONTEXT_CHARS)
    local_sources.extend(guidance['sources'])
    entries.extend(guidance['entries'])
    public_guidance = [{k: item[k] for k in ('id', 'path', 'status', 'reason')}
                       for item in guidance['decisions'] if item['scope'] == 'project']
    rendered = ('Source precedence: user and host constraints and explicit decisions '
                '> checked project/task guidance > private defaults > lower inferred guidance. '
                'Declared topics prefer project rules, then narrower directories; '
                'equally ranked contradictions stop delivery.\n\n' +
                '\n\n'.join('## ' + title + '\n' + body
                            for title, body in private_entries + entries))
    if len(rendered) > min(max_chars, MAX_CONTEXT_CHARS):
        raise Invalid('selected context exceeds hook delivery bound')
    public_selection = {'selected': selected,
                        'library_revision': resolution['library_revision'],
                        'loadouts': resolution['loadouts'], 'guidance': public_guidance}
    public = {'schema_version': SCHEMA_VERSION, 'status': 'prepared_unverified',
              'selected': selected, 'omissions': omissions,
              'private_included': bool(private_parts) or any(
                  x['scope'] == 'private' and x['status'] == 'selected' for x in guidance['decisions']),
              'guidance': public_guidance,
              'source_digest': digest(json.dumps(public_selection, sort_keys=True).encode())}
    # The local identity binds exact private bytes for a trusted local consumer.
    local = digest(json.dumps({'context': rendered, 'sources': local_sources,
                              'installation': {
                                  'source_tree_sha256': resolution['source_tree_sha256'],
                                  'library_revision': resolution['library_revision'],
                                  'loadouts': resolution['loadouts'], 'owned': lock['owned']},
                              'task_files': guidance['task_files'],
                              'decisions': guidance['decisions']}, sort_keys=True).encode())
    return {'context': rendered, 'public_receipt': public,
            'local_identity': local, 'local_sources': local_sources,
            'task_guidance': {k: guidance[k] for k in ('task_files', 'decisions')}}


def hook_response(provider, payload, *, private_root=None, stage=None,
                  private_resources=(), optional_private_resources=(), task_files=()):
    if not isinstance(payload, dict) or payload.get('hook_event_name') != 'SessionStart':
        raise Invalid('unsupported hook event')
    if not isinstance(payload.get('source'), str) or payload['source'] not in SOURCES:
        raise Invalid('unsupported session source')
    cwd = payload.get('cwd')
    if not isinstance(cwd, str) or not cwd:
        raise Invalid('missing hook project directory')
    result = prepare(cwd, provider, private_root=private_root, stage=stage,
                     private_resources=private_resources,
                     optional_private_resources=optional_private_resources, task_files=task_files,
                     discover_ancestor=True)
    return {'hookSpecificOutput': {'hookEventName': 'SessionStart',
                                   'additionalContext': result['context']}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', required=True, choices=('codex', 'claude'))
    parser.add_argument('--private-root', type=Path)
    parser.add_argument('--stage')
    parser.add_argument('--private-resource', action='append', default=[])
    parser.add_argument('--optional-private-resource', action='append', default=[])
    parser.add_argument('--task-file', action='append', default=[], help='Known file relative to equipped project, or absolute within it')
    parser.add_argument('--project', type=Path, help='Prepare directly instead of reading a hook payload')
    parser.add_argument('--format', choices=('receipt', 'context', 'local'), default='receipt',
                        help='Direct output; context/local may contain private guidance')
    args = parser.parse_args(argv)
    if args.project is None and sys.stdin.isatty():
        parser.error('--project is required when stdin is a terminal; hooks send a JSON payload on stdin')
    try:
        if args.project is not None:
            result = prepare(args.project, args.provider, private_root=args.private_root,
                             stage=args.stage, private_resources=args.private_resource,
                             optional_private_resources=args.optional_private_resource,
                             task_files=args.task_file)
            if args.format == 'context':
                print(result['context'])
            else:
                print(json.dumps(result if args.format == 'local' else result['public_receipt'], ensure_ascii=False))
            return 0
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise Invalid('hook payload exceeds bound')
        try:
            payload = json.loads(raw)
        except ValueError:
            raise Invalid('hook payload is not valid JSON') from None
        output = hook_response(args.provider, payload,
                               private_root=args.private_root, stage=args.stage,
                               private_resources=args.private_resource,
                               optional_private_resources=args.optional_private_resource,
                               task_files=args.task_file)
    except Exception as error:
        # Do not put paths or private source material in provider-facing errors.
        failure = {'continue': False, 'stopReason': GENERIC_FAILURE}
        if isinstance(error, GuidanceConflict):
            failure.update(reason='guidance_conflict', stopReason=(
                'Equally ranked guidance disagrees; narrow its scope or revise topic assignments.'))
            if args.project is not None and args.format == 'local':
                failure['conflict'] = error.details
        elif type(error) is Invalid and str(error) in REFUSALS:
            failure['reason'], failure['stopReason'] = REFUSALS[str(error)]
        print(json.dumps(failure))
        return 2 if args.project is not None else 0
    # ASCII escapes parse to the same Unicode and survive any stdout encoding.
    print(json.dumps(output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
