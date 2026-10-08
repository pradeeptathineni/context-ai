import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import context_ai as c
import context_library as lib


class PersonalLibrary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name).resolve() / 'private'

    def tearDown(self):
        self.temp.cleanup()

    def intake(self):
        source = ROOT / 'tests/fixtures/evidence-bundle-v1.fixture.json'
        return lib.intake(source, hashlib.sha256(source.read_bytes()).hexdigest(), None, None, 'project-equipment', True)

    def test_profiles_and_original_scope_remain_browsable(self):
        options = lib.inventory()
        self.assertTrue(set(c.catalogue()).issubset(options))
        self.assertEqual(lib.catalog_view()['concepts'], 140)
        ps = lib.profiles()
        self.assertIn('labs', ps)
        self.assertIn('home-lab', ps)
        self.assertNotEqual(ps['labs']['selections'], ps['home-lab']['selections'])
        self.assertTrue(all(not p['policy']['schedule'] for p in ps.values()))
        self.assertIn('opportunity', lib.suggestions()['suggestions'][0])

    def test_profile_delivery_pins_then_preserves_edits_on_undo(self):
        project = Path(self.temp.name).resolve() / 'consumer'
        project.mkdir()
        (project / 'AGENTS.md').write_text('User rules\n')
        preview = lib.delivery('home-lab', project)
        self.assertFalse((project / '.context-ai').exists())
        self.assertTrue(preview['delivery']['writes'])
        lib.delivery('home-lab', project, action='apply')
        self.assertEqual(c.verify(project)['project_checks'], 'not_run')
        (project / 'AGENTS.md').write_text('Preface\n' + (project / 'AGENTS.md').read_text())
        c.undo(project)
        self.assertEqual((project / 'AGENTS.md').read_text(), 'Preface\nUser rules\n')

    def test_profile_refresh_apply_keeps_installed_provider_without_override(self):
        project = Path(self.temp.name).resolve() / 'one-host'
        project.mkdir()
        lib.delivery('home-lab', project, provider='codex', action='apply')
        preview = lib.delivery('home-lab', project, action='refresh')
        self.assertEqual(preview['delivery']['resolution']['provider'], 'codex')
        lib.delivery('home-lab', project, action='apply')
        self.assertEqual(c.installed(project)['resolution']['provider'], 'codex')
        self.assertFalse((project / 'CLAUDE.md').exists())

    def test_missing_peer_does_not_remove_selections(self):
        before = lib.selection('signals')
        result = lib.maintenance(self.state, today=date(2026, 10, 8))
        self.assertEqual(result['status'], 'no-peer-input')
        self.assertTrue(result['due_research'])
        self.assertEqual(lib.selection('signals', self.state)['profile']['selections'], before['profile']['selections'])

    def test_grouped_source_bundle_keeps_distinct_interest_assessments(self):
        report = self.intake()
        self.assertEqual(lib.maintenance(self.state, report)['status'], 'assessed-new-input')
        second = copy.deepcopy(report)
        second['interest'] = 'computer-simulation'
        self.assertEqual(lib.maintenance(self.state, second)['status'], 'assessed-new-input')
        self.assertEqual({e['interest'] for e in lib.events(self.state)},
                         {'project-equipment', 'computer-simulation'})
        self.assertEqual(lib.maintenance(self.state, second)['status'], 'unchanged')

    def test_changed_and_unchanged_finite_passes_never_install(self):
        intake = self.intake()
        result = lib.maintenance(self.state, intake, today=date(2026, 10, 8))
        self.assertEqual(result['status'], 'assessed-new-input')
        self.assertEqual(result['actions'][0]['action'], 'inspect-new-option')
        self.assertEqual(lib.maintenance(self.state, intake)['status'], 'unchanged')
        clone = copy.deepcopy(intake)
        clone['evidence']['bundle_sha256'] = 'a' * 64
        clone.pop('_raw_bundle', None)
        self.assertEqual(lib.maintenance(self.state, clone)['status'], 'refetch-no-material-change')
        self.assertEqual(len(lib.events(self.state)), 2)

    def test_only_matched_policy_eligible_known_recipe_can_execute(self):
        intake = self.intake()
        intake['evidence']['recommendations'][0]['canonical_uri'] = lib.inventory()['context-output']['upstream']['url']
        with patch('context_trials.run_trial') as trial:
            result = lib.maintenance(self.state, intake, execute_trials=False)
        trial.assert_not_called()
        self.assertTrue(any(a['status'] == 'eligible' for a in result['actions']))
        self.assertTrue(any(a['status'] == 'blocked-policy' for a in result['actions']))

    def test_unchanged_intake_retries_changed_preparation_then_skips_completed_work(self):
        report = self.intake()
        report['evidence']['recommendations'][0]['canonical_uri'] = lib.inventory()['hypothesis']['upstream']['url']
        ready = False
        executed = []
        def trial(recipe, destination, execute=False, cache=None):
            plan = {'recipe_sha256': 'r', 'runner_sha256': 's', 'resources': [],
                    'runtime': {}, 'preparation': {'ready': ready, 'cache': str(cache)}}
            if execute:
                destination.mkdir(parents=True)
                value = {'status': 'passed' if ready else 'blocked', **plan}
                (destination / 'trial.json').write_text(json.dumps(value))
                executed.append(value['status'])
                return value
            return plan
        with patch('context_trials.run_trial', side_effect=trial):
            lib.maintenance(self.state, report, execute_trials=True)
            before = len(executed)
            self.assertGreater(before, 0)
            self.assertEqual(lib.maintenance(self.state, report, execute_trials=True)['status'], 'unchanged')
            ready = True
            result = lib.maintenance(self.state, report, execute_trials=True)
            self.assertEqual(result['status'], 'assessed-new-input')
            self.assertEqual(len(executed), before * 2)
            self.assertEqual(lib.maintenance(self.state, report, execute_trials=True)['status'], 'unchanged')

            self.assertEqual(lib.maintenance(self.state, report, execute_trials=True, wheel_cache='/another/locator')['status'], 'unchanged')
            self.assertEqual(len(executed), before * 2)

    def test_policy_blocks_unknown_option_and_fixture_active_selection(self):
        result = lib.maintenance(self.state, self.intake())
        with self.assertRaisesRegex(c.Invalid, 'standing policy'):
            lib.approve_selection(self.state, 'home-lab', 'ecc-whole-harness', self.intake()['evidence']['bundle_sha256'])
        with self.assertRaisesRegex(c.Invalid, 'unknown option'):
            lib.approve_selection(self.state, 'signals', 'arbitrary-shell-command', 'a' * 64)
        self.assertTrue(result['event'])

    def test_history_sequence_survives_missing_earlier_event(self):
        with lib.locked(self.state):
            lib.save_event(self.state, {'step': 1})
            lib.save_event(self.state, {'step': 2})
            first = sorted((self.state / 'events').glob('*.json'))[0]
            first.unlink()
            lib.save_event(self.state, {'step': 3})
        names = [p.name.split('-', 1)[0] for p in sorted((self.state / 'events').glob('*.json'))]
        self.assertEqual(names, ['00000002', '00000003'])

    def test_semantic_refetch_keeps_intake_provenance(self):
        report = self.intake()
        lib.maintenance(self.state, report)
        report = copy.deepcopy(report)
        report.pop('_raw_bundle')
        report['evidence']['bundle_sha256'] = 'b' * 64
        lib.maintenance(self.state, report)
        event = lib.events(self.state)[-1]
        self.assertEqual(event['mode'], 'fixture')
        self.assertEqual(event['evidence_report'], report['evidence'])
        self.assertEqual(event['bundle_ref'], 'bundles/' + 'b' * 64 + '.json')

    def test_pause_resume_and_lock(self):
        lib.control(self.state, True)
        self.assertEqual(lib.maintenance(self.state)['status'], 'paused')
        lib.control(self.state, False)
        with lib.locked(self.state):
            with self.assertRaisesRegex(c.Invalid, 'already locked'):
                lib.maintenance(self.state)
        self.assertEqual(lib.maintenance(self.state)['status'], 'no-peer-input')

    def test_symlink_state_and_unsupported_contract_rejected(self):
        target = Path(self.temp.name).resolve() / 'real'; target.mkdir()
        self.state.symlink_to(target)
        with self.assertRaisesRegex(c.Invalid, 'symlink'):
            lib.maintenance(self.state)
        self.state.unlink()
        with self.assertRaisesRegex(c.Invalid, 'unknown interest'):
            lib.intake(ROOT / 'tests/fixtures/evidence-bundle-v1.fixture.json', 'a' * 64, None, None, 'invented')

if __name__ == '__main__':
    unittest.main()
