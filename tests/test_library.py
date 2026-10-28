import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4

import yaml
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
        moved = lib.suggestions()
        self.assertEqual(moved['status'], 'moved')
        self.assertEqual(moved['destination'], 'signals-ai/project-opportunities')
        self.assertEqual(moved['suggestions'], [])
        self.assertEqual(moved['migration']['count'], 13)
        self.assertTrue((ROOT / moved['export_reference']).is_file())
        self.assertTrue((ROOT / moved['receipt_reference']).is_file())

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

    def test_profile_delivery_through_ancestor_alias_uses_canonical_lifecycle_binding(self):
        root=Path(self.temp.name).resolve()
        parent=root/'projects';parent.mkdir()
        project=parent/'consumer';project.mkdir()
        (project/'AGENTS.md').write_bytes(b'User rules\r\n')
        alias=root/'alias';alias.symlink_to(parent,target_is_directory=True)
        selected=alias/'consumer'
        lib.delivery('home-lab',selected,action='apply')
        self.assertEqual(c.installed(project)['bound_project'],str(project))
        self.assertEqual(c.verify(project)['project_checks'],'not_run')
        self.assertFalse(lib.delivery('home-lab',selected,action='refresh')['delivery']['conflicts'])
        self.assertTrue(c.undo(project)['undone'])
        self.assertEqual((project/'AGENTS.md').read_bytes(),b'User rules\r\n')
        with self.assertRaisesRegex(c.Invalid,'absolute consumer'):
            lib.delivery('home-lab',alias,action='apply')

    def test_explicit_provider_on_profile_refresh_overrides_inherited_host(self):
        project=Path(self.temp.name).resolve()/'provider-change';project.mkdir()
        lib.delivery('home-lab',project,provider='codex',action='apply')
        preview=lib.delivery('home-lab',project,provider='both',action='refresh')
        self.assertEqual(preview['delivery']['resolution']['provider'],'both')
        self.assertIn('.claude/skills/context-output/SKILL.md',preview['delivery']['writes'])
        self.assertEqual(c.installed(project)['resolution']['provider'],'codex')
        lib.delivery('home-lab',project,provider='both',action='apply')
        self.assertEqual(c.verify(project)['provider'],'both')
        self.assertTrue(c.undo(project)['undone'])

    def test_missing_peer_does_not_remove_selections(self):
        before = lib.selection('signals')
        result = lib.maintenance(self.state, today=date(2026, 10, 8))
        self.assertEqual(result['status'], 'no-peer-input')
        self.assertTrue(result['due_research'])
        self.assertEqual(lib.selection('signals', self.state)['profile']['selections'], before['profile']['selections'])

    def test_grouped_source_bundle_keeps_distinct_active_equipment_assessments(self):
        original = lib.document
        interests = copy.deepcopy(original('interests'))
        second_scope = copy.deepcopy(interests['interests'][0])
        second_scope['id'] = 'equipment-second'
        interests['interests'].append(second_scope)
        def document(name):
            return interests if name == 'interests' else original(name)
        with patch('context_library.document', side_effect=document):
            report = self.intake()
            self.assertEqual(lib.maintenance(self.state, report)['status'], 'assessed-new-input')
            second = copy.deepcopy(report)
            second['interest'] = 'equipment-second'
            self.assertEqual(lib.maintenance(self.state, second)['status'], 'assessed-new-input')
            self.assertEqual({e['interest'] for e in lib.events(self.state)},
                             {'project-equipment', 'equipment-second'})
            self.assertEqual(lib.maintenance(self.state, second)['status'], 'unchanged')

    def test_transferred_interest_cannot_create_events_or_trials(self):
        before = lib.selection('signals', self.state)
        report = self.intake()
        report['interest'] = 'computer-simulation'
        with patch('context_trials.run_trial') as trial:
            result = lib.maintenance(self.state, report, execute_trials=True)
        trial.assert_not_called()
        self.assertEqual(result['status'], 'moved')
        self.assertEqual(result['actions'], [])
        self.assertEqual(lib.events(self.state), [])
        self.assertEqual({row['id'] for row in result['due_research']}, {'project-equipment'})
        self.assertEqual(lib.selection('signals', self.state), before)

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

    def test_activation_budget_defers_pending_recipes_without_losing_retry(self):
        report = self.intake()
        report['evidence']['recommendations'][0]['canonical_uri'] = lib.inventory()['context-output']['upstream']['url']
        executed = []
        def trial(recipe, destination, execute=False, cache=None):
            plan = {'recipe_sha256': recipe, 'runner_sha256': 'r', 'resources': [], 'runtime': {}}
            if execute:
                destination.mkdir(parents=True)
                (destination / 'trial.json').write_text(json.dumps({'status': 'passed'}))
                executed.append(recipe)
                return {'status': 'passed'}
            return plan
        with patch('context_trials.run_trial', side_effect=trial):
            first = lib.maintenance(self.state, report, execute_trials=True)
            self.assertEqual(len(executed), 2)
            self.assertTrue(any(a['status'] == 'blocked-budget' for a in first['actions']))
            lib.maintenance(self.state, report, execute_trials=True)
            self.assertGreater(len(executed), 2)
            self.assertEqual(lib.maintenance(self.state, report, execute_trials=True)['status'], 'unchanged')

    def test_policy_blocks_unknown_option_and_fixture_active_selection(self):
        result = lib.maintenance(self.state, self.intake())
        with self.assertRaisesRegex(c.Invalid, 'standing policy'):
            lib.approve_selection(self.state, 'home-lab', 'ecc-whole-harness', self.intake()['evidence']['bundle_sha256'])
        with self.assertRaisesRegex(c.Invalid, 'unknown option'):
            lib.approve_selection(self.state, 'signals', 'arbitrary-shell-command', 'a' * 64)
        self.assertTrue(result['event'])

    def test_equipment_review_requires_exact_comparable_pair_and_creates_future_profile_successor(self):
        current, profile_digest = lib._effective_profile(self.state, 'signals')
        request = {
            'schema': 'context-equipment-review-request.v1',
            'operation': 'preview',
            'profileId': 'signals',
            'candidateOptionId': 'context-tdd',
            'contextOwnerRevision': 'e' * 40,
            'criterion': 'Preserve a focused test-first workflow for this project.',
            'evidence': {
                'reference': {
                    'owner': 'sandbox-experiment-evidence',
                    'id': str(uuid4()),
                    'packetSha256': 'a' * 64,
                    'sandboxRevision': '0' * 40,
                    'planSha256': 'b' * 64,
                    'baselineAttemptId': 'baseline-1',
                    'baselineAttemptSha256': 'c' * 64,
                    'candidateAttemptId': 'candidate-1',
                    'candidateAttemptSha256': 'd' * 64,
                },
                'pair': {
                    'verdict': 'comparable', 'outcomeComparable': True,
                    'baselineStatus': 'completed', 'candidateStatus': 'completed',
                    'treatmentFields': ['identity.equipment'], 'unresolved': [],
                    'unknownCriteria': [], 'unknownMeasurements': ['elapsed'],
                    'resourceQualifications': ['elapsed: unknown; no resource claim'],
                    'contextIdentityMatched': True,
                },
                'equipment_binding': {
                    'contextOwnerRevision': 'e' * 40, 'profileId': 'signals',
                    'profileDigest': profile_digest, 'baselineOptionId': 'none',
                    'candidateOptionId': 'context-tdd',
                },
            },
        }
        self.assertIn('signals', current['profile']['id'])
        preview = lib.equipment_review(self.state, request)
        self.assertEqual(preview['status'], 'candidate_for_human_review')
        self.assertTrue(preview['canAccept'])
        self.assertEqual(preview['currentOptionId'], 'none')
        self.assertEqual(preview['compatibility']['status'], 'owner-declared-compatible')
        self.assertEqual(preview['evidence']['pair']['unknownMeasurements'], ['elapsed'])
        self.assertEqual(lib.events(self.state), [])

        insufficient = copy.deepcopy(request)
        insufficient['evidence']['pair']['candidateStatus'] = 'partial'
        withheld = lib.equipment_review(self.state, insufficient)
        self.assertEqual(withheld['status'], 'insufficient_evidence')
        self.assertFalse(withheld['canAccept'])
        with self.assertRaisesRegex(c.Invalid, 'insufficient evidence'):
            lib.equipment_review(self.state, {
                **insufficient, 'operation': 'accept', 'previewDigest': withheld['previewDigest'],
                'reviewId': str(uuid4()), 'accepted': True, 'reason': 'Synthetic test acceptance',
            })
        self.assertEqual(lib.events(self.state), [])

        accepted = lib.equipment_review(self.state, {
            **request, 'operation': 'accept', 'previewDigest': preview['previewDigest'],
            'reviewId': str(uuid4()), 'accepted': True,
            'reason': 'The named project criterion is met by this explicit profile choice.',
        })
        self.assertEqual(accepted['status'], 'accepted_for_future_profile')
        self.assertFalse(accepted['activeConsumerChanges'])
        self.assertEqual(accepted['deliveryState'], 'not-installed')
        reopened = lib.equipment_review(self.state, {
            'schema': 'context-equipment-review-request.v1', 'operation': 'read',
            'reviewId': accepted['reviewId'], 'profileId': 'signals',
        })
        self.assertEqual(reopened['review']['evidenceReference'], request['evidence']['reference'])
        self.assertEqual(reopened['currentness'], 'successor-created')
        self.assertEqual(reopened['effectiveProfile']['selections'][-1]['option'], 'context-tdd')
        self.assertEqual(reopened['review']['deliveryState'], 'not-installed')
        self.assertEqual(len(lib.events(self.state)), 1)

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

    def test_runner_catalog_keeps_source_and_intel_limits_visible(self):
        row = next(o for o in lib.catalog_view()['options'] if o['id'] == 'runner')
        self.assertEqual(row['delivery']['kind'], 'direct-upstream')
        self.assertEqual(row['status'], 'conditional')
        self.assertEqual(row['upstream']['revision'], 'feb2f6804f7f0f8d35e89c2a76e6088b4df3ce43')
        self.assertEqual(row['state'], 'suggested')
        self.assertIn('macOS x86_64: unavailable from official v0.16.2 artifacts; source compilation is unproven.', row['limits'])
        self.assertIn('Existing external-session attachment and accurate live coverage are unverified.', row['limits'])
        self.assertIn('Codex native trust seeding targets and guards are not closed by this inspection.', row['limits'])
        self.assertTrue(all(a['grade'] is None for a in row['assessments']))
        self.assertTrue(all(choice['option'] != 'runner' for p in lib.profiles().values()
                            for choice in p['selections']))

    def test_runner_preview_never_installs_or_refreshes_consumer(self):
        project = Path(self.temp.name).resolve() / 'runner-consumer'
        project.mkdir()
        (project / 'AGENTS.md').write_bytes(b'Unmanaged user instructions\r\n')
        profile = {'schema_version': 1, 'id': 'runner-preview', 'project': None,
                   'snapshot': {'revision': None, 'files': []},
                   'purpose': 'Authored source-only GUI option preview', 'environment': {},
                   'priorities': ['preserve authority'],
                   'policy': {'trials': [], 'updates': [], 'schedule': False},
                   'selections': [{'option': 'runner', 'concern': 'agent-session-control',
                                   'reason': 'Inspect compatibility without installing'},
                                  {'option': 'context-output', 'concern': 'output-handling',
                                   'reason': 'An otherwise deliverable control'}]}
        path = Path(self.temp.name).resolve() / 'caller.yaml'
        path.write_text(yaml.safe_dump(profile))
        before = {p.name: p.read_bytes() for p in project.iterdir()}
        for action in ('plan', 'refresh'):
            preview = lib.external_delivery(path, project, action=action)
            self.assertEqual(preview['external_delivery'][0]['status'], 'native-installer-required')
            self.assertEqual(preview['selection']['direct_upstream'][0]['id'], 'runner')
            self.assertIn('macOS x86_64: unavailable from official v0.16.2 artifacts; source compilation is unproven.',
                          preview['selection']['direct_upstream'][0]['limits'])
            self.assertEqual({p.name: p.read_bytes() for p in project.iterdir()}, before)
        with self.assertRaisesRegex(c.Invalid, 'native installer; no implicit execution'):
            lib.external_delivery(path, project, action='apply')
        self.assertEqual({p.name: p.read_bytes() for p in project.iterdir()}, before)
        self.assertEqual(yaml.safe_load(path.read_text()), profile)

if __name__ == '__main__':
    unittest.main()
