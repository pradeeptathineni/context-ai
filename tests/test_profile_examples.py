"""Characterize generic example metadata without changing legacy profile behavior."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import context_ai as c
import context_library as lib


class ProfileExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads((ROOT / 'tests/fixtures/profile-compatibility-v1.json').read_text())['profiles']

    def test_unbound_examples_do_not_report_a_current_consumer_runtime(self):
        for id in set(self.baseline) - {'simulation'}:
            with self.subTest(profile=id):
                p = lib.profile(id)
                self.assertIsNone(p['project'])
                self.assertEqual(set(p['environment']), {'snapshot_scope'})

    def test_legacy_identity_policy_and_trial_snapshot_remain_exact(self):
        self.assertEqual(set(lib.profiles()), set(self.baseline))
        for id, expected in self.baseline.items():
            with self.subTest(profile=id):
                p = lib.profile(id)
                self.assertEqual(p['id'], id)
                self.assertEqual(p['schema_version'], expected['schema_version'])
                self.assertEqual(p['policy'], expected['policy'])
                self.assertEqual(c.digest(c.encoded(p['snapshot'])), expected['snapshot_sha256'])
                self.assertEqual([{'option': x['option'], 'concern': x['concern']} for x in p['selections']], expected['selections'])

    def test_same_selection_delivers_same_resource_bytes(self):
        for id, expected in self.baseline.items():
            with self.subTest(profile=id):
                s = lib.selection(id)
                self.assertEqual(s['loadouts'], expected['loadouts'])
                self.assertEqual(s['capabilities'], expected['capabilities'])
                self.assertEqual([x['id'] for x in s['direct_upstream']], expected['direct_upstream_ids'])
                lock, files = c.source_resolution(s['loadouts'], 'both', extras=s['capabilities'])
                self.assertEqual(lock['resources'], expected['resource_hashes'])
                self.assertEqual(lock['source_tree_sha256'], expected['source_tree_sha256'])
                self.assertEqual({name: c.digest(raw) for name, raw in files.items()}, expected['resource_hashes'])

    def test_metadata_changes_preserve_trial_identity_but_policy_and_snapshot_do_not(self):
        current = lib.profile('context')
        prior = copy.deepcopy(current)
        prior.update(project='https://example.invalid/prior', purpose='Synthetic prior purpose',
                     environment={'runtime': 'Synthetic prior runtime'}, priorities=['Synthetic prior preference'])
        prior['selections'][0]['reason'] = 'Synthetic prior rationale'
        planned = {'recipe_sha256': 'a' * 64, 'runner_sha256': 'b' * 64,
                   'preparation': {'ready': True}, 'resources': {'synthetic.txt': 'c' * 64},
                   'runtime': {'interpreter': 'synthetic'}}
        with tempfile.TemporaryDirectory() as directory, patch('context_trials.run_trial', return_value=planned):
            state = Path(directory).resolve()
            key = lib.trial_plan(state, current, 'synthetic', None)
            self.assertEqual(lib.trial_plan(state, prior, 'synthetic', None), key)
            changed_snapshot = copy.deepcopy(current)
            changed_snapshot['snapshot']['revision'] = 'synthetic changed revision'
            self.assertNotEqual(lib.trial_plan(state, changed_snapshot, 'synthetic', None), key)
            changed_policy = copy.deepcopy(current)
            changed_policy['policy']['updates'] = []
            self.assertNotEqual(lib.trial_plan(state, changed_policy, 'synthetic', None), key)

    def test_catalog_basename_and_caller_task_file_remain_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / 'consumer'
            project.mkdir()
            supplied = root / 'home-lab.yaml'
            supplied.write_text('This is not a catalog declaration.\n')
            def invoke(command):
                return json.loads(subprocess.check_output([sys.executable, str(ROOT / 'scripts/context_ai.py'), command, '--profile', str(supplied), '--project', str(project)], text=True))
            plan = invoke('plan')
            self.assertEqual(plan['selection']['profile']['id'], 'home-lab')
            task = {'schema_version': 1, 'task': 'Inspect this caller-owned task without installing anything.', 'verification': ['No consumer files changed.']}
            supplied.write_text(json.dumps(task))
            self.assertEqual(invoke('packet')['task'], task['task'])
            self.assertEqual(list(project.iterdir()), [])

    def test_private_update_is_isolated_and_denied_policy_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory).resolve() / 'one'
            sha = 'a' * 64
            original = lib.selection('signals')['profile']['selections']
            home = lib.selection('home-lab')['profile']['selections']
            with lib.locked(state):
                lib.save_event(state, {'intake_sha': sha, 'mode': 'native', 'assessments': [{'option': 'context-tdd', 'evidence': [sha], 'evidence_class': 'source-inspection'}]})
            lib.approve_selection(state, 'signals', 'context-tdd', sha)
            self.assertIn('context-tdd', [x['option'] for x in lib.selection('signals', state)['profile']['selections']])
            self.assertEqual(lib.selection('signals')['profile']['selections'], original)
            self.assertEqual(lib.selection('home-lab', state)['profile']['selections'], home)
            self.assertEqual(lib.selection('signals', Path(directory).resolve() / 'two')['profile']['selections'], original)
            before = {p.name: p.read_bytes() for p in (state / 'events').glob('*.json')}
            with self.assertRaisesRegex(c.Invalid, 'standing policy'):
                lib.approve_selection(state, 'home-lab', 'context-tdd', sha)
            self.assertEqual({p.name: p.read_bytes() for p in (state / 'events').glob('*.json')}, before)


if __name__ == '__main__':
    unittest.main()
