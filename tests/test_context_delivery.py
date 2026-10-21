import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import context_ai as c
import context_delivery as d


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
        self.assertEqual(d.prepare(child, 'codex')['public_receipt']['source_digest'],
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


if __name__ == '__main__':
    unittest.main()
