#!/usr/bin/env python3
"""Opt-in trusted recipes; deny-default native isolation is verified before use.

No command text, downloaded entrypoint, hooks, or model-generated recipes are accepted.
Planning is read-only. Execution requires a new, empty destination and fails closed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
try:
    import resource
except ImportError:  # Planning remains available on hosts without Unix limits.
    resource = None
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
RECIPES = {
    'output-helper': {
        'resource_id': 'context-output',
        'files': ['scripts/context_output.py', 'procedures/output.md', 'LICENSE'],
        'purpose': 'Retain failed producer output and recover the actual cause through bounded retrieval.',
        'evidence_class': 'actual-executable-observation-with-controlled-input',
    },
    'tdd-consumer': {
        'resource_id': 'context-tdd',
        'files': ['procedures/tdd.md', 'sourced/mattpocock/tdd/instruction.md',
                  'sourced/mattpocock/tdd/tests.md', 'sourced/mattpocock/tdd/mocking.md',
                  'sourced/mattpocock/LICENSE'],
        'purpose': 'Exercise a public money-formatting seam: a failing test, minimal correction, passing test.',
        'evidence_class': 'deterministic-consumer-fixture; guidance-is-not-executable',
    },
    'hypothesis-undo': {
        'resource_id': 'hypothesis-preservation',
        'files': ['scripts/context_ai.py', 'scripts/context_trial_wheels.py', 'requirements.txt', 'LICENSE'],
        'purpose': 'Generate real Context apply/edit/verify/undo cases and preserve unmanaged and edited managed bytes.',
        'evidence_class': 'actual-executable-candidate-trial-with-controlled-consumers',
    },
}

OUTPUT_DRIVER = r'''
import json, subprocess, sys
from pathlib import Path
p = Path.cwd()
helper = p / 'resources/scripts/context_output.py'
calls = []
def call(*argv, status=0):
    command = [sys.executable, '-I', '-S', str(helper), *map(str, argv)]
    result = subprocess.run(command, capture_output=True, text=True)
    calls.append({'command': command, 'exit_status': result.returncode})
    assert result.returncode == status, (result.returncode, result.stderr)
    assert len(result.stdout.encode()) <= 4097
    return json.loads(result.stdout)
short = call('run', '--log', p/'short.log', '--', sys.executable, '-I', '-S', '-c',
             "import sys; print('starting\\nERROR invalid JSON\\nproducer stopped'); sys.exit(7)", status=7)
assert [r['text'] for r in short['evidence']] == ['starting', 'ERROR invalid JSON', 'producer stopped']
assert short['exit_status'] == 7
long = call('run', '--log', p/'long.log', '--query', 'FAILED', '--', sys.executable, '-I', '-S', '-c',
            "import sys; print('\\n'.join('schema mismatch: required id absent' if i == 49 else 'noise '+str(i+1) for i in range(200))); print('FAILED validation'); sys.exit(9)", status=9)
assert long['raw_lines'] == 201 and long['exit_status'] == 9
assert not any('schema mismatch' in r['text'] for r in long['evidence'])
assert long['tail']['label'] and long['tail']['evidence'][-1]['text'] == 'FAILED validation'
cause = call('inspect', p/'long.log', '--query', 'schema mismatch')
assert any(r['line'] == 50 and r['text'] == 'schema mismatch: required id absent' for r in cause['evidence'])
tail = call('inspect', p/'long.log', '--start', '197', '--lines', '5', '--context', '0')
assert tail['evidence'][-1]['text'] == 'FAILED validation'
for name, code in [('short', 7), ('long', 9)]:
    receipt = json.loads((p/(name+'.log.status.json')).read_text())
    assert receipt['execution'] == 'completed' and receipt['exit_status'] == code
result = {'commands': calls, 'short_failed_log': short, 'long_filtered_view': long, 'recovered_cause': cause,
          'labeled_tail': {'label': 'Last 5 lines of retained failed output', 'view': tail},
          'checks': ['short log complete within budget', 'raw and nonzero status retained',
                     'long failed tail labeled', 'cause omitted by initial filter recovered']}
(p/'consumer-result.json').write_text(json.dumps(result, indent=2)+'\n')
print('Output helper: four acceptance checks passed; producer failures 7 and 9 retained.')
'''

TDD_DRIVER = r'''
import json, subprocess, sys
from pathlib import Path
p = Path.cwd()
(p/'money.py').write_text('def format_cents(cents):\n    return "$" + str(cents / 100)\n')
(p/'test_money.py').write_text('import unittest\nfrom money import format_cents\nclass Money(unittest.TestCase):\n    def test_invoice_amount_has_two_decimal_places(self):\n        self.assertEqual(format_cents(105), "$1.05")\n        self.assertEqual(format_cents(100), "$1.00")\n')
def test(phase):
    command = [sys.executable, '-S', '-m', 'unittest', 'test_money.py']
    run = subprocess.run(command, capture_output=True, text=True)
    (p/(phase+'.log')).write_text(run.stdout+run.stderr)
    return {'phase': phase, 'command': command, 'exit_status': run.returncode, 'raw': phase+'.log'}
red = test('red')
assert red['exit_status'] != 0 and "'$1.0' != '$1.00'" in (p/'red.log').read_text()
(p/'money.py').write_text('def format_cents(cents):\n    return f"${cents // 100}.{cents % 100:02d}"\n')
green = test('green')
assert green['exit_status'] == 0
(p/'consumer-result.json').write_text(json.dumps({'evidence_class': 'deterministic-consumer-fixture',
    'seam': 'format_cents(integer cents) -> invoice display', 'red': red, 'green': green,
    'limitations': ['Synthetic consumer, not a human or model comparison.', 'Pinned guidance was retained, not executed.']}, indent=2)+'\n')
print('TDD consumer: invoice formatting regression failed before correction and passed after correction.')
'''

HYPOTHESIS_DRIVER = r'''
import base64, json, random, sys, time, traceback, unittest
from pathlib import Path
p = Path.cwd()
sys.path[:0] = [str(p/'vendor'), str(p/'snapshot/scripts')]
import context_ai as c
consumers = p/'consumers'
consumers.mkdir()
records = []
setup_started = time.monotonic()
selected_lock, selected_files = c.resolve([], consumers, 'codex', extras=['context-output'])
setup_time = time.monotonic()-setup_started
def exercise(case, arm):
    initial, prefix, suffix, managed_edit, refresh = case
    project = consumers/(arm+'-'+str(len(records)))
    project.mkdir()
    agents = project/'AGENTS.md'
    agents.write_bytes(initial.encode())
    errors = []
    lock, files = selected_lock, selected_files
    plan = c.plan(project, lock, files)
    assert not plan['conflicts']
    c.apply(project, lock, files)
    c.verify(project)
    if refresh:
        c.apply(project, lock, files)
        c.verify(project)
    agents.write_bytes(prefix.encode()+agents.read_bytes()+suffix.encode())
    script = project/'.context-ai/resources/scripts/context_output.py'
    edited = script.read_bytes()+b'\n# user-preserved edit\n'
    if managed_edit:
        script.write_bytes(edited)
    outcome = c.undo(project)
    expected = (prefix+initial+suffix).encode()
    if agents.read_bytes() != expected:
        errors.append('unmanaged AGENTS bytes changed')
    if managed_edit:
        if not script.exists() or script.read_bytes() != edited:
            errors.append('edited managed script bytes were lost')
        if str(script.relative_to(project)) not in outcome['preserved_conflicts']:
            errors.append('edited managed conflict was not reported')
    elif script.exists() or not outcome['undone']:
        errors.append('unedited delivery was not removed')
    record = {'arm': arm, 'case': case, 'errors': errors, 'undo': outcome,
              'expected_agents_base64': base64.b64encode(expected).decode(),
              'observed_agents_base64': base64.b64encode(agents.read_bytes()).decode()}
    records.append(record)
    return errors

rng = random.Random(20261008)
fixed = [('', '', '', False, False), ('owner', '', '', False, True),
         ('owner\n', 'before\n', 'after\n', True, True),
         ('owner\r\n', '', '', False, False), ('π café\r\n', 'local\n', 'tail\n', True, False)]
alphabet = 'abc XYZ019πé\n\r'
baseline_cases = fixed + [(
    ''.join(rng.choice(alphabet) for _ in range(rng.randint(0,24))),
    ''.join(rng.choice('PRE π\n') for _ in range(rng.randint(0,8))),
    ''.join(rng.choice('POST é\n') for _ in range(rng.randint(0,8))),
    rng.choice([False, True]), rng.choice([False, True])) for _ in range(19)]
class Preservation(unittest.TestCase):
    def test_fixed_and_seeded_sequences(self):
        for case in baseline_cases:
            with self.subTest(case=case):
                self.assertEqual(exercise(case, 'baseline'), [])
started = time.monotonic()
with (p/'baseline.log').open('w') as log:
    baseline = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Preservation))
baseline_time = time.monotonic()-started
started = time.monotonic()
from hypothesis import given, settings, strategies as st
import hypothesis
case_strategy = st.tuples(st.text(alphabet=alphabet, max_size=24),
                          st.text(alphabet='PRE π\n', max_size=8),
                          st.text(alphabet='POST é\n', max_size=8), st.booleans(), st.booleans())
@settings(max_examples=32, derandomize=True, database=None, deadline=None)
@given(case_strategy)
def property_preserves_user_bytes(case):
    assert exercise(case, 'hypothesis') == []
candidate_passed = True
try:
    property_preserves_user_bytes()
except Exception:
    candidate_passed = False
    (p/'hypothesis-failure.log').write_text(traceback.format_exc())
candidate_time = time.monotonic()-started
result = {'need': 'Signals project-equipment candidate: edit/undo preservation',
          'hypothesis_version': hypothesis.__version__,
          'shared_portable_selection_setup_seconds': setup_time,
          'acceptance': 'unmanaged AGENTS exact bytes; edited managed bytes retained and conflicts reported; unedited delivery removed',
          'baseline': {'method': 'stdlib unittest plus fixed boundaries and seeded RNG 20261008',
                       'cases': len(baseline_cases), 'passed': baseline.wasSuccessful(), 'elapsed_seconds': baseline_time},
          'candidate': {'method': 'Hypothesis generated lifecycle cases', 'max_examples': 32,
                        'actual_exercise_calls_including_shrink': sum(r['arm']=='hypothesis' for r in records),
                        'passed': candidate_passed, 'elapsed_seconds_including_import': candidate_time,
                        'settings': {'derandomize': True, 'database': None, 'deadline': None, 'plugins': 'disabled'}},
          'failures': [r for r in records if r['errors']], 'all_cases_file': 'cases.json',
          'decision': 'Keep deterministic baseline; Hypothesis is opt-in for generated adversarial preservation cases.',
          'limitations': ['Controlled consumers, no human productivity or superiority claim.',
                         'Candidate and baseline share the same acceptance seam.',
                         'Native binary contents are pinned, not independently audited.']}
(p/'cases.json').write_text(json.dumps(records, indent=2, ensure_ascii=False)+'\n')
(p/'consumer-result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
print(json.dumps(result, ensure_ascii=False))
sys.exit(0 if baseline.wasSuccessful() and candidate_passed else 1)
'''


def _snapshot_files():
    names = ['capabilities.yaml', 'resources.yaml', 'ownership.yaml', 'sources.lock.json', 'LICENSE',
             'scripts/context_ai.py', 'scripts/context_output.py']
    for folder in ['core', 'overlays', 'domains', 'procedures', 'skills', 'providers', 'loadouts',
                   'schemas', 'decisions', 'models', 'sourced', 'archive']:
        for path in sorted((ROOT/folder).rglob('*')):
            if path.is_symlink():
                raise ValueError('source snapshot contains a symlink')
            if path.is_file():
                names.append(path.relative_to(ROOT).as_posix())
    if (ROOT/'REVISION').is_file():
        names.append('REVISION')
    return [{'path': name, 'sha256': _sha(ROOT/name)} for name in sorted(set(names))]

def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _stamp():
    return datetime.now(timezone.utc).isoformat()

def _profile(destination, runtime):
    # No allow-default or broad user-directory rule. Native system and exact runtime
    # reads enable Python; writes are confined to the consumer. Network stays denied.
    quoted = lambda value: json.dumps(str(value))
    reads = ['/System', '/usr/lib', '/usr/share/locale', '/private/var/db/dyld', str(runtime)]
    return '\n'.join([
        '(version 1)', '(deny default)', '(allow process-exec process-fork sysctl-read)',
        '(allow file-read* ' + ' '.join('(subpath '+quoted(p)+')' for p in reads) +
        ' (subpath '+quoted(destination)+') (literal "/") (literal "/usr/bin/git") (literal "/dev/null") (literal "/dev/random") (literal "/dev/urandom"))',
        '(allow file-read-metadata ' + ' '.join('(literal '+quoted(p)+')' for p in runtime.parents) + ')',
        '(allow file-write* (subpath '+quoted(destination)+') (literal "/dev/null"))',
    ]) + '\n'

def _limits(cpu_seconds=10):
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024, 4 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))

def _run(command, destination, environment, label, cpu_seconds=10, wall_seconds=20):
    stdout = destination / (label + '.stdout.log')
    stderr = destination / (label + '.stderr.log')
    begun = time.monotonic()
    with stdout.open('xb') as out, stderr.open('xb') as err:
        process = subprocess.Popen(command, cwd=destination, env=environment,
                                   stdout=out, stderr=err, start_new_session=True,
                                   preexec_fn=lambda: _limits(cpu_seconds))
        timed_out = False
        try:
            status = process.wait(timeout=wall_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            status = process.wait()
        except BaseException:
            # The child owns a separate process group. Ctrl-C of the CLI must
            # also stop that group, rather than leaving a hidden trial running.
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise
    return {'command': command, 'exit_status': status, 'timed_out': timed_out,
            'elapsed_seconds': round(time.monotonic() - begun, 6),
            'stdout': str(stdout), 'stderr': str(stderr),
            'stdout_sha256': _sha(stdout), 'stderr_sha256': _sha(stderr)}

def _safe_destination(destination):
    path = Path(destination).absolute()
    if path.is_symlink():
        raise ValueError('trial destination must not be a symlink')
    # macOS /tmp and /var are platform aliases. Publish and use their canonical
    # destination, rather than allowing the child to resolve arbitrary links.
    path = path.resolve()
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError('trial destination must be new or empty; existing data is never overwritten')
    return path

def run_trial(recipe, destination, execute=False, cache=None):
    """Return a JSON-compatible record; execute only a known trusted recipe.

    The caller persists plans if desired. Executed/blocked records are also retained
    in the exclusively owned destination as trial.json; no automatic catalog mutation.
    """
    if recipe not in RECIPES:
        raise ValueError('unknown trusted trial recipe: ' + str(recipe))
    dest = _safe_destination(destination)
    spec = RECIPES[recipe]
    resources = [{'path': p, 'sha256': _sha(ROOT / p)} for p in spec['files']]
    driver = {'output-helper': OUTPUT_DRIVER, 'tdd-consumer': TDD_DRIVER,
              'hypothesis-undo': HYPOTHESIS_DRIVER}[recipe]
    record = {'schema_version': 1, 'recipe': recipe, 'recipe_version': 1,
              'recipe_sha256': hashlib.sha256(driver.encode()).hexdigest(),
              'runner_sha256': _sha(__file__), 'resource_id': spec['resource_id'],
              'resources': resources, 'purpose': spec['purpose'], 'evidence_class': spec['evidence_class'],
              'destination': str(dest), 'created_at': _stamp(), 'status': 'planned',
              'policy': {'trusted_recipe_only': True, 'network': 'denied', 'personal_home': 'denied',
                         'writes': 'destination only', 'cpu_seconds': 10, 'wall_seconds_per_command': 20,
                         'file_size_bytes': 4194304, 'open_files': 128},
              'environment': {'HOME': str(dest/'home'), 'TMPDIR': str(dest/'tmp'),
                              'PATH': '/usr/bin:/bin', 'PYTHONNOUSERSITE': '1',
                              'PYTHONDONTWRITEBYTECODE': '1', 'LC_ALL': 'C', 'LANG': 'C'},
              'commands': [], 'isolation': {'verified': False}, 'result': None,
              'limitations': ['Controlled input does not establish human usefulness or comparative benefit.']}
    snapshot = None
    wheel_reports = None
    if recipe == 'hypothesis-undo':
        from context_trial_wheels import WHEELS, verified
        snapshot = _snapshot_files()
        identity = json.dumps(snapshot, sort_keys=True).encode()
        record['snapshot'] = {'file_count': len(snapshot), 'tree_sha256': hashlib.sha256(identity).hexdigest(),
                              'manifest': str(dest/'snapshot.json'),
                              'revision_semantics': 'exact working-tree file hashes; not an invented Git execution commit'}
        record['source_snapshot_sha256'] = record['snapshot']['tree_sha256']
        snapshot_bytes = (json.dumps(snapshot, indent=2)+'\n').encode()
        record['resources'] = [*resources, {'path': 'snapshot.json',
                                           'sha256': hashlib.sha256(snapshot_bytes).hexdigest(),
                                           'role': 'trial-source-snapshot-manifest'}]
        record['preparation'] = {'cache': str(Path(cache).resolve()) if cache else None,
                                 'required_wheels': [{k: entry[k] for k in ['filename', 'sha256', 'name', 'version']} for entry in WHEELS],
                                 'ready': False, 'candidate_executed_during_preparation': False}
        if cache:
            try:
                wheel_reports = verified(cache)
                record['preparation']['ready'] = True
            except (ValueError, OSError) as error:
                record['preparation']['reason'] = str(error)
        record['environment'].update({'HYPOTHESIS_NO_PLUGINS': '1',
                                      'HYPOTHESIS_STORAGE_DIRECTORY': str(dest/'hypothesis-storage')})
        record['policy'].update({'cpu_seconds': 60, 'wall_seconds_per_command': 60})
    if recipe == 'tdd-consumer':
        pins = json.loads((ROOT/'sources.lock.json').read_text())
        entries = pins.get('sources', pins.get('snapshots', [])) if isinstance(pins, dict) else pins
        if isinstance(entries, dict):
            entries = list(entries.values())
        pin = next((entry for entry in entries if entry.get('id') == 'mattpocock'), None)
        if not pin:
            raise ValueError('required Matt Pocock source pin is missing')
        for item in resources:
            expected = pin.get('files', {}).get(item['path'])
            if item['path'].startswith('sourced/') and (not expected or item['sha256'] != expected):
                raise ValueError('pinned guidance integrity mismatch: ' + item['path'])
        record['upstream'] = {'repository': pin['repository'], 'revision': pin['revision'],
                              'executed': False}
    python = Path(sys.executable).resolve()
    runtime = Path(sys.base_prefix).resolve()
    sandbox = shutil.which('sandbox-exec') if platform.system() == 'Darwin' and resource else None
    record['runtime'] = {'python': str(python), 'python_sha256': _sha(python),
                         'version': platform.python_version(), 'sandbox': sandbox,
                         'sandbox_sha256': _sha(sandbox) if sandbox else None}
    record['planned_command'] = [sandbox or '/usr/bin/sandbox-exec', '-f', str(dest/'sandbox.sb'),
                                 str(python), '-I', '-S', str(dest/'recipe.py')]
    if not execute:
        return record
    dest.mkdir(parents=True, exist_ok=True)
    def finish(status, reason=None):
        record['status'] = status
        record['finished_at'] = _stamp()
        if reason:
            record['reason'] = reason
        (dest/'trial.json').write_text(json.dumps(record, indent=2)+'\n')
        return record
    if not sandbox:
        return finish('blocked', 'Verified native sandbox-exec is unavailable; no recipe was executed.')
    if recipe == 'hypothesis-undo' and (sys.version_info[:2] != (3, 12) or platform.machine() != 'x86_64'):
        return finish('blocked', 'Reviewed Hypothesis wheel set requires macOS CPython 3.12 x86_64; no candidate executed.')
    if recipe == 'hypothesis-undo' and not wheel_reports:
        return finish('blocked', 'Reviewed trial wheels unavailable. Acquire explicitly with context_trial_wheels.py --cache PATH; no candidate executed.')
    # A runtime located in the user's home would require granting access to that
    # directory; do not broaden permissions to make such an interpreter work.
    if runtime.is_relative_to(Path.home().resolve()):
        return finish('blocked', 'Runtime is inside personal HOME; use a system runtime without widening reads.')
    for directory in ['home', 'tmp']:
        (dest/directory).mkdir()
    policy = _profile(dest, runtime)
    (dest/'sandbox.sb').write_text(policy)
    record['isolation'].update({'backend': 'macOS sandbox-exec', 'profile_sha256': hashlib.sha256(policy.encode()).hexdigest()})
    # The controller creates a non-secret canary. Only the sandboxed child probes
    # it; no personal file contents or credentials are inspected.
    with tempfile.TemporaryDirectory(prefix='context-trial-denial-') as canary:
        sentinel = Path(canary)/'read-canary'
        sentinel.write_text('non-secret isolation canary')
        outside = Path(canary)/'write-canary'
        probe = r'''
import json, socket, sys
from pathlib import Path
checks = {}
try: Path(sys.argv[1]).read_text(); checks['outside_read_denied'] = False
except PermissionError: checks['outside_read_denied'] = True
try: Path(sys.argv[2]).write_text('must be denied'); checks['outside_write_denied'] = False
except PermissionError: checks['outside_write_denied'] = True
try: list(Path(sys.argv[3]).iterdir()); checks['personal_home_denied'] = False
except PermissionError: checks['personal_home_denied'] = True
try:
    s = socket.socket(); s.settimeout(1); s.connect(('127.0.0.1', 9)); checks['network_denied'] = False
except PermissionError: checks['network_denied'] = True
except OSError: checks['network_denied'] = False
Path('probe-result.json').write_text(json.dumps(checks))
sys.exit(0 if all(checks.values()) else 3)
'''
        (dest/'probe.py').write_text(probe)
        command = [sandbox, '-f', str(dest/'sandbox.sb'), str(python), '-I', '-S', str(dest/'probe.py'),
                   str(sentinel), str(outside), str(Path.home().resolve())]
        try:
            observed = _run(command, dest, record['environment'], 'isolation-probe')
        except KeyboardInterrupt:
            return finish('interrupted', 'Isolation probe interrupted; owned process group stopped; no recipe executed.')
        except OSError as error:
            return finish('blocked', 'Native sandbox probe could not start: ' + str(error))
        record['commands'].append(observed)
        probe_result = dest/'probe-result.json'
        if observed['exit_status'] != 0 or not probe_result.is_file() or outside.exists():
            return finish('blocked', 'Native isolation denial probe failed; no recipe was executed. Inspect isolation-probe.stderr.log.')
        checks = json.loads(probe_result.read_text())
        expected = {'outside_read_denied': True, 'outside_write_denied': True,
                    'personal_home_denied': True, 'network_denied': True}
        record['isolation'].update({'checks': checks, 'verified': checks == expected})
        if not record['isolation']['verified']:
            return finish('blocked', 'Native isolation did not deny every required boundary; no recipe was executed.')
    for entry in resources:
        target = dest/'resources'/entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/entry['path'], target)
        if _sha(target) != entry['sha256']:
            return finish('blocked', 'Resource changed while preparing trial; no recipe was executed.')
    if snapshot:
        from context_trial_wheels import extract
        for entry in snapshot:
            target = dest/'snapshot'/entry['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/entry['path'], target)
            if _sha(target) != entry['sha256']:
                return finish('blocked', 'Source snapshot changed during preparation; no candidate executed.')
        (dest/'snapshot.json').write_text(json.dumps(snapshot, indent=2)+'\n')
        try:
            record['preparation']['inspections'] = extract(cache, dest/'vendor')
        except (ValueError, OSError) as error:
            return finish('blocked', 'Reviewed wheel extraction failed: '+str(error))
    (dest/'recipe.py').write_text(driver)
    try:
        observed = _run(record['planned_command'], dest, record['environment'], 'recipe',
                        cpu_seconds=record['policy']['cpu_seconds'],
                        wall_seconds=record['policy']['wall_seconds_per_command'])
    except KeyboardInterrupt:
        return finish('interrupted', 'Trial interrupted; owned sandbox process group stopped and raw logs retained.')
    except OSError as error:
        return finish('failed', 'Trusted recipe could not start: '+str(error))
    record['commands'].append(observed)
    result = dest/'consumer-result.json'
    if result.is_file():
        record['result'] = json.loads(result.read_text())
        record['result_sha256'] = _sha(result)
    if observed['exit_status'] == 0 and result.is_file():
        return finish('passed')
    return finish('failed', 'Trusted recipe did not complete its acceptance checks; raw output retained.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', choices=sorted(RECIPES))
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--cache', type=Path, help='Explicit reviewed wheel cache, only for hypothesis-undo')
    args = parser.parse_args()
    record = run_trial(args.recipe, args.destination, args.execute, cache=args.cache)
    print(json.dumps(record, indent=2))
    return 0 if record['status'] in ['planned', 'passed'] else 2

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
