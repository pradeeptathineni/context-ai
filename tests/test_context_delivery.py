import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import context_ai as c
import context_delivery as d
from context_guidance import GuidanceConflict

SCRIPT = str(ROOT / 'scripts/context_delivery.py')
GENERIC = 'Context delivery failed; inspect local installation.'


class FakeTerminal:
    """Interactive stdin whose payload must never be read."""
    def isatty(self):
        return True

    @property
    def buffer(self):
        raise AssertionError('interactive stdin was read')


def run_main(argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
            mock.patch.object(sys, 'stdin', stdin or io.TextIOWrapper(io.BytesIO(b''))):
        try:
            code = d.main(argv)
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


class ContextDelivery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / 'project'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_text('Project rule wins.\n')
        self.private = Path(self.temp.name) / 'private'
        self.private.mkdir()
        (self.private / 'README.md').write_text('PRIVATE_START_MARKER\n')
        (self.private / 'task.md').write_text('PRIVATE_TASK_MARKER\n')
        lock, files = c.resolve(['essentials'], self.project, 'both')
        c.apply(self.project, lock, files)

    def tearDown(self):
        self.temp.cleanup()

    def test_project_and_private_order_identity_and_receipt(self):
        result = d.prepare(self.project, 'codex', private_root=self.private,
                           private_resources=['task.md', 'task.md'])
        self.assertIn('PRIVATE_START_MARKER', result['context'])
        self.assertEqual(result['context'].count('PRIVATE_TASK_MARKER'), 1)
        self.assertLess(result['context'].index('PRIVATE_START_MARKER'),
                        result['context'].index('project route'))
        public = json.dumps(result['public_receipt'])
        self.assertNotIn('PRIVATE_', public)
        self.assertNotIn(str(self.private), public)
        self.assertEqual(result['local_identity'], d.prepare(
            self.project, 'codex', private_root=self.private,
            private_resources=['task.md'])['local_identity'])
        (self.private / 'task.md').write_text('PRIVATE_CHANGED_MARKER\n')
        changed = d.prepare(self.project, 'codex', private_root=self.private,
                            private_resources=['task.md'])
        self.assertNotEqual(changed['local_identity'], result['local_identity'])
        self.assertEqual(changed['public_receipt']['source_digest'],
                         result['public_receipt']['source_digest'])
        agents = self.project / 'AGENTS.md'
        agents.write_text(agents.read_text().replace('Project rule wins.', 'Private project rule changed.'))
        private_project = d.prepare(self.project, 'codex', private_root=self.private,
                                    private_resources=['task.md'])
        self.assertNotEqual(private_project['local_identity'], changed['local_identity'])
        self.assertEqual(private_project['public_receipt']['source_digest'],
                         result['public_receipt']['source_digest'])

    def test_required_missing_escape_and_bound_fail_before_delivery(self):
        for name in ('missing.md', '../escape.md'):
            with self.subTest(name=name), self.assertRaises(c.Invalid):
                d.prepare(self.project, 'codex', private_root=self.private,
                          private_resources=[name])
        with self.assertRaises(c.Invalid):
            d.prepare(self.project, 'codex', private_root=self.private,
                      max_chars=10)
        optional = d.prepare(self.project, 'codex', private_root=self.private,
                             optional_private_resources=['optional.md'])
        self.assertEqual(optional['public_receipt']['omissions'],
                         [{'scope': 'private', 'reason': 'optional missing'}])
        (self.project / 'AGENTS.md').write_text('Drifted\n')
        with self.assertRaises(c.Invalid):
            d.prepare(self.project, 'codex')

    def test_installed_stage_content_and_drift(self):
        result = d.prepare(self.project, 'codex', stage='implement')
        self.assertIn('procedures/tdd.md', result['context'])
        self.assertTrue(any(item['name'] == 'procedures/tdd.md'
                            for item in result['public_receipt']['selected']))
        target = self.project / '.context-ai/resources/procedures/tdd.md'
        target.write_text('Changed without updating the pin')
        with self.assertRaises(c.Invalid):
            d.prepare(self.project, 'codex', stage='implement')

    def test_advertised_resource_missing_stops_even_without_stage(self):
        (self.project / '.context-ai/resources/core/testing.md').unlink()
        with self.assertRaises(c.Invalid):
            d.prepare(self.project, 'codex')

    def test_hook_payload_and_stop_contract(self):
        payload = {'hook_event_name': 'SessionStart', 'source': 'startup',
                   'cwd': str(self.project)}
        for provider in ('codex', 'claude'):
            with self.subTest(provider=provider):
                response = d.hook_response(provider, payload, private_root=self.private)
                self.assertEqual(response['hookSpecificOutput']['hookEventName'],
                                 'SessionStart')
                self.assertIn('PRIVATE_START_MARKER', response['hookSpecificOutput']['additionalContext'])
                cli_ok = subprocess.run(
                    [sys.executable, str(ROOT / 'scripts/context_delivery.py'),
                     '--provider', provider, '--private-root', str(self.private)],
                    input=json.dumps(payload), capture_output=True, text=True)
                self.assertEqual(cli_ok.returncode, 0)
                self.assertEqual(json.loads(cli_ok.stdout), response)
        for source in ('resume', 'compact', 'clear', 'fork'):
            self.assertIn('additionalContext', d.hook_response(
                'codex', {**payload, 'source': source})['hookSpecificOutput'])
        with self.assertRaises(c.Invalid):
            d.hook_response('codex', {**payload, 'source': 'unknown'})
        cli = subprocess.run([sys.executable, str(ROOT / 'scripts/context_delivery.py'),
                              '--provider', 'claude', '--private-root', str(self.private),
                              '--private-resource', 'missing.md'], input=json.dumps(payload),
                             capture_output=True, text=True)
        self.assertEqual(cli.returncode, 0)
        self.assertFalse(json.loads(cli.stdout)['continue'])
        self.assertNotIn(str(self.private), cli.stdout)
        invalid = subprocess.run([sys.executable, str(ROOT / 'scripts/context_delivery.py'),
                                  '--provider', 'codex'],
                                 input=json.dumps({**payload, 'source': []}),
                                 capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 0)
        self.assertFalse(json.loads(invalid.stdout)['continue'])

    def test_uninstalled_is_not_verified(self):
        other = Path(self.temp.name) / 'other'
        other.mkdir()
        with self.assertRaisesRegex(c.Invalid, 'installation'):
            d.prepare(other, 'codex')

    def test_subdirectory_finds_nearest_equipped_project(self):
        child = self.project / 'src'
        child.mkdir()
        self.assertEqual(d.prepare(child, 'codex', discover_ancestor=True)['public_receipt']['source_digest'],
                         d.prepare(self.project, 'codex')['public_receipt']['source_digest'])

    def test_claude_imports_agents_symlink(self):
        other = Path(self.temp.name) / 'imports'
        other.mkdir()
        (other / 'AGENTS.md').write_text('Project rule.\n')
        (other / 'CLAUDE.md').symlink_to('AGENTS.md')
        lock, files = c.resolve(['essentials'], other, 'both')
        c.apply(other, lock, files)
        self.assertIn('Project rule.', d.prepare(other, 'claude')['context'])

    def test_distinct_installed_selection_changes_public_source_identity(self):
        other = Path(self.temp.name) / 'native'
        other.mkdir()
        (other / 'AGENTS.md').write_text('Another project.\n')
        lock, files = c.resolve([], other, 'both')
        c.apply(other, lock, files)
        self.assertNotEqual(d.prepare(other, 'codex')['public_receipt']['source_digest'],
                            d.prepare(self.project, 'codex')['public_receipt']['source_digest'])

    def equipped(self, name, provider='both'):
        project = Path(self.temp.name) / name
        project.mkdir()
        (project / 'AGENTS.md').write_text('Project rule wins.\n')
        lock, files = c.resolve(['essentials'], project, provider)
        c.apply(project, lock, files)
        return project

    def hook(self, *args, cwd=None, stdin=None, env=None):
        payload = stdin if stdin is not None else json.dumps(
            {'hook_event_name': 'SessionStart', 'source': 'startup',
             'cwd': str(cwd or self.project)}).encode()
        return subprocess.run([sys.executable, SCRIPT, '--provider', 'codex', *args],
                              input=payload, capture_output=True, env=env)

    def test_common_refusals_name_their_cause_and_next_step(self):
        missing = str(Path(self.temp.name) / 'missing')
        unequipped = Path(self.temp.name) / 'unequipped'
        unequipped.mkdir()
        outside = str(Path(self.temp.name) / 'outside.md')
        private = str(self.private)
        cases = [
            ('project_not_equipped', unequipped, []),
            ('project_unavailable', Path(missing), []),
            ('stage_unavailable', self.project, ['--stage', 'nope']),
            ('private_root_required', self.project, ['--private-resource', 'task.md']),
            ('private_root_unavailable', self.project, ['--private-root', missing]),
            ('guidance_unavailable', self.project,
             ['--private-root', private, '--private-resource', 'missing.md']),
            ('task_file_invalid', self.project, ['--task-file', outside]),
        ]
        valid = ['--stage', 'implement', '--private-root', private,
                 '--private-resource', 'task.md', '--task-file', 'src/new.py']
        delivered = json.loads(self.hook(*valid).stdout)
        self.assertNotIn('continue', delivered)
        self.assertIn('PRIVATE_TASK_MARKER', delivered['hookSpecificOutput']['additionalContext'])
        code, out, _ = run_main(['--provider', 'codex', '--project', str(self.project), *valid])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['status'], 'prepared_unverified')
        stops = set()
        for reason, project, args in cases:
            with self.subTest(reason=reason):
                hook = self.hook(*args, cwd=project)
                self.assertEqual(hook.returncode, 0)
                direct = run_main(['--provider', 'codex', '--project', str(project), *args])
                self.assertEqual(direct[0], 2)
                for text in (hook.stdout.decode(), direct[1]):
                    failure = json.loads(text)
                    self.assertFalse(failure['continue'])
                    self.assertEqual(failure['reason'], reason)
                    self.assertNotEqual(failure['stopReason'], GENERIC)
                    self.assertNotIn(self.temp.name, text)
                stops.add(failure['stopReason'])
        self.assertEqual(len(stops), len(cases))

    def test_drift_provider_and_hook_input_refusals(self):
        resource = self.equipped('resource-drift')
        (resource / '.context-ai/resources/core/testing.md').write_text('Changed')
        route = self.equipped('route-drift')
        (route / 'AGENTS.md').write_text('Drifted\n')
        codex_only = self.equipped('codex-only', 'codex')
        for reason, project, provider in (('installation_drift', resource, 'codex'),
                                          ('routing_drift', route, 'codex'),
                                          ('provider_not_installed', codex_only, 'claude')):
            with self.subTest(reason=reason):
                code, out, _ = run_main(['--provider', provider, '--project', str(project)])
                self.assertEqual((code, json.loads(out)['reason']), (2, reason))
                self.assertNotIn(self.temp.name, out)
        self.assertEqual(run_main(['--provider', 'codex', '--project', str(codex_only)])[0], 0)
        for stdin in (b'not json', b'\xff\xfe', b'{"hook_event_name": "Other"}'):
            with self.subTest(stdin=stdin):
                failure = json.loads(self.hook(stdin=stdin).stdout)
                self.assertEqual((failure['continue'], failure['reason']),
                                 (False, 'hook_input_invalid'))

    def test_unknown_and_path_bearing_errors_stay_generic(self):
        secret = '/private/SECRET_PATH/notes.md'
        errors = (c.Invalid('unsafe relative path: ' + secret), c.Invalid('new unlisted ' + secret),
                  ValueError('project unavailable'), OSError(secret), KeyError(secret))
        for error in errors:
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(d, 'prepare', side_effect=error):
                code, out, err = run_main(['--provider', 'codex', '--project', str(self.project)])
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(out), {'continue': False, 'stopReason': GENERIC})
                self.assertNotIn('SECRET_PATH', out + err)
        # Real inside() refusals carry the requested name; none of it may be echoed.
        hook = self.hook('--private-root', str(self.private), '--private-resource', '../escape.md')
        self.assertEqual(json.loads(hook.stdout), {'continue': False, 'stopReason': GENERIC})

    def test_guidance_conflict_keeps_reason_and_local_only_details(self):
        rules = [{'scope': 'project', 'id': 'a', 'path': 'a.md'},
                 {'scope': 'project', 'id': 'b', 'path': 'b.md'}]
        conflict = GuidanceConflict('style', 'src/app.py', rules)
        with mock.patch.object(d, 'prepare', side_effect=conflict):
            for fmt, details in (('receipt', False), ('context', False), ('local', True)):
                with self.subTest(format=fmt):
                    code, out, _ = run_main(['--provider', 'codex', '--project',
                                             str(self.project), '--format', fmt])
                    failure = json.loads(out)
                    self.assertEqual((code, failure['reason']), (2, 'guidance_conflict'))
                    self.assertEqual(failure.get('conflict'), conflict.details if details else None)
        payload = json.dumps({'hook_event_name': 'SessionStart', 'source': 'startup',
                              'cwd': str(self.project)}).encode()
        with mock.patch.object(d, 'hook_response', side_effect=conflict):
            code, out, _ = run_main(['--provider', 'codex'],
                                    stdin=io.TextIOWrapper(io.BytesIO(payload)))
        failure = json.loads(out)
        self.assertEqual((code, failure['reason']), (0, 'guidance_conflict'))
        self.assertNotIn('conflict', failure)

    def test_hook_success_is_ascii_json_with_unicode_preserved(self):
        text = 'Règle — ✓ \U0001f680'
        (self.private / 'README.md').write_text('PRIVATE_START_MARKER ' + text + '\n', encoding='utf-8')
        expected = d.hook_response('codex', {'hook_event_name': 'SessionStart',
                                             'source': 'startup', 'cwd': str(self.project)},
                                   private_root=self.private)
        env = {**os.environ, 'PYTHONIOENCODING': 'ascii:strict'}
        hook = self.hook('--private-root', str(self.private), env=env)
        self.assertEqual(hook.returncode, 0, hook.stderr)
        hook.stdout.decode('ascii')
        parsed = json.loads(hook.stdout)
        self.assertEqual(parsed, expected)
        self.assertIn(text, parsed['hookSpecificOutput']['additionalContext'])

    def test_interactive_direct_call_without_project_is_a_usage_error(self):
        for argv in (['--provider', 'codex'], ['--provider', 'claude', '--private-root', str(self.private)]):
            with self.subTest(argv=argv):
                code, out, err = run_main(argv, stdin=FakeTerminal())
                self.assertEqual((code, out), (2, ''))
                self.assertIn('--project', err)
        code, out, _ = run_main(['--provider', 'codex', '--project', str(self.project)],
                                stdin=FakeTerminal())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['status'], 'prepared_unverified')

    @unittest.skipUnless(hasattr(os, 'openpty'), 'needs a pseudo-terminal')
    def test_native_terminal_stdin_fails_fast_without_waiting(self):
        for extra, code in (([], 2), (['--project', str(self.project)], 0)):
            master, slave = os.openpty()
            try:
                result = subprocess.run([sys.executable, SCRIPT, '--provider', 'codex', *extra],
                                        stdin=slave, capture_output=True, text=True, timeout=20)
            finally:
                os.close(master)
                os.close(slave)
            self.assertEqual(result.returncode, code, result.stderr)
            if code:
                self.assertIn('--project', result.stderr)
                self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
