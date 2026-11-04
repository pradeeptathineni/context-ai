import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_context_delivery as fixtures

c, d = fixtures.c, fixtures.d
ROOT = Path(__file__).resolve().parents[1]


class DeliveryIntegrity(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ContextDelivery()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.project, self.private = self.fixture.project, self.fixture.private

    def test_newline_only_project_and_private_changes_bind_raw_bytes_without_public_hashes(self):
        for path, scope, name in [
                (self.private / 'README.md', 'private', 'README.md'),
                (self.project / 'AGENTS.md', 'project', 'AGENTS.md')]:
            with self.subTest(scope=scope):
                raw = path.read_bytes()
                before = d.prepare(self.project, 'codex', private_root=self.private)
                changed = raw.replace(b'\n', b'\r\n')
                path.write_bytes(changed)
                after = d.prepare(self.project, 'codex', private_root=self.private)
                self.assertEqual(before['context'], after['context'])
                self.assertNotEqual(before['local_identity'], after['local_identity'])
                selected = next(r for r in after['local_sources'] if r['scope'] == scope and r['name'] == name)
                self.assertEqual(selected['sha256'], c.digest(changed))
                self.assertEqual(before['public_receipt'], after['public_receipt'])
                self.assertNotIn(selected['sha256'], json.dumps(after['public_receipt']))
                path.write_bytes(raw)

    def test_reinstalled_advertised_resources_invalidate_an_unchanged_preview(self):
        """Bind advertised resources even when the short delivered route is unchanged."""
        before = d.prepare(self.project, 'codex')
        lock_path = self.project / '.context-ai/lock.json'
        lock = json.loads(lock_path.read_text())
        name = next(iter(lock['resolution']['resources']))
        path = self.project / '.context-ai/resources' / name
        path.write_bytes(path.read_bytes() + b'\nSYNTHETIC UPDATED RESOURCE\n')
        sha = c.digest(path.read_bytes())
        lock['resolution']['resources'][name] = sha
        lock['resolution']['source_tree_sha256'] = c.digest(c.encoded(lock['resolution']['resources']))
        lock['owned']['.context-ai/resources/' + name] = sha
        lock_path.write_text(json.dumps(lock))
        after = d.prepare(self.project, 'codex')
        self.assertEqual(before['context'], after['context'])
        self.assertNotEqual(before['local_identity'], after['local_identity'])
        self.assertNotIn(sha, json.dumps(after['public_receipt']))

    def test_changed_native_skill_refuses_delivery_for_both_providers(self):
        """Native skill bytes must match the same installation that preview checked."""
        lock = c.installed(self.project)
        names = [name for name in lock['owned'] if '/skills/' in name]
        self.assertTrue(names)
        for name in names:
            path = self.project / name
            original = path.read_bytes()
            with self.subTest(name=name):
                try:
                    path.write_bytes(original + b'\nSYNTHETIC UNPINNED INSTRUCTION\n')
                    for provider in ('codex', 'claude'):
                        with self.assertRaisesRegex(c.Invalid, '^installed resource drift$'):
                            d.prepare(self.project, provider)
                finally:
                    path.write_bytes(original)
        d.prepare(self.project, 'codex')

    def test_claude_project_identity_uses_complete_original_source_bytes(self):
        project = self.project.parent / 'claude'
        project.mkdir()
        (project / 'AGENTS.md').write_text('SYNTHETIC PROJECT RULE\n')
        (project / 'CLAUDE.md').write_text('SYNTHETIC CLAUDE RULE\n')
        lock, files = c.resolve(['essentials'], project, 'both')
        c.apply(project, lock, files)
        path = project / c.installed(project)['claude_routing']['path']
        before = d.prepare(project, 'claude')
        raw = path.read_bytes().replace(b'\n', b'\r\n')
        path.write_bytes(raw)
        after = d.prepare(project, 'claude')
        self.assertEqual(before['context'], after['context'])
        self.assertNotEqual(before['local_identity'], after['local_identity'])
        selected = next(r for r in after['local_sources'] if r['name'] == 'CLAUDE.md')
        self.assertEqual(selected['sha256'], c.digest(raw))

    def test_valid_raw_pinned_crlf_stage_delivers_and_unpinned_bytes_refuse(self):
        name = 'procedures/tdd.md'
        path = self.project / '.context-ai/resources' / name
        raw = path.read_bytes().replace(b'\n', b'\r\n')
        path.write_bytes(raw)
        lock_path = self.project / '.context-ai/lock.json'
        lock = json.loads(lock_path.read_text())
        lock['resolution']['resources'][name] = c.digest(raw)
        lock['resolution']['source_tree_sha256'] = c.digest(c.encoded(lock['resolution']['resources']))
        lock['owned']['.context-ai/resources/' + name] = c.digest(raw)
        lock_path.write_text(json.dumps(lock))
        c.installed(self.project)
        result = d.prepare(self.project, 'codex', stage='implement')
        selected = next(r for r in result['local_sources'] if r['name'] == name)
        self.assertEqual(selected['sha256'], c.digest(raw))
        self.assertIn(name, result['context'])
        path.write_bytes(raw + b'changed')
        with self.assertRaises(c.Invalid):
            d.prepare(self.project, 'codex', stage='implement')

    def test_managed_only_claude_route_identity_uses_original_bytes(self):
        project = self.project.parent / 'managed-claude'
        project.mkdir()
        (project / 'AGENTS.md').write_text('SYNTHETIC PROJECT RULE\n')
        (project / 'CLAUDE.md').write_text('')
        lock, files = c.resolve(['essentials'], project, 'both')
        c.apply(project, lock, files)
        path = project / c.installed(project)['claude_routing']['path']
        before = d.prepare(project, 'claude')
        raw = path.read_bytes().replace(b'\n', b'\r\n')
        path.write_bytes(raw)
        after = d.prepare(project, 'claude')
        self.assertEqual(before['context'], after['context'])
        self.assertNotEqual(before['local_identity'], after['local_identity'])
        selected = next(r for r in after['local_sources'] if r['name'] == 'CLAUDE.md')
        self.assertEqual(selected['sha256'], c.digest(raw))

    def test_declared_manifest_and_rule_identity_use_raw_bytes(self):
        for root, scope, manifest in [
                (self.project, 'project', '.context-ai/guidance.yaml'),
                (self.private, 'private', 'guidance.yaml')]:
            path = root / manifest
            path.write_text(json.dumps({'schema_version': 1, 'rules': [
                {'id': 'synthetic-rule', 'path': 'rule.md'}]}) + '\n')
            (root / 'rule.md').write_bytes(b'SYNTHETIC DECLARED RULE\n')
            for selected_path, name in [(path, manifest), (root / 'rule.md', 'rule.md')]:
                with self.subTest(scope=scope, name=name):
                    before = d.prepare(self.project, 'codex', private_root=self.private)
                    raw = selected_path.read_bytes().replace(b'\n', b'\r\n')
                    selected_path.write_bytes(raw)
                    after = d.prepare(self.project, 'codex', private_root=self.private)
                    selected = next(r for r in after['local_sources'] if r['scope'] == scope and r['name'] == name)
                    self.assertEqual(selected['sha256'], c.digest(raw))
                    self.assertNotEqual(before['local_identity'], after['local_identity'])
                    self.assertEqual(before['public_receipt'], after['public_receipt'])

    def test_direct_root_refuses_parent_installation_while_hook_discovers_it(self):
        child = self.project / 'nested'
        child.mkdir()
        (child / 'AGENTS.md').write_text('SYNTHETIC NESTED RULE\n')
        with self.assertRaisesRegex(c.Invalid, 'installation'):
            d.prepare(child, 'codex')
        output = d.hook_response('codex', {'hook_event_name': 'SessionStart', 'source': 'startup', 'cwd': str(child)})
        self.assertIn('Project rule wins.', output['hookSpecificOutput']['additionalContext'])
        self.assertEqual(d.prepare(child, 'codex', discover_ancestor=True)['local_identity'],
                         d.prepare(self.project, 'codex')['local_identity'])
        direct = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/context_delivery.py'),
                                 '--project', str(child), '--provider', 'codex'], capture_output=True, text=True)
        self.assertEqual(direct.returncode, 2)
        self.assertFalse(json.loads(direct.stdout)['continue'])
        self.assertNotIn(str(child), direct.stdout)

    def test_nested_installation_and_task_paths_stay_at_the_selected_root(self):
        child = self.project / 'nested'
        child.mkdir()
        (child / 'AGENTS.md').write_text('SYNTHETIC NESTED RULE\n')
        lock, files = c.resolve([], child, 'both')
        c.apply(child, lock, files)
        (child / 'rule.md').write_text('SYNTHETIC DOCS RULE\n')
        (child / '.context-ai/guidance.yaml').write_text(json.dumps({'schema_version': 1, 'rules': [
            {'id': 'docs', 'path': 'rule.md', 'globs': 'docs/*.md'}]}))
        result = d.prepare(child, 'codex', task_files=['docs/new.md'])
        self.assertIn('SYNTHETIC NESTED RULE', result['context'])
        self.assertNotIn('Project rule wins.', result['context'])
        self.assertIn('SYNTHETIC DOCS RULE', result['context'])
        self.assertEqual(result['task_guidance']['task_files'], ['docs/new.md'])


if __name__ == '__main__':
    unittest.main()
