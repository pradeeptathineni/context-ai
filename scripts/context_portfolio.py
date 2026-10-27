#!/usr/bin/env python3
"""Preview and explicitly deliver Context loadout changes to named projects.

This coordinator stores immutable portfolio revisions and append-only operation
receipts. It delegates every project mutation to context_ai's native lifecycle.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

import context_ai as ai

MAX_BEFORE_IMAGE_BYTES = 8_000_000


class Invalid(ai.Invalid):
    pass


def _json(value):
    return ai.encoded(value)


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _private(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise Invalid('portfolio store must be an absolute private directory')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_mode & 0o077:
        raise Invalid('portfolio store must deny group and other access')
    return path


def _atomic(path, data):
    ai.atomic(path, data, 0o600)


def _safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}', value):
        raise Invalid('invalid portfolio identity')
    return value


def _project_map(projects):
    if not isinstance(projects, dict) or not 1 <= len(projects) <= 8:
        raise Invalid('configure between one and eight named projects')
    result = {}
    for key, entry in projects.items():
        _safe_id(key)
        if not isinstance(entry, dict) or set(entry) - {'label', 'path'}:
            raise Invalid('project configuration requires only label and path')
        label, path = entry.get('label'), Path(entry.get('path', ''))
        if not isinstance(label, str) or not label.strip() or not path.is_absolute() or path.is_symlink() or not path.is_dir():
            raise Invalid('each configured project needs a label and existing absolute directory')
        result[key] = {'label': label.strip(), 'path': path.resolve()}
    return result


def _read(store, name):
    path = store / name
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None
    except (ValueError, OSError):
        raise Invalid('portfolio record is malformed: ' + name) from None
    if not isinstance(value, dict):
        raise Invalid('portfolio record is malformed: ' + name)
    return value


def _save(store, name, value):
    _atomic(store / name, _json(value))


def _revision_digest(spec):
    return _hash(_json(spec))


def create(store, projects, spec):
    """Create immutable version 1 from explicit per-project selections."""
    store, projects = _private(store), _project_map(projects)
    if not isinstance(spec, dict) or set(spec) != {'projects'} or not isinstance(spec['projects'], dict):
        raise Invalid('portfolio spec must contain named project selections')
    rows = _validated_rows(projects, spec['projects'])
    source_revision = ai.source_revision()
    ident = 'portfolio-' + _hash(_json({'source_revision': source_revision, 'selection': rows}))[:24]
    if _read(store, ident + '.json'):
        return {'portfolio_id': ident, 'version': 1, 'digest': _revision_digest(rows), 'created': False}
    _save(store, ident + '.json', {'id': ident, 'source_revision': source_revision, 'version': 1,
                                   'digest': _revision_digest(rows), 'selection': rows,
                                   'history': [{'version': 1, 'source_revision': source_revision,
                                                'digest': _revision_digest(rows), 'selection': rows}]})
    return {'portfolio_id': ident, 'version': 1, 'digest': _revision_digest(rows), 'created': True}


def read_portfolio(store, portfolio_id):
    record = _read(_private(store), _safe_id(portfolio_id) + '.json')
    if not record:
        raise Invalid('unknown portfolio')
    return record


def catalog():
    return {'source_revision': ai.source_revision(),
            'loadouts': [{'id': key, 'description': value['description']}
                         for key, value in sorted(ai.catalogue().items())]}


def _validated_rows(projects, rows):
    if not isinstance(rows, dict) or not rows or set(rows) - set(projects):
        raise Invalid('selection must name configured projects')
    result = {}
    for project_id, row in sorted(rows.items()):
        if not isinstance(row, dict) or set(row) - {'loadouts', 'provider', 'options', 'extras'}:
            raise Invalid('selection row contains unsupported fields')
        loadouts = row.get('loadouts')
        provider = row.get('provider', 'codex')
        options = row.get('options', {})
        extras = row.get('extras', [])
        if not isinstance(loadouts, list) or not loadouts or not all(isinstance(x, str) for x in loadouts):
            raise Invalid('each named project requires explicit loadouts')
        if provider not in ai.PROVIDERS or not isinstance(options, dict) or not isinstance(extras, list):
            raise Invalid('invalid provider, options, or capabilities')
        # Resolve now to validate against the canonical accepted source.
        lock, _ = ai.resolve(loadouts, projects[project_id]['path'], provider, options=options, extras=extras)
        result[project_id] = {'loadouts': lock['loadouts'], 'provider': provider,
                              'options': lock['options'], 'extras': lock.get('extra_capabilities', [])}
    return result


def revise(store, projects, portfolio_id, expected_version, expected_digest, spec):
    store, projects = _private(store), _project_map(projects)
    ident = _safe_id(portfolio_id)
    record = _read(store, ident + '.json')
    if not record:
        raise Invalid('unknown portfolio')
    if record.get('digest') != _revision_digest(record.get('selection')):
        raise Invalid('portfolio revision digest is invalid')
    if record['version'] != expected_version or record['digest'] != expected_digest:
        raise Invalid('stale portfolio basis; reload the latest revision')
    rows = _validated_rows(projects, spec.get('projects') if isinstance(spec, dict) and set(spec) == {'projects'} else None)
    version = record['version'] + 1
    digest = _revision_digest(rows)
    source_revision = ai.source_revision()
    record['version'], record['digest'], record['selection'] = version, digest, rows
    record['source_revision'] = source_revision
    record['history'].append({'version': version, 'source_revision': source_revision,
                              'digest': digest, 'selection': rows})
    _save(store, ident + '.json', record)
    return {'portfolio_id': ident, 'version': version, 'digest': digest}


def _installed_state(project):
    return ai.installed(project)


def _before_image(project, state):
    if not state:
        return None
    data = {}
    size = 0
    for name in state['resolution']['resources']:
        path = ai.inside(project, '.context-ai/resources/' + name)
        if not path.is_file():
            raise Invalid('previous project selection is incomplete; resolve native drift before preview')
        content = path.read_bytes()
        if _hash(content) != state['resolution']['resources'][name]:
            raise Invalid('previous project selection has resource drift; resolve native drift before preview')
        size += len(content)
        if size > MAX_BEFORE_IMAGE_BYTES:
            raise Invalid('previous selection exceeds the bounded rollback receipt size')
        data[name] = base64.b64encode(content).decode('ascii')
    return {'resolution': state['resolution'], 'files': data}


def preview(store, projects, portfolio_id, version, digest, project_ids):
    store, projects = _private(store), _project_map(projects)
    record = _read(store, _safe_id(portfolio_id) + '.json')
    if not record or record['version'] != version or record['digest'] != digest:
        raise Invalid('stale portfolio basis; reload before preview')
    if record['digest'] != _revision_digest(record.get('selection')):
        raise Invalid('portfolio revision digest is invalid')
    source_revision = ai.source_revision()
    if source_revision != record.get('source_revision'):
        raise Invalid('canonical Context source changed since this revision; create a successor before preview')
    if not isinstance(project_ids, list) or not project_ids or len(set(project_ids)) != len(project_ids) or set(project_ids) - set(record['selection']):
        raise Invalid('preview requires an explicit unique subset of selected project IDs')
    items = {}
    for project_id in project_ids:
        project = projects[project_id]['path']
        selected = record['selection'][project_id]
        lock, files = ai.resolve(selected['loadouts'], project, selected['provider'],
                                 options=selected['options'], extras=selected['extras'])
        report = ai.plan(project, lock, files)
        report['plan_id'] = ai.delivery_plan_id(project, lock, files)
        previous = _installed_state(project)
        old = previous['resolution'] if previous else {}
        report['project_id'] = project_id
        report['project_label'] = projects[project_id]['label']
        report['old_scope'] = {'loadouts': old.get('loadouts', []), 'stages': old.get('stages', {}), 'capabilities': sorted(old.get('capabilities', {}))}
        report['new_scope'] = {'loadouts': lock['loadouts'], 'stages': lock['stages'], 'capabilities': sorted(lock['capabilities'])}
        report['prerequisite_blocked'] = [key for key, value in report['prerequisites'].items() if not value['available'] and value['requirement'] == 'required']
        report['selection'] = selected
        report['before_image'] = _before_image(project, previous)
        items[project_id] = report
    preview_id = 'preview-' + _hash(_json({'id': portfolio_id, 'version': version, 'digest': digest, 'items': items}))[:24]
    value = {'preview_id': preview_id, 'portfolio_id': portfolio_id, 'version': version, 'digest': digest,
             'source_revision': source_revision, 'created_at': int(time.time()), 'items': items}
    _save(store, preview_id + '.json', value)
    return {**value, 'items': {key: {k: v for k, v in item.items() if k != 'before_image'} for key, item in items.items()}}


def _current_matches(project, receipt):
    installed = _installed_state(project)
    lock_path = ai.inside(project, '.context-ai/lock.json')
    if not installed or not lock_path.is_file() or _hash(lock_path.read_bytes()) != receipt.get('after_lock_sha256'):
        return False
    for name, expected in receipt.get('after_owned', {}).items():
        path = ai.inside(project, name)
        if not path.is_file() or _hash(path.read_bytes()) != expected:
            return False
    return True


def apply(store, projects, preview_id, project_ids):
    store, projects = _private(store), _project_map(projects)
    preview_record = _read(store, _safe_id(preview_id) + '.json')
    if not preview_record:
        raise Invalid('unknown preview')
    if not isinstance(project_ids, list) or not project_ids or len(set(project_ids)) != len(project_ids) or set(project_ids) - set(preview_record['items']):
        raise Invalid('apply requires an explicit unique subset of this preview')
    op_id = 'operation-' + _hash(_json({'preview': preview_id, 'projects': sorted(project_ids)}))[:24]
    prior = _read(store, op_id + '.json')
    if prior:
        return {'operation_id': op_id, 'replayed': True, 'projects': _public_outcomes(prior['projects'])}
    operation = {'operation_id': op_id, 'preview_id': preview_id, 'created_at': int(time.time()), 'projects': {}}
    for project_id in project_ids:
        item = preview_record['items'][project_id]
        project = projects[project_id]['path']
        receipt = {'status': 'pending', 'plan_id': item['plan_id'], 'before_image': item['before_image'],
                   'selection': item['selection'], 'project_label': projects[project_id]['label']}
        operation['projects'][project_id] = receipt
        _save(store, op_id + '.json', operation)
        if item['conflicts'] or item['prerequisite_blocked']:
            receipt['status'] = 'blocked'
            receipt['detail'] = 'preview has conflicts or unavailable required prerequisites'
            _save(store, op_id + '.json', operation)
            continue
        try:
            if ai.source_revision() != preview_record['source_revision']:
                raise Invalid('canonical Context source changed after preview; create a new preview')
            lock, files = ai.resolve(item['selection']['loadouts'], project, item['selection']['provider'],
                                     options=item['selection']['options'], extras=item['selection']['extras'])
            result = ai.apply(project, lock, files, expected_plan=item['plan_id'])
            current = ai.installed(project)
            lock_path = ai.inside(project, '.context-ai/lock.json')
            receipt.update({'status': 'applied', 'result': result, 'after_lock_sha256': _hash(lock_path.read_bytes()),
                            'after_owned': current['owned']})
        except Exception as error:
            receipt.update({'status': 'unknown', 'detail': str(error)[:400]})
        _save(store, op_id + '.json', operation)
    return {'operation_id': op_id, 'replayed': False, 'projects': _public_outcomes(operation['projects'])}


def _public_outcomes(projects):
    private = {'before_image', 'selection', 'after_owned', 'rollback_state'}
    return {key: {name: value for name, value in receipt.items() if name not in private}
            for key, receipt in projects.items()}


def status(store, projects, operation_id):
    store, projects = _private(store), _project_map(projects)
    operation = _read(store, _safe_id(operation_id) + '.json')
    if not operation:
        raise Invalid('unknown operation')
    result = {}
    for project_id, receipt in operation['projects'].items():
        if project_id not in projects:
            result[project_id] = {'status': 'unknown', 'detail': 'project is no longer configured'}
        elif receipt['status'] == 'pending':
            result[project_id] = {'status': 'unknown', 'detail': 'operation has an incomplete pending receipt; inspect native project state'}
        elif receipt.get('rollback_state') is not None:
            project = projects[project_id]['path']
            state = receipt['rollback_state']
            try:
                if not state['installed']:
                    matches = _installed_state(project) is None
                else:
                    installed = _installed_state(project)
                    lock_path = ai.inside(project, '.context-ai/lock.json')
                    matches = bool(installed and lock_path.is_file() and
                                   _hash(lock_path.read_bytes()) == state['lock_sha256'] and
                                   installed['owned'] == state['owned'])
                result[project_id] = {'status': 'rolled_back' if matches else 'drifted_after_rollback',
                                      'label': projects[project_id]['label']}
            except Exception as error:
                result[project_id] = {'status': 'unknown', 'detail': str(error)[:300]}
        elif receipt.get('rollback_outcome') in ('partial', 'partial_or_unknown'):
            result[project_id] = {'status': 'partial_or_unknown', 'detail': 'rollback has a retained partial outcome; inspect native project state'}
        elif receipt['status'] == 'applied':
            try:
                current = _current_matches(projects[project_id]['path'], receipt)
                result[project_id] = {'status': 'current' if current else 'drifted',
                                      'label': projects[project_id]['label']}
            except Exception as error:
                result[project_id] = {'status': 'unknown', 'detail': str(error)[:300]}
        else:
            result[project_id] = {'status': receipt['status'], 'detail': receipt.get('detail')}
    return {'operation_id': operation_id, 'preview_id': operation['preview_id'], 'projects': result}


def rollback(store, projects, operation_id, project_ids):
    store, projects = _private(store), _project_map(projects)
    operation = _read(store, _safe_id(operation_id) + '.json')
    if not operation:
        raise Invalid('unknown operation')
    if not isinstance(project_ids, list) or not project_ids or len(set(project_ids)) != len(project_ids) or set(project_ids) - set(operation['projects']):
        raise Invalid('rollback requires an explicit unique subset of operation projects')
    results = {}
    for project_id in project_ids:
        receipt = operation['projects'][project_id]
        project = projects[project_id]['path']
        if receipt['status'] != 'applied' or not _current_matches(project, receipt):
            results[project_id] = {'status': 'refused', 'detail': 'project drifted or operation was not confirmed; inspect before rollback'}
            continue
        before = receipt['before_image']
        try:
            if before is None:
                undone = ai.undo(project)
                results[project_id] = {'status': 'rolled_back' if undone.get('undone') else 'partial', 'result': undone}
            else:
                previous_lock = before['resolution']
                files = {name: base64.b64decode(value, validate=True) for name, value in before['files'].items()}
                undone = ai.apply(project, previous_lock, files, expected_plan=ai.delivery_plan_id(project, previous_lock, files))
                results[project_id] = {'status': 'rolled_back', 'result': undone}
            if results[project_id]['status'] == 'rolled_back':
                restored = _installed_state(project)
                if restored:
                    restored_lock = ai.inside(project, '.context-ai/lock.json')
                    receipt['rollback_state'] = {'installed': True, 'lock_sha256': _hash(restored_lock.read_bytes()),
                                                 'owned': restored['owned']}
                else:
                    receipt['rollback_state'] = {'installed': False}
            else:
                receipt['rollback_outcome'] = results[project_id]['status']
        except Exception as error:
            results[project_id] = {'status': 'partial_or_unknown', 'detail': str(error)[:400]}
            receipt['rollback_outcome'] = 'partial_or_unknown'
    operation.setdefault('rollback', []).append({'at': int(time.time()), 'projects': results})
    _save(store, operation_id + '.json', operation)
    return {'operation_id': operation_id, 'projects': results}


def main():
    """JSON-in/JSON-out bridge; trusted config arrives only from the owner adapter."""
    envelope = json.load(sys.stdin)
    if not isinstance(envelope, dict) or set(envelope) != {'store', 'projects', 'request'}:
        raise Invalid('invalid owner request envelope')
    store = Path(envelope['store'])
    projects = envelope['projects']
    request = envelope['request']
    if not isinstance(request, dict):
        raise Invalid('request must be an object')
    action = request.get('action')
    common = (store, projects)
    if action == 'create':
        result = create(*common, request.get('spec'))
    elif action == 'catalog' and len(request) == 1:
        result = catalog()
    elif action == 'read' and set(request) == {'action', 'portfolio_id'}:
        result = read_portfolio(store, request.get('portfolio_id'))
    elif action == 'revise':
        result = revise(*common, request.get('portfolio_id'), request.get('expected_version'), request.get('expected_digest'), request.get('spec'))
    elif action == 'preview':
        result = preview(*common, request.get('portfolio_id'), request.get('version'), request.get('digest'), request.get('project_ids'))
    elif action == 'apply':
        result = apply(*common, request.get('preview_id'), request.get('project_ids'))
    elif action == 'status' and set(request) == {'action', 'operation_id'}:
        result = status(*common, request.get('operation_id'))
    elif action == 'rollback':
        result = rollback(*common, request.get('operation_id'), request.get('project_ids'))
    else:
        raise Invalid('unsupported action or request fields')
    sys.stdout.buffer.write(_json(result))


if __name__ == '__main__':
    try:
        main()
    except (Invalid, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
