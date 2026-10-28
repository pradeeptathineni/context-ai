#!/usr/bin/env python3
"""Personal choices and finite maintenance; native hosts own semantic interpretation."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
import re

import yaml
from jsonschema import ValidationError

from context_ai import ROOT, Invalid, read_yaml, parse_yaml, encoded, digest, inside, atomic, validate_schema

# Trusted local activation limit; candidate data cannot enlarge it.
TRIALS_PER_ACTIVATION = 2


def document(name):
    value = read_yaml(inside(ROOT, 'library/' + name + '.yaml'))
    validate_schema('library-' + ('profile' if name.startswith('profiles/') else name), value)
    return value


def inventory():
    data = document('catalog')
    options = {row['id']: row for row in data['options']}
    if len(options) != len(data['options']):
        raise Invalid('duplicate catalog option')
    from context_ai import catalogue, capability_registry
    loads, capabilities = catalogue(), capability_registry()['capabilities']
    for row in options.values():
        delivery = row['delivery']
        if delivery['kind'] == 'loadout' and delivery['id'] not in loads:
            raise Invalid('unknown delivered loadout')
        if delivery['kind'] == 'capability' and delivery['id'] not in capabilities:
            raise Invalid('unknown delivered capability')
    return options


def profile(id):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', id):
        raise Invalid('unsafe profile id')
    value = document('profiles/' + id)
    if value['id'] != id:
        raise Invalid('profile identity mismatch')
    return checked_profile(value)


def checked_profile(value):
    """Option, concern and overlap checks shared by catalog and caller-owned profiles."""
    options = inventory()
    concerns = set()
    for choice in value['selections']:
        if choice['option'] not in options or choice['concern'] != options[choice['option']]['concern']:
            raise Invalid('unknown option or mismatched concern')
        if choice['concern'] in concerns:
            raise Invalid('overlapping active concern owner')
        concerns.add(choice['concern'])
    for suggestion in value.get('suggestions', []):
        if suggestion['option'] not in options:
            raise Invalid('unknown suggestion option')
    # Legacy profile records remain parseable, but general opportunities have
    # one live owner and are recovered through the frozen migration export.
    value.pop('suggestions', None)
    return value


def external_profile(path):
    """One exact caller-owned schema-v1 profile file; its basename carries no identity."""
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise Invalid('--library-profile needs an existing absolute regular profile file')
    try:
        raw = path.read_bytes()
        value = parse_yaml(raw.decode('utf-8'))
        validate_schema('library-profile', value)
    except (OSError, UnicodeError, yaml.YAMLError):
        raise Invalid('library profile file is unreadable or not valid YAML') from None
    except ValidationError:
        raise Invalid('library profile file does not match the library profile schema') from None
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', value['id']):
        raise Invalid('unsafe profile id')
    return checked_profile(value), digest(raw)


def profiles():
    return {p.stem: profile(p.stem) for p in sorted((ROOT / 'library/profiles').glob('*.yaml'))}


def private_path(state):
    state = Path(state)
    if state.is_symlink():
        raise Invalid('symlink state directory')
    if not state.is_absolute():
        raise Invalid('state needs an absolute private directory')
    for p in state.parents:
        if p.is_symlink():
            raise Invalid('symlink in state path')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.stat().st_mode & 0o077:
        raise Invalid('private state directory must deny group and other access')
    return state


@contextmanager
def locked(state):
    state = private_path(state)
    path = inside(state, 'maintenance.lock')
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        raise Invalid('maintenance already locked; inspect prior process before removing stale lock')
    try:
        yield state
    finally:
        path.rmdir()


def events(state):
    if state is None:
        return []
    state = private_path(state)
    result = []
    directory = inside(state, 'events')
    if directory.exists():
        for path in sorted(directory.glob('*.json')):
            inside(state, path.relative_to(state).as_posix())
            try:
                value = json.loads(path.read_text())
            except ValueError:
                raise Invalid('malformed event file ' + path.name) from None
            if not isinstance(value, dict):
                raise Invalid('malformed event file ' + path.name)
            updates = value.get('profile_updates', [])
            if not isinstance(updates, list) or not all(
                    isinstance(u, dict) and isinstance(u.get('profile'), str) and u['profile']
                    for u in updates):
                raise Invalid('malformed profile update identity in event file ' + path.name)
            result.append(value)
    return result


def save_event(state, value):
    key = digest(encoded(value))
    directory = inside(state, 'events')
    directory.mkdir(exist_ok=True, mode=0o700)
    existing = list(directory.glob('*-' + key + '.json'))
    index = max((int(p.name.split('-', 1)[0]) for p in directory.glob('*.json')), default=0) + 1
    path = existing[0] if existing else inside(state, 'events/' + f'{index:08d}-' + key + '.json')
    if path.exists() and path.read_bytes() != encoded(value):
        raise Invalid('event identity conflict')
    atomic(path, encoded(value))
    path.chmod(0o600)
    return key


def catalog_view(state=None):
    options = inventory()
    for row in options.values():
        row['state'] = 'suggested'
    effective = {key: selection(key, state)['profile'] for key in profiles()} if state else profiles()
    for p in effective.values():
        for choice in p['selections']:
            options[choice['option']]['state'] = 'selected'
    for e in events(state):
        for assessment in e.get('assessments', []):
            if assessment['option'] in options:
                options[assessment['option']]['assessments'].append(assessment)
    return {'schema_version': 1, 'options': list(options.values()),
            'profiles': list(effective.values()), 'concepts': len(read_yaml(ROOT / 'concepts.yaml')['concepts']),
            'limits': ['Selection is not installation, invocation, or benefit. State-local evidence is private unless explicitly exported.']}


def selection(id, state=None):
    p = profile(id)
    # Effective profile choices derive from immutable policy-approved events, never peer commands.
    for e in events(state):
        for update in e.get('profile_updates', []):
            if update['profile'] == id:
                p['selections'] = update.get('selections')
    return selected(p)


def external_selection(path):
    """Selection from a caller-owned profile file; no state events apply to it."""
    p, raw = external_profile(path)
    result = selected(p)
    result['origin'] = {
        'kind': 'library-profile-file', 'path': str(Path(path)), 'sha256': raw,
        'authority': 'Selection input for this preview or explicitly authorized apply only; '
                     'declared policy and snapshot are preserved data, not permission or catalog identity.'}
    return result


def selected(p):
    opts = inventory()
    # Only the final effective choices are checked, so a superseded historical
    # choice absent from the current catalog cannot block a valid later update.
    if not isinstance(p['selections'], list):
        raise Invalid('effective profile selections must be a list')
    loads, capabilities, direct = [], [], []
    concerns = set()
    for choice in p['selections']:
        if (not isinstance(choice, dict) or set(choice) != {'option', 'reason', 'concern'}
                or not all(isinstance(v, str) and v for v in choice.values())):
            raise Invalid('effective profile has a malformed selection')
        if choice['option'] not in opts:
            raise Invalid('effective profile selects an unknown option')
        row = opts[choice['option']]
        if choice['concern'] != row['concern']:
            raise Invalid('effective profile selection has a mismatched concern')
        if row['concern'] in concerns:
            raise Invalid('effective profile has overlapping owners')
        concerns.add(row['concern'])
        delivery = row['delivery']
        if delivery['kind'] == 'loadout':
            loads.append(delivery['id'])
        elif delivery['kind'] == 'capability':
            capabilities.append(delivery['id'])
        elif delivery['kind'] == 'direct-upstream':
            direct.append(row)
    return {'profile': p, 'loadouts': loads, 'capabilities': capabilities, 'direct_upstream': direct,
            'comparison': comparison(p['selections'], opts),
            'authority': 'explicit profile; ordinary tasks load no extra guidance',
            'direct_limit': 'Direct upstream selection records fit and pin. Its installer is never executed implicitly.'}


def comparison(choices, opts):
    """Each chosen concern beside its catalog alternatives, with scoped evidence; fit stays a judgment."""
    return [{'concern': choice['concern'], 'selected': choice['option'], 'reason': choice['reason'],
             'options': [{'id': o['id'], 'name': o['name'], 'purpose': o['purpose'], 'status': o['status'],
                          'delivery': o['delivery'], 'limits': o['limits'],
                          'evidence': [{key: a[key] for key in ('scope', 'strengths', 'weaknesses', 'checked_ref')}
                                       for a in o['assessments']]}
                         for o in opts.values() if o['concern'] == choice['concern']]}
            for choice in choices]


def delivery(id, project, provider=None, action='plan', state=None):
    return deliver(lambda: selection(id, state), project, provider, action)


def external_delivery(path, project, provider=None, action='plan'):
    return deliver(lambda: external_selection(path), project, provider, action)


def deliver(pick, project, provider, action):
    from context_ai import resolve, plan, apply, installed
    if action not in ('plan', 'apply', 'refresh'):
        raise Invalid('unsupported profile delivery action')
    project = Path(project)
    if not project.is_absolute() or not project.is_dir() or project.is_symlink():
        raise Invalid('delivery needs an existing absolute consumer directory')
    project=project.resolve()
    picked = pick()
    id = picked['profile']['id']
    if picked['direct_upstream'] and action == 'apply':
        raise Invalid('direct-upstream profile requires its inspected native installer; no implicit execution')
    previous = installed(project)
    if previous and provider is None:
        provider = previous['resolution']['provider']
    provider = provider or 'both'
    lock, files = resolve(picked['loadouts'], project, provider, extras=picked['capabilities'])
    preview = plan(project, lock, files)
    result = apply(project, lock, files) if action == 'apply' else preview
    return {'profile_id': id, 'selection': picked, 'delivery': result,
            'external_delivery': [{'option': o['id'], 'upstream': o['upstream'], 'status': 'native-installer-required'} for o in picked['direct_upstream']]}


def opportunity_migration():
    """One ownership record in the existing product ledger; no peer query needed."""
    ledger = read_yaml(ROOT / 'docs/product.yaml')
    row = next(r for r in ledger['features'] if r['id'] == 'ecosystem-suggestions')
    return row.get('ownership', {'status': 'context-owned', 'destination': 'context-ai'})


def suggestions(state=None):
    migration = opportunity_migration()
    if migration['status'] != 'moved':
        raise Invalid('opportunity ownership migration is not verified')
    return {'schema_version': 1, 'status': 'moved', 'destination': migration['destination'],
            'export_reference': migration['export_reference'],
            'receipt_reference': migration['receipt_reference'],
            'migration': migration, 'suggestions': [], 'mutations': 'none',
            'authority': 'Historical export and ownership notice; AI-engineering selection stays in Context.'}


def render_suggestions():
    migration = suggestions()['migration']
    return '\n'.join([
        '# Project opportunities moved to Signals', '',
        'Signals owns general project opportunities, project interests and their feedback. '
        'Context owns AI-engineering equipment, loadout selection, trials and safe delivery.', '',
        f"The verified migration retained {migration['count']} records from Context `"
        + migration['source_revision'] + '`. Source states, evidence and provenance were preserved. '
        'The inspected peer receipt reports no added records on the second import and '
        'successful recovery in a disposable destination.', '',
        migration['identity_note'], '',
        '[Frozen export](../' + migration['export_reference'] + ') · '
        '[Conservation receipt](../' + migration['receipt_reference'] + ')', '',
        'The `suggestions` CLI remains a read-only moved response with those recovery references. '
        'It does not generate or mutate another opportunity list. '
        'Use `catalog`, `profiles` and `select PROFILE` for Context equipment.', '',
        'The previous project-suggestions assessment remains in [the product ledger](product.yaml) '
        'at its original evidence scope. Migration is not new discovery or installation authority.',
        ''])


def intake(path, sha, producer, commit, interest, fixture=False):
    from evidence import inspect_bundle
    interests = {i['id']: i for i in document('interests')['interests']}
    if interest not in interests:
        raise Invalid('unknown interest scope')
    report = inspect_bundle(Path(path), sha, producer, commit, allow_fixture=fixture)
    raw = Path(path).read_bytes()
    if digest(raw) != sha:
        raise Invalid('intake changed after validation')
    return {'schema_version': 1, 'interest': interest, 'evidence': report, '_raw_bundle': raw,
            'authority': 'advisory; no commands or profile changes authorized by intake'}


def trial_plan(state, profile_value, recipe, wheel_cache):
    from context_trials import run_trial
    planned = run_trial(recipe, inside(state, 'trial-plan'), execute=False, cache=wheel_cache)
    key = digest(encoded({'recipe_sha256': planned['recipe_sha256'],
                          'runner_sha256': planned['runner_sha256'],
                          'preparation': {k: v for k, v in planned.get('preparation', {}).items()
                                          if k not in ('cache', 'reason')},
                          'resources': planned['resources'], 'runtime': planned['runtime'],
                          'profile_snapshot': profile_value['snapshot'], 'policy': profile_value['policy']}))
    return inside(state, 'trials/' + key)


def maintenance(state, intake_report=None, today=None, execute_trials=False, wheel_cache=None):
    today = today or date.today()
    opts, ps = inventory(), profiles()
    interests = document('interests')['interests']
    with locked(state) as state:
        prior = events(state)
        control = inside(state, 'control.json')
        if control.exists() and json.loads(control.read_text()).get('paused'):
            return {'status': 'paused', 'actions': []}
        seen = {(e.get('interest'), e.get('intake_sha')) for e in prior}
        due = []
        for interest in interests:
            if interest.get('ownership', {}).get('status') == 'moved':
                continue
            latest = [e for e in prior if e.get('interest') == interest['id']]
            next_due = date.fromisoformat(latest[-1]['next_due'] if latest else interest['due'])
            if next_due <= today:
                due.append({'id': interest['id'], 'query': interest['query'], 'concepts': interest['concepts'],
                            'profiles': interest['profiles'], 'route': 'Signals when available; native research otherwise',
                            'status': 'research-requested', 'authority': 'host executes under existing tool/data permissions'})
        if intake_report is None:
            return {'status': 'no-peer-input', 'due_research': due, 'actions': [],
                    'current_selections': 'preserved', 'coverage_gap': 'No new source observation supplied.'}
        report = intake_report['evidence']
        sha = report['bundle_sha256']
        scope = next(i for i in interests if i['id'] == intake_report['interest'])
        if scope.get('ownership', {}).get('status') == 'moved':
            return {'status': 'moved', 'interest': scope['id'],
                    'destination': scope['ownership']['destination'],
                    'history_reference': scope['ownership']['history_reference'],
                    'actions': [], 'due_research': due, 'current_selections': 'preserved'}
        raw = intake_report.get('_raw_bundle')
        if raw is not None:
            if digest(raw) != sha:
                raise Invalid('intake raw digest mismatch')
            raw_path = inside(state, 'bundles/' + sha + '.json')
            if raw_path.exists() and raw_path.read_bytes() != raw:
                raise Invalid('retained bundle changed')
            atomic(raw_path, raw)
            raw_path.chmod(0o600)
        retry = False
        if execute_trials:
            for candidate in report['recommendations']:
                for option in opts.values():
                    recipe = {'context-output': 'output-helper', 'context-tdd': 'tdd-consumer', 'hypothesis': 'hypothesis-undo'}.get(option['id'])
                    if recipe and option['upstream']['url'].rstrip('/') == candidate['canonical_uri'].rstrip('/'):
                        for profile_id in scope['profiles']:
                            p = ps[profile_id]
                            if option['id'] in p['policy']['trials'] and not trial_plan(state, p, recipe, wheel_cache).exists():
                                retry = True
        if (scope['id'], sha) in seen and not retry:
            return {'status': 'unchanged', 'actions': [], 'due_research': due}
        semantic_sha = digest(encoded({'interest': scope['id'], 'claims': report['claims'],
                                     'candidates': report['recommendations'],
                                     'sources': [{k: v for k, v in source.items() if k != 'observed_at'} for source in report['sources']]}))
        if any(e.get('semantic_sha') == semantic_sha for e in prior) and not retry:
            event = {'schema_version': 1, 'interest': scope['id'], 'intake_sha': sha,
                     'evidence_report': report, 'bundle_ref': 'bundles/' + sha + '.json',
                     'producer': report['producer'], 'mode': report['mode'],
                     'semantic_sha': semantic_sha, 'date': today.isoformat(),
                     'next_due': (today + timedelta(days=scope['refresh_days'])).isoformat(),
                     'status': 'refetch-no-material-change', 'assessments': [], 'profile_updates': []}
            key = save_event(state, event)
            return {'status': 'refetch-no-material-change', 'event': key, 'actions': [], 'trials': []}
        assessments, proposals, trials = [], [], []
        attempts = 0
        for candidate in report['recommendations']:
            matched = [o for o in opts.values() if o['upstream']['url'].rstrip('/') == candidate['canonical_uri'].rstrip('/')]
            if not matched:
                proposals.append({'candidate': candidate['id'], 'action': 'inspect-new-option', 'uri': candidate['canonical_uri'],
                                  'status': 'review-required', 'reason': 'New equipment requires source/license/runtime review before catalog admission.'})
            for option in matched:
                assessment = {'option': option['id'], 'scope': scope['id'], 'checked_ref': report['producer']['commit'],
                              'evidence': [sha], 'grade': None, 'strengths': [], 'weaknesses': report['limitations'],
                              'status': 'review-required', 'basis': 'New source observation; semantic fit remains an explicit host assessment.'}
                assessments.append(assessment)
                for profile_id in scope['profiles']:
                    if profile_id not in ps:
                        raise Invalid('unknown interest profile')
                    p = ps[profile_id]
                    permitted = option['id'] in p['policy']['trials']
                    recipe = {'context-output': 'output-helper', 'context-tdd': 'tdd-consumer', 'hypothesis': 'hypothesis-undo'}.get(option['id'])
                    result = {'profile': profile_id, 'option': option['id'], 'action': 'trial',
                              'status': 'eligible' if permitted and recipe else 'blocked-policy',
                              'reason': 'Only declared trusted recipes run; producer recommendations cannot expand trial policy.'}
                    if execute_trials and permitted and recipe:
                        from context_trials import run_trial
                        destination = trial_plan(state, p, recipe, wheel_cache)
                        if destination.exists():
                            result['status'] = 'already-attempted' if (destination / 'trial.json').is_file() else 'interrupted-review-required'
                            result['trial_ref'] = destination.relative_to(state).as_posix() + '/trial.json'
                        elif attempts >= TRIALS_PER_ACTIVATION:
                            result['status'] = 'blocked-budget'
                            result['reason'] = 'Two trusted trial attempts per activation; pending work remains eligible on a later finite pass.'
                        else:
                            attempts += 1
                            try:
                                trials.append(run_trial(recipe, destination, execute=True, cache=wheel_cache))
                            except (ValueError, OSError) as error:
                                trials.append({'status': 'blocked-setup', 'reason': str(error), 'recipe': recipe})
                            result['status'] = trials[-1]['status']
                            result['trial_ref'] = destination.relative_to(state).as_posix() + '/trial.json'
                            assessment['trial_ref'] = result['trial_ref']
                            assessment['trial_status'] = result['status']
                    proposals.append(result)
        event = {'schema_version': 1, 'interest': scope['id'], 'intake_sha': sha,
                 'evidence_report': report, 'bundle_ref': 'bundles/' + sha + '.json',
                 'producer': report['producer'], 'semantic_sha': semantic_sha, 'mode': report['mode'], 'date': today.isoformat(),
                 'next_due': (today + timedelta(days=scope['refresh_days'])).isoformat(),
                 'assessments': assessments, 'proposals': proposals, 'trials': trials,
                 'profile_updates': [], 'selections': 'preserved until explicit assessment and allowed policy'}
        key = save_event(state, event)
        return {'status': 'assessed-new-input', 'event': key, 'actions': proposals, 'trials': trials, 'due_research': due}


def approve_selection(state, profile_id, option_id, evidence_sha):
    """Explicit local decision; changes future profile delivery only, never active consumer bytes."""
    p, opts = profile(profile_id), inventory()
    if option_id not in opts:
        raise Invalid('unknown option')
    if option_id not in p['policy']['updates']:
        raise Invalid('profile update blocked by standing policy')
    with locked(state) as state:
        prior = events(state)
        if not any(e.get('intake_sha') == evidence_sha and e.get('mode') not in (None, 'fixture') for e in prior):
            raise Invalid('selection requires retained non-fixture intake evidence')
        if not any(a.get('option') == option_id and evidence_sha in a.get('evidence', [])
                   and a.get('evidence_class') in ('source-inspection', 'controlled-trial', 'first-party-use')
                   for e in prior for a in e.get('assessments', [])):
            raise Invalid('selection requires a retained local scoped assessment of this option')
        selected = selection(profile_id, state)['profile']['selections']
        concern = opts[option_id]['concern']
        updated = [s for s in selected if s['concern'] != concern]
        updated.append({'option': option_id, 'concern': concern, 'reason': 'Explicit local policy-approved decision from ' + evidence_sha})
        event = {'schema_version': 1, 'profile_updates': [{'profile': profile_id, 'selections': updated}],
                 'evidence': evidence_sha, 'active_consumer_changes': False}
        key = save_event(state, event)
        return {'event': key, 'selection': updated, 'next_action': 'Preview profile delivery; installed consumers stay pinned.'}


def _review_closed(value, keys, required=None):
    required = keys if required is None else required
    if (not isinstance(value, dict) or set(value) - set(keys) or
            any(key not in value for key in required)):
        raise Invalid('equipment review has unknown or missing fields')
    return value


def _review_sha(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise Invalid(label + ' must be a lowercase SHA-256 digest')
    return value


def _effective_profile(state, profile_id):
    current = selection(profile_id, state)
    path = inside(ROOT, 'library/profiles/' + profile_id + '.yaml')
    file_sha = digest(path.read_bytes())
    identity = digest(encoded({'owner_profile_sha256': file_sha,
                               'effective_profile': current['profile']}))
    return current, identity


def _trial_review_input(value):
    _review_closed(value, ['reference', 'pair', 'equipment_binding'])
    ref = _review_closed(value['reference'],
                         ['owner', 'id', 'packetSha256', 'sandboxRevision', 'planSha256',
                          'baselineAttemptId', 'baselineAttemptSha256',
                          'candidateAttemptId', 'candidateAttemptSha256'])
    if ref['owner'] != 'sandbox-experiment-evidence':
        raise Invalid('equipment review requires the retained Sandbox evidence owner')
    if not re.fullmatch(r'[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}', str(ref['id'])):
        raise Invalid('invalid retained Sandbox evidence ID')
    for key in ('packetSha256', 'planSha256', 'baselineAttemptSha256', 'candidateAttemptSha256'):
        _review_sha(ref[key], key)
    for key in ('sandboxRevision',):
        if not isinstance(ref[key], str) or not re.fullmatch(r'[0-9a-f]{40}', ref[key]):
            raise Invalid(key + ' must be an exact owner revision')
    for key in ('baselineAttemptId', 'candidateAttemptId'):
        if not isinstance(ref[key], str) or not ref[key] or len(ref[key]) > 120:
            raise Invalid('invalid selected trial attempt identity')
    pair = _review_closed(value['pair'],
                          ['verdict', 'outcomeComparable', 'baselineStatus', 'candidateStatus',
                           'treatmentFields', 'unresolved', 'unknownCriteria',
                           'unknownMeasurements', 'resourceQualifications', 'contextIdentityMatched',
                           'criterionId', 'criterionStatement', 'criterionKind', 'criterionOwner',
                           'criterionVersion', 'criterionReference', 'criterionSha256',
                           'criterionIndependentOfSubject', 'baselineCriterionResult',
                           'candidateCriterionResult'])
    if (not isinstance(pair['verdict'], str) or len(pair['verdict']) > 80 or
            type(pair['outcomeComparable']) is not bool or
            type(pair['contextIdentityMatched']) is not bool or
            pair['baselineStatus'] not in ('completed', 'failed', 'partial', 'blocked', 'unknown') or
            pair['candidateStatus'] not in ('completed', 'failed', 'partial', 'blocked', 'unknown') or
            type(pair['criterionIndependentOfSubject']) is not bool or
            pair['baselineCriterionResult'] not in ('pass', 'fail', 'unknown') or
            pair['candidateCriterionResult'] not in ('pass', 'fail', 'unknown')):
        raise Invalid('invalid retained trial comparison status')
    if (not isinstance(pair['criterionId'], str) or
            not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', pair['criterionId']) or
            not isinstance(pair['criterionStatement'], str) or
            not pair['criterionStatement'].strip() or len(pair['criterionStatement']) > 1000 or
            not isinstance(pair['criterionKind'], str) or
            not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', pair['criterionKind']) or
            not isinstance(pair['criterionOwner'], str) or
            not pair['criterionOwner'].strip() or len(pair['criterionOwner']) > 200 or
            not isinstance(pair['criterionVersion'], str) or
            not pair['criterionVersion'].strip() or len(pair['criterionVersion']) > 100 or
            not isinstance(pair['criterionReference'], str) or
            not pair['criterionReference'].strip() or len(pair['criterionReference']) > 300):
        raise Invalid('invalid selected Sandbox criterion provenance')
    _review_sha(pair['criterionSha256'], 'criterionSha256')
    for key in ('treatmentFields', 'unresolved', 'unknownCriteria', 'unknownMeasurements',
                'resourceQualifications'):
        values = pair[key]
        if not isinstance(values, list) or len(values) > 100 or any(
                not isinstance(item, str) or not item or len(item) > 300 for item in values):
            raise Invalid('invalid bounded trial qualification list')
    binding = _review_closed(value['equipment_binding'],
                             ['contextOwnerRevision', 'profileId', 'profileDigest',
                              'baselineOptionId', 'candidateOptionId'])
    if not isinstance(binding['contextOwnerRevision'], str) or not re.fullmatch(
            r'[0-9a-f]{40}', binding['contextOwnerRevision']):
        raise Invalid('invalid Context owner revision in trial binding')
    if not isinstance(binding['profileId'], str) or not re.fullmatch(
            r'[a-z][a-z0-9-]{0,63}', binding['profileId']):
        raise Invalid('invalid Context profile in trial binding')
    _review_sha(binding['profileDigest'], 'profileDigest')
    for key in ('baselineOptionId', 'candidateOptionId'):
        if not isinstance(binding[key], str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', binding[key]):
            raise Invalid('invalid Context equipment option in trial binding')
    return {'reference': ref, 'pair': pair, 'equipment_binding': binding}


def _equipment_review_preview(state, request):
    _review_closed(request, ['schema', 'operation', 'profileId', 'candidateOptionId', 'contextOwnerRevision',
                             'criterion', 'evidence'])
    if request['schema'] != 'context-equipment-review-request.v1' or request['operation'] != 'preview':
        raise Invalid('unsupported Context equipment review request')
    profile_id, candidate_id = request['profileId'], request['candidateOptionId']
    if not isinstance(profile_id, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', profile_id):
        raise Invalid('invalid Context profile ID')
    if not isinstance(candidate_id, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', candidate_id):
        raise Invalid('invalid Context equipment option ID')
    owner_revision = request['contextOwnerRevision']
    if not isinstance(owner_revision, str) or not re.fullmatch(r'[0-9a-f]{40}', owner_revision):
        raise Invalid('invalid current Context owner revision')
    criterion = request['criterion']
    if not isinstance(criterion, str) or not criterion.strip() or len(criterion) > 2000:
        raise Invalid('provide one explicit bounded review criterion')
    evidence = _trial_review_input(request['evidence'])
    current, profile_digest = _effective_profile(state, profile_id)
    options = inventory()
    if candidate_id not in options:
        raise Invalid('candidate is not in the current Context equipment catalog')
    candidate = options[candidate_id]
    if candidate['delivery']['kind'] not in ('loadout', 'capability'):
        raise Invalid('candidate has no supported Context loadout delivery')
    concern = candidate['concern']
    current_rows = [row for row in current['profile']['selections'] if row['concern'] == concern]
    if len(current_rows) > 1:
        raise Invalid('current Context profile has conflicting equipment choices for this concern')
    current_option = current_rows[0]['option'] if current_rows else 'none'
    if candidate_id not in current['profile']['policy']['updates']:
        raise Invalid('Context profile policy does not allow this future selection')
    binding = evidence['equipment_binding']
    pair = evidence['pair']
    identity_matches = (
        binding['profileId'] == profile_id and
        binding['profileDigest'] == profile_digest and
        binding['contextOwnerRevision'] == owner_revision and
        binding['baselineOptionId'] == current_option and
        binding['candidateOptionId'] == candidate_id
    )
    evidence_sufficient = (
        pair['verdict'] == 'comparable' and pair['outcomeComparable'] is True and
        pair['baselineStatus'] == 'completed' and pair['candidateStatus'] == 'completed' and
        pair['treatmentFields'] == ['identity.equipment'] and
        pair['baselineCriterionResult'] == 'fail' and
        pair['candidateCriterionResult'] == 'pass' and
        not pair['unresolved'] and not pair['unknownCriteria'] and
        pair['contextIdentityMatched'] is True and identity_matches
    )
    proposed = deepcopy(current['profile'])
    proposed['selections'] = [row for row in proposed['selections'] if row['concern'] != concern]
    proposed['selections'].append({
        'option': candidate_id, 'concern': concern,
        'reason': 'Explicitly reviewed candidate for: ' + criterion.strip(),
    })
    target = selected(proposed)
    from context_ai import explain, capability_registry
    try:
        before_explanation = explain(current['loadouts'])
        after_explanation = explain(target['loadouts'])
        registry = capability_registry()['capabilities']
        if any(key not in registry for key in target['capabilities']):
            raise Invalid('candidate profile includes an unresolved Context capability')
        compatibility = {'status': 'owner-declared-compatible',
                         'before': before_explanation['composition'],
                         'after': after_explanation['composition'],
                         'capabilities': {key: registry[key] for key in target['capabilities']},
                         'decisions': after_explanation['decisions'],
                         'checks': after_explanation['checks'],
                         'capabilityRequirements': after_explanation['capability_requirements'],
                         'qualification': 'Context declarations only; no host runtime or installation was checked.'}
    except Invalid as error:
        compatibility = {'status': 'blocked', 'detail': str(error),
                         'before': current['loadouts'], 'after': target['loadouts'],
                         'qualification': 'Declared Context conflict; no change was made.'}
        evidence_sufficient = False
    result = {
        'schema': 'context-equipment-review-preview.v1',
        'status': 'candidate_for_human_review' if evidence_sufficient else 'insufficient_evidence',
        'canAccept': bool(evidence_sufficient and compatibility['status'] == 'owner-declared-compatible'),
        'profileId': profile_id, 'profileDigest': profile_digest,
        'contextOwnerRevision': owner_revision,
        'currentOptionId': current_option, 'candidateOptionId': candidate_id,
        'concern': concern, 'criterion': criterion.strip(),
        'evidence': evidence, 'compatibility': compatibility,
        'explanation': ('This retained pair records the candidate passing the selected Sandbox criterion '
                        'while the baseline failed; review whether that evidence fits your separate project criterion. '
                        'One pair does not establish general benefit or superiority.'
                        if evidence_sufficient else
                        'The exact criterion result, comparison, profile binding, or declared compatibility is insufficient; '
                        'review only, with no profile change.'),
        'limitations': [
            'Sandbox comparability describes recorded trial structure, not general performance or superiority.',
            'Unknown measurements remain unknown and cannot support a resource-efficiency claim.',
            'A future profile choice is not installation or activation.',
        ],
    }
    result['previewDigest'] = digest(encoded(result))
    return result


def equipment_review(state, request):
    """Review exact Context profile equipment against a reread Sandbox pair; adoption is explicit."""
    if not isinstance(request, dict) or request.get('schema') != 'context-equipment-review-request.v1':
        raise Invalid('unsupported Context equipment review request')
    operation = request.get('operation')
    if operation == 'preview':
        return _equipment_review_preview(state, request)
    if operation == 'accept':
        _review_closed(request, ['schema', 'operation', 'profileId', 'candidateOptionId', 'contextOwnerRevision', 'criterion',
                                 'evidence', 'previewDigest', 'reviewId', 'accepted', 'reason'])
        if request['accepted'] is not True:
            raise Invalid('explicit human acceptance is required')
        _review_sha(request['previewDigest'], 'previewDigest')
        review_id = request['reviewId']
        if not isinstance(review_id, str) or not re.fullmatch(
                r'[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}', review_id):
            raise Invalid('invalid equipment review identity')
        reason = request['reason']
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise Invalid('provide a bounded human acceptance reason')
        preview_request = {key: request[key] for key in
                           ('schema', 'profileId', 'candidateOptionId', 'contextOwnerRevision', 'criterion', 'evidence')}
        preview_request['operation'] = 'preview'
        with locked(state):
            preview = _equipment_review_preview(state, preview_request)
            if preview['previewDigest'] != request['previewDigest']:
                raise Invalid('equipment review preview changed; review the current profile again')
            if not preview['canAccept']:
                raise Invalid('insufficient evidence or Context compatibility blocks profile adoption')
            current = selection(request['profileId'], state)['profile']
            concern = preview['concern']
            updated = [row for row in current['selections'] if row['concern'] != concern]
            updated.append({'option': request['candidateOptionId'], 'concern': concern,
                            'reason': reason.strip()})
            retained = {
                'schema': 'context-equipment-review.v1', 'reviewId': review_id,
                'acceptedAt': date.today().isoformat(), 'profileId': request['profileId'],
                'predecessorProfileDigest': preview['profileDigest'],
                'contextOwnerRevision': preview['contextOwnerRevision'],
                'successorSelections': updated, 'candidateOptionId': request['candidateOptionId'],
                'criterion': preview['criterion'], 'humanReason': reason.strip(),
                'evidenceReference': preview['evidence']['reference'],
                'evidenceAssessment': preview['evidence']['pair'],
                'equipmentBinding': preview['evidence']['equipment_binding'],
                'evidenceQualification': preview['explanation'],
                'previewDigest': preview['previewDigest'],
                'compatibility': preview['compatibility'],
                'activeConsumerChanges': False,
                'deliveryState': 'not-installed',
            }
            event = {'schema_version': 1, 'equipment_reviews': [retained],
                     'profile_updates': [{'profile': request['profileId'], 'selections': updated}],
                     'authority': 'explicit human future-profile selection; no consumer delivery',
                     'source_binding': preview['evidence']['reference']}
            event_id = save_event(state, event)
        return {'schema': 'context-equipment-review-receipt.v1', 'status': 'accepted_for_future_profile',
                'reviewId': review_id, 'eventId': event_id, 'profileId': request['profileId'],
                'selection': updated, 'activeConsumerChanges': False, 'deliveryState': 'not-installed'}
    if operation == 'read':
        _review_closed(request, ['schema', 'operation', 'reviewId', 'profileId'])
        review_id, profile_id = request['reviewId'], request['profileId']
        if not isinstance(review_id, str) or not re.fullmatch(
                r'[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}', review_id):
            raise Invalid('invalid equipment review identity')
        current, current_digest = _effective_profile(state, profile_id)
        found = None
        for event in events(state):
            for row in event.get('equipment_reviews', []):
                if row.get('reviewId') == review_id and row.get('profileId') == profile_id:
                    found = row
        if found is None:
            raise Invalid('exact accepted equipment review was not found')
        return {'schema': 'context-equipment-review-read.v1', 'review': found,
                'profileDigest': current_digest,
                'currentness': 'current' if current_digest == found['predecessorProfileDigest'] else 'successor-created',
                'effectiveProfile': current['profile'],
                'activeConsumerChanges': False, 'deliveryState': 'not-installed'}
    raise Invalid('unsupported Context equipment review operation')


def record_assessment(state, path):
    value = read_yaml(Path(path))
    validate_schema('library-assessment', value)
    if value['option'] not in inventory():
        raise Invalid('assessment names an unknown option')
    with locked(state) as state:
        refs = []
        for reference in value['artifacts']:
            artifact = Path(reference['path'])
            if not artifact.is_absolute() or artifact.is_symlink() or not artifact.is_file():
                raise Invalid('assessment artifact needs a local absolute regular file')
            raw = artifact.read_bytes()
            if digest(raw) != reference['sha256']:
                raise Invalid('assessment artifact digest mismatch')
            name = 'artifacts/' + reference['sha256'] + '.json'
            atomic(inside(state, name), raw)
            inside(state, name).chmod(0o600)
            refs.append(name)
        assessment = {**value, 'retained_artifacts': refs}
        key = save_event(state, {'schema_version': 1, 'assessments': [assessment],
                                 'profile_updates': [], 'authority': 'explicit local assessment; no installation'})
    return {'event': key, 'assessment': assessment}


def control(state, paused):
    with locked(state) as state:
        atomic(inside(state, 'control.json'), encoded({'schema_version': 1, 'paused': paused}))
        inside(state, 'control.json').chmod(0o600)
    return {'paused': paused, 'production_timer': 'not enabled'}


def dispatch(args):
    command = args.command
    if command == 'equipment-review':
        if not args.state or not args.input or args.loadouts:
            raise Invalid('equipment-review needs --state and one exact --input request')
        path = Path(args.input)
        if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
            raise Invalid('equipment-review input must be one bounded absolute regular file')
        try:
            request = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError):
            raise Invalid('equipment-review request is unreadable JSON') from None
        return equipment_review(args.state, request)
    if command == 'assess':
        if not args.state or not args.input:
            raise Invalid('assess needs --state and --input assessment file')
        return record_assessment(args.state, args.input)
    if command == 'catalog':
        return catalog_view(args.state)
    if command == 'profiles':
        return {key: selection(key, args.state)['profile'] for key in profiles()} if args.state else profiles()
    if command == 'suggestions':
        return suggestions(args.state)
    if command == 'select':
        if len(args.loadouts) != 1:
            raise Invalid('select requires one catalog profile id')
        return selection(args.loadouts[0], args.state)
    if command == 'trial':
        from context_trials import run_trial
        if len(args.loadouts) != 1 or not args.destination:
            raise Invalid('trial requires a trusted recipe and --destination')
        return run_trial(args.loadouts[0], args.destination, execute=args.execute, cache=args.wheel_cache)
    if command in ('pause', 'resume'):
        if not args.state:
            raise Invalid('maintenance needs --state private absolute directory')
        return control(args.state, command == 'pause')
    if command == 'evolve':
        if not args.state:
            raise Invalid('evolve needs --state private absolute directory')
        report = None
        if args.input:
            if not all((args.sha256, args.producer, args.commit, args.interest)):
                raise Invalid('intake needs --sha256 --producer --commit --interest')
            report = intake(args.input, args.sha256, args.producer, args.commit, args.interest, args.fixture)
        return maintenance(args.state, report, execute_trials=args.execute, wheel_cache=args.wheel_cache)
    if command == 'decide':
        if not args.state or len(args.loadouts) != 2 or not args.sha256:
            raise Invalid('decide needs PROFILE OPTION --state --sha256 retained intake')
        return approve_selection(args.state, *args.loadouts, args.sha256)
    raise Invalid('unsupported library operation')
