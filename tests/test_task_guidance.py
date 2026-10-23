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


class TaskGuidance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.private = Path(self.temp.name) / 'private'
        self.project.mkdir()
        self.private.mkdir()
        (self.project / 'AGENTS.md').write_text('Keep the public API compatible.\n')
        (self.private / 'README.md').write_text('Private defaults apply when compatible.\n')
        lock, files = c.resolve([], self.project, 'both')
        c.apply(self.project, lock, files)

    def rules(self, root, rules):
        path = root / ('.context-ai/guidance.yaml' if root == self.project else 'guidance.yaml')
        path.write_text(json.dumps({'schema_version': 1, 'rules': rules}))

    def body(self, root, path, text):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def prepare(self, files=()):
        return d.prepare(self.project, 'codex', private_root=self.private, task_files=files)

    def test_docs_and_code_receive_different_guidance_with_provenance(self):
        self.body(self.project, 'guidance/docs.md', 'Explain the reader outcome first.')
        self.body(self.project, 'guidance/python.md', 'Preserve typed public interfaces.')
        self.body(self.private, 'voice.md', 'PRIVATE_VOICE: use short natural sentences.')
        self.rules(self.project, [
            {'id': 'docs', 'path': 'guidance/docs.md', 'directory': 'docs'},
            {'id': 'python', 'path': 'guidance/python.md', 'globs': ['**/*.py', '!vendor/**']},
        ])
        self.rules(self.private, [{'id': 'personal-voice', 'path': 'voice.md',
                                   'topic': 'voice', 'globs': '**/*.md'}])
        docs = self.prepare(['docs/guide.md', 'docs/guide.md'])
        code = self.prepare(['src/main.py'])
        self.assertIn('Explain the reader outcome first.', docs['context'])
        self.assertIn('PRIVATE_VOICE', docs['context'])
        self.assertNotIn('typed public interfaces', docs['context'])
        self.assertIn('typed public interfaces', code['context'])
        self.assertNotIn('PRIVATE_VOICE', code['context'])
        self.assertNotEqual(docs['local_identity'], code['local_identity'])
        self.assertEqual(len(docs['task_guidance']['task_files']), 1)
        public = json.dumps(docs['public_receipt'])
        for secret in ('PRIVATE_VOICE', 'personal-voice', 'voice.md', str(self.private)):
            self.assertNotIn(secret, public)
        decisions = docs['task_guidance']['decisions']
        self.assertTrue(any(x['id'] == 'docs' and x['status'] == 'selected' for x in decisions))
        self.assertTrue(any(x['id'] == 'python' and x['reason'] == 'no matching task file' for x in decisions))
        self.assertTrue(any(x['name'] == 'guidance/docs.md' and x['sha256'] for x in docs['local_sources']))

    def test_colocation_glob_negation_global_and_disabled_controls(self):
        self.body(self.project, 'rule.md', 'Scoped instructions.')
        self.rules(self.project, [
            {'id': 'nested', 'path': 'rule.md', 'directory': 'src', 'globs': ['**/*.py', '!generated/**']},
            {'id': 'global', 'path': 'rule.md', 'always_apply': True},
            {'id': 'off', 'path': 'rule.md', 'policy': 'off', 'always_apply': True},
            {'id': 'manual', 'path': 'rule.md', 'always_apply': False},
        ])
        def selected(files):
            return {x['id'] for x in self.prepare(files)['task_guidance']['decisions'] if x['status'] == 'selected'}
        self.assertEqual(selected([]), {'global'})
        self.assertIn('nested', selected(['src/main.py']))
        for path in ('other/src/main.py', 'src/generated/main.py', 'src/main.ts'):
            self.assertNotIn('nested', selected([path]))

    def test_declared_conflicts_resolve_by_owner_then_directory_and_refuse_ties(self):
        for root, path, text in [(self.private, 'voice.md', 'PERSONAL_DEFAULT'),
                                 (self.project, 'root.md', 'PROJECT_VOICE'),
                                 (self.project, 'docs.md', 'DOCS_VOICE')]:
            self.body(root, path, text)
        self.rules(self.private, [{'id': 'private-voice', 'path': 'voice.md', 'topic': 'voice'}])
        self.rules(self.project, [{'id': 'root', 'path': 'root.md', 'topic': 'voice'},
                                 {'id': 'docs', 'path': 'docs.md', 'topic': 'voice', 'directory': 'docs'}])
        result = self.prepare(['docs/a.md'])
        self.assertIn('DOCS_VOICE', result['context'])
        self.assertNotIn('PROJECT_VOICE', result['context'])
        self.assertNotIn('PERSONAL_DEFAULT', result['context'])
        self.assertEqual(sum(x['status'] == 'shadowed' for x in result['task_guidance']['decisions']), 2)
        self.rules(self.project, [{'id': 'a', 'path': 'root.md', 'topic': 'voice'},
                                 {'id': 'b', 'path': 'docs.md', 'topic': 'voice'}])
        with self.assertRaisesRegex(c.Invalid, 'conflict'):
            self.prepare(['docs/a.md'])

    def test_safe_paths_required_sources_and_bounds(self):
        self.body(self.project, 'rule.md', 'Apply guidance.')
        for path in ('../outside.py', '/outside.py'):
            with self.subTest(path=path), self.assertRaises(c.Invalid):
                self.prepare([path])
        (self.project / 'linked').symlink_to(self.private, target_is_directory=True)
        with self.assertRaises(c.Invalid):
            self.prepare(['linked/a.md'])
        self.rules(self.project, [{'id': 'missing', 'path': 'missing.md', 'globs': '*.py'}])
        self.assertNotIn('missing.md', self.prepare(['docs/a.md'])['context'])
        with self.assertRaises(c.Invalid):
            self.prepare(['main.py'])
        self.rules(self.project, [{'id': 'large', 'path': 'rule.md'}])
        self.body(self.project, 'rule.md', 'a' * 9501)
        with self.assertRaises(c.Invalid):
            self.prepare()

    def test_mixed_task_keeps_disjoint_topics_and_explains_overlap_privately(self):
        self.body(self.project, 'docs.md', 'DOCS_VOICE')
        self.body(self.project, 'src.md', 'CODE_VOICE')
        self.rules(self.project, [
            {'id': 'docs', 'path': 'docs.md', 'directory': 'docs', 'topic': 'voice'},
            {'id': 'code', 'path': 'src.md', 'directory': 'src', 'topic': 'voice'}])
        mixed = self.prepare(['docs/a.md', 'src/a.py'])
        self.assertIn('Applies to: docs/a.md\nDOCS_VOICE', mixed['context'])
        self.assertIn('Applies to: src/a.py\nCODE_VOICE', mixed['context'])
        self.rules(self.project, [])
        self.body(self.private, 'one.md', 'PRIVATE_ONE')
        self.body(self.private, 'two.md', 'PRIVATE_TWO')
        self.rules(self.private, [{'id': 'secret-one', 'path': 'one.md', 'topic': 'secret-topic'},
                                 {'id': 'secret-two', 'path': 'two.md', 'topic': 'secret-topic'}])
        command = [sys.executable, str(ROOT / 'scripts/context_delivery.py'), '--provider', 'codex',
                   '--project', str(self.project), '--private-root', str(self.private)]
        public = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(public.returncode, 2)
        self.assertEqual(json.loads(public.stdout)['reason'], 'guidance_conflict')
        self.assertNotIn('secret-', public.stdout)
        local = subprocess.run(command + ['--format', 'local'], capture_output=True, text=True)
        self.assertEqual(json.loads(local.stdout)['conflict']['topic'], 'secret-topic')
        self.assertNotIn('PRIVATE_ONE', local.stdout)

    def test_private_drift_changes_local_identity_only_and_invalid_manifest_refuses(self):
        self.body(self.private, 'voice.md', 'PRIVATE_ONE')
        self.rules(self.private, [{'id': 'private-id', 'path': 'voice.md'}])
        first = self.prepare(['draft.md'])
        self.body(self.private, 'voice.md', 'PRIVATE_TWO')
        second = self.prepare(['draft.md'])
        self.assertNotEqual(first['local_identity'], second['local_identity'])
        self.assertEqual(first['public_receipt'], second['public_receipt'])
        (self.project / '.context-ai/guidance.yaml').write_text('schema_version: 1\nrules: []\nrules: []\n')
        with self.assertRaises(c.Invalid):
            self.prepare()

    def test_read_only_cli_receipt_context_and_hook_share_selection(self):
        self.body(self.private, 'voice.md', 'PRIVATE_CLI_VOICE')
        self.rules(self.private, [{'id': 'voice', 'path': 'voice.md', 'globs': '**/*.md'}])
        base = [sys.executable, str(ROOT / 'scripts/context_delivery.py'), '--provider', 'codex',
                '--private-root', str(self.private), '--task-file', 'docs/a.md']
        receipt = subprocess.run(base + ['--project', str(self.project)], capture_output=True, text=True)
        self.assertEqual(receipt.returncode, 0, receipt.stderr)
        self.assertNotIn('PRIVATE_CLI_VOICE', receipt.stdout)
        self.assertEqual(json.loads(receipt.stdout)['status'], 'prepared_unverified')
        context = subprocess.run(base + ['--project', str(self.project), '--format', 'context'], capture_output=True, text=True)
        payload = {'hook_event_name': 'SessionStart', 'source': 'startup', 'cwd': str(self.project)}
        hook = subprocess.run(base, input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(context.stdout.rstrip(), json.loads(hook.stdout)['hookSpecificOutput']['additionalContext'])
        self.assertIn('PRIVATE_CLI_VOICE', context.stdout)


if __name__ == '__main__':
    unittest.main()
