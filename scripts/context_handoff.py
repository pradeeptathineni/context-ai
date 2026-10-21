#!/usr/bin/env python3
"""Local read-only Context handoff. The caller, never the request, binds paths."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

import context_ai as engine
import context_library as library

VERSION = 1
MAX_BYTES = 32768


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise engine.Invalid('unexpected or missing handoff fields')


def text(value, limit=512):
    if not isinstance(value, str) or not value or len(value) > limit:
        raise engine.Invalid('invalid handoff text')
    # Portable prose may cite HTTPS sources, but cannot carry local paths/controls.
    without_urls = re.sub(r'https://[^\s]+', '', value)
    if (any(ord(c) < 32 for c in value) or
            re.search(r'(?<![A-Za-z0-9_.-])/(?!/)|~[/\\]|[A-Za-z]:[/\\]|file:', without_urls)):
        raise engine.Invalid('local path or control character in portable request')
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}', value):
        raise engine.Invalid('invalid handoff identifier')
    return value


def source_ref(value):
    text(value, 1024)
    if re.fullmatch(r'interest:[a-z][a-z0-9-]{0,63}', value):
        return value
    url = urlsplit(value)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise engine.Invalid('source reference requires a public HTTPS URL or named interest')
    return value


def validate_request(request):
    fields(request, ('schema_version', 'request_id', 'method', 'profile_id', 'project_ref', 'constraints', 'findings'))
    if type(request['schema_version']) is not int or request['schema_version'] != VERSION:
        raise engine.Invalid('unsupported handoff schema')
    identifier(request['request_id'])
    identifier(request['profile_id'])
    if request['method'] not in ('plan', 'status'):
        raise engine.Invalid('handoff permits plan and status only')
    fields(request['project_ref'], ('id', 'source_ref'))
    identifier(request['project_ref']['id'])
    source_ref(request['project_ref']['source_ref'])
    if not isinstance(request['constraints'], list) or len(request['constraints']) > 16:
        raise engine.Invalid('invalid constraints')
    for value in request['constraints']:
        text(value)
    if not isinstance(request['findings'], list) or len(request['findings']) > 16:
        raise engine.Invalid('invalid findings')
    ids = set()
    for finding in request['findings']:
        fields(finding, ('id', 'outcome', 'evidence_refs'))
        key = text(finding['id'], 192)
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,191}', key):
            raise engine.Invalid('invalid finding identity')
        if key in ids:
            raise engine.Invalid('duplicate finding identity')
        ids.add(key)
        text(finding['outcome'])
        if not isinstance(finding['evidence_refs'], list) or len(finding['evidence_refs']) > 16:
            raise engine.Invalid('invalid evidence references')
        for ref in finding['evidence_refs']:
            text(ref, 1024)
    if len(engine.encoded(request)) > MAX_BYTES:
        raise engine.Invalid('handoff request too large')
    return request


def read_request(path):
    path = Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise engine.Invalid('symlink request path')
    with path.open('rb') as source:
        data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise engine.Invalid('handoff request too large')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise engine.Invalid('duplicate JSON field')
            result[key] = value
        return result
    return validate_request(json.loads(data, object_pairs_hook=unique))


def local_directory(value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts or not path.is_dir():
        raise engine.Invalid('binding needs an existing absolute directory')
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise engine.Invalid('symlink binding path')
    return path


def bind(request, bindings):
    """Bindings are caller configuration, never merged with remote request data."""
    key = request['project_ref']['id']
    if not isinstance(bindings, dict) or key not in bindings:
        raise engine.Invalid('project has no approved local binding')
    binding = bindings[key]
    fields(binding, ('path', 'allow_root', 'profile_id', 'source_ref'))
    if binding['profile_id'] != request['profile_id'] or binding['source_ref'] != request['project_ref']['source_ref']:
        raise engine.Invalid('request does not match approved project/profile binding')
    project, root = local_directory(binding['path']), local_directory(binding['allow_root'])
    if not project.is_relative_to(root):
        raise engine.Invalid('project outside approved root')
    # Do not permit a broad home/root binding. Approve an individual project instead.
    if project in (Path('/'), Path.home()) or root in (Path('/'), Path.home()):
        raise engine.Invalid('home/root binding is too broad')
    return project


def pins(resolution):
    return {key: resolution[key] for key in ('library_revision', 'source_tree_sha256', 'resources', 'provider', 'loadouts')}


def selected_options(picked):
    options = library.inventory()
    return [{'id': choice['option'], 'concern': choice['concern'], 'reason': choice['reason'],
             'upstream': options[choice['option']]['upstream'],
             'requirements': options[choice['option']]['requirements'],
             'permissions': options[choice['option']]['permissions'],
             'delivery_kind': options[choice['option']]['delivery']['kind']}
            for choice in picked['profile']['selections']]


def handle_request(request, *, bindings, provider=None, principles=None):
    """Return private local data; use public_result before any portable export."""
    validate_request(request)
    project = bind(request, bindings)
    if provider is not None:
        engine.hosts(provider)  # trusted local setting, absent from request contract
    try:
        picked = library.selection(request['profile_id'])
    except (engine.Invalid, OSError) as error:
        raise engine.Invalid('profile unavailable') from error
    result = {'schema_version': VERSION, 'scope': 'local', 'request_id': request['request_id'],
              'method': request['method'], 'project_ref': request['project_ref'],
              'profile_id': request['profile_id'],
              'profile_sha256': engine.digest(engine.encoded(picked['profile'])),
              'observed_at': datetime.now(timezone.utc).isoformat(),
              'options': selected_options(picked), 'applied': False,
              'selection_outcome': 'focused' if picked['loadouts'] or picked['capabilities'] else 'native-sufficient',
              'claims': {'consumer_task': 'not_run', 'trial': 'not_run', 'human_usefulness': 'unknown'},
              '_local': {'project': str(project)}}
    try:
        selection_lock, _ = engine.resolve(picked['loadouts'], project, provider or 'both', extras=picked['capabilities'])
        result['selection_pins'] = pins(selection_lock)
        if request['method'] == 'plan':
            preview = library.delivery(request['profile_id'], project, provider=provider, action='plan')
            if principles is not None:
                preview['delivery']=engine.principles_delivery(project,principles,provider=provider or 'both',
                                                               ids=picked['loadouts'],extras=picked['capabilities'])
            plan = preview['delivery']
            # Exact existing target bytes affect plan identity without exposing instructions.
            inputs = {}
            for name in sorted(set(plan['writes']) | {'.context-ai/lock.json', 'AGENTS.md'}):
                path = engine.inside(project, name)
                inputs[name] = engine.digest(path.read_bytes()) if path.is_file() else None
            identity = {'request': request, 'profile_sha256': result['profile_sha256'],
                        'options': result['options'], 'external_delivery': preview['external_delivery'],
                        'plan': plan, 'input_sha256': inputs}
            result.update(status='blocked' if plan['conflicts'] or plan['duplicate_concern_owners'] else 'planned',
                          plan_id=engine.digest(engine.encoded(identity)), pins=pins(plan['resolution']),
                          conflict_count=len(plan['conflicts']),
                          duplicate_concern_count=len(plan['duplicate_concern_owners']),
                          changes={key: len(plan[key]) for key in ('writes', 'additions', 'replacements', 'removals', 'changes')},
                          prerequisites=plan['prerequisites'], upstream_pins=plan['upstream_pins'],
                          external_delivery=preview['external_delivery'])
            result['_local'].update(engine_plan=preview, input_sha256=inputs)
        else:
            state = engine.installed(project)
            if state is None:
                result.update(status='not-installed', installation='absent')
            else:
                verification = engine.verify(project)
                result.update(status='verified', installation='present', pins=pins(state['resolution']),
                              verification={'scope': verification['scope'], 'levels': verification['levels'],
                                            'project_checks': verification['project_checks'],
                                            'required_command_probes': verification['required_command_probes']})
                result['_local']['engine_status'] = verification
                if principles is not None:
                    from context_principles import read
                    current=read(principles)
                    pinned=state['resolution'].get('principles',{})
                    if any(current[key]!=pinned.get(key) for key in ('input_sha256','artifact_sha256','intent','selected_ids')):
                        result.update(status='blocked',reason_code='principles-repreview-required')
                        result['_local']['error']='Principles source/input changed; re-preview before delivery'
    except (engine.Invalid, OSError, ValueError) as error:
        result.update(status='blocked', reason_code='engine-check-failed')
        result['_local']['error'] = str(error)
    return result


def public_result(result):
    """Static selection only. Even relative target filenames/status are private."""
    allowed = ('schema_version', 'request_id', 'method', 'project_ref', 'profile_id', 'profile_sha256',
               'options', 'selection_outcome', 'selection_pins')
    exported = {key: result[key] for key in allowed if key in result}
    exported['scope'] = 'portable-selection'
    exported['local_state'] = 'unknown'
    exported['command_template'] = ['python3', 'scripts/context_ai.py', 'plan', '--profile',
                                    result['profile_id'], '--project', 'APPROVED_PROJECT']
    if 'selection_pins' in result:
        exported['command_template'] += ['--provider', result['selection_pins']['provider']]
    # Refuse accidental machine-path leaks in trusted metadata as well.
    def portable(value):
        if isinstance(value, str):
            text(value, 16384)
        elif isinstance(value, dict):
            for key, item in value.items():
                text(key, 1024)
                portable(item)
        elif isinstance(value, list):
            for item in value:
                portable(item)
    portable(exported)
    return exported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--project', required=True, help='Trusted local project path')
    parser.add_argument('--allow-root', required=True, help='Trusted approved local scope')
    parser.add_argument('--project-id', required=True, help='Trusted project registration ID')
    parser.add_argument('--profile', required=True, help='Trusted allowed profile')
    parser.add_argument('--source-ref', required=True, help='Trusted public source URL or named interest')
    parser.add_argument('--provider', choices=tuple(engine.PROVIDERS))
    parser.add_argument('--public', action='store_true', help='Export path-free summary')
    args = parser.parse_args()
    try:
        request = read_request(args.request)
        bindings = {args.project_id: {'path': args.project, 'allow_root': args.allow_root,
                    'profile_id': args.profile, 'source_ref': args.source_ref}}
        result = handle_request(request, bindings=bindings, provider=args.provider)
        print(json.dumps(public_result(result) if args.public else result, indent=2))
        return 2 if result['status'] == 'blocked' else 0
    except (engine.Invalid, OSError, ValueError) as error:
        parser.exit(2, 'handoff rejected: ' + str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
