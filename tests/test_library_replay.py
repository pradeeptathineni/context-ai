import copy
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


class EffectiveSelectionReplay(unittest.TestCase):
    """Public functions with authored profiles/state; never original profile YAML."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name).resolve() / 'state'
        self.options = lib.inventory()
        self.profiles = {name: self.fixture(name) for name in ('replay-a', 'replay-b')}
        original_document = lib.document

        def document(name):
            if name.startswith('profiles/'):
                value = copy.deepcopy(self.profiles[name.removeprefix('profiles/')])
                c.validate_schema('library-profile', value)
                return value
            return original_document(name)

        for patcher in (patch.object(lib, 'document', side_effect=document),
                        patch.object(lib, 'profiles', side_effect=lambda: {
                            name: lib.profile(name) for name in self.profiles
                        })):
            patcher.start()
            self.addCleanup(patcher.stop)

    def choice(self, option='context-output'):
        return {'option': option, 'concern': self.options[option]['concern'],
                'reason': 'Authored synthetic selection'}

    def fixture(self, name):
        return {'schema_version': 1, 'id': name, 'project': None,
                'snapshot': {'revision': None, 'files': []},
                'purpose': 'Synthetic replay characterization', 'environment': {},
                'priorities': [], 'policy': {'trials': [],
                'updates': ['context-output', 'context-tdd'], 'schedule': False},
                'selections': [self.choice()]}

    def update(self, choices, profile='replay-a', **metadata):
        lib.private_path(self.state)
        return lib.save_event(self.state, {'schema_version': 1, **metadata,
            'profile_updates': [{'profile': profile, 'selections': choices}]})

    def hashes(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (self.state / 'events').glob('*.json')}

    def evidence(self, mode='synthetic-nonfixture-proof'):
        # These authored records simulate the existing gate predicates only;
        # they are not genuine intake, user approval or adoption evidence.
        sha = 'a' * 64
        lib.private_path(self.state)
        lib.save_event(self.state, {'mode': mode, 'intake_sha': sha,
            'assessments': [{'option': option, 'evidence': [sha],
                            'evidence_class': 'source-inspection'}
                           for option in ('context-output', 'context-tdd')]})
        return sha

    def test_normal_same_concern_replacement_preserves_other_concern(self):
        self.profiles['replay-a']['selections'].append(self.choice('context-tdd'))
        sha = self.evidence()
        before = self.hashes()
        result = lib.approve_selection(self.state, 'replay-a', 'context-output', sha)
        effective = lib.selection('replay-a', self.state)
        self.assertEqual([x['option'] for x in result['selection']],
                         ['context-tdd', 'context-output'])
        self.assertEqual(effective['capabilities'], ['context-tdd', 'context-output'])
        self.assertTrue(all(self.hashes()[k] == v for k, v in before.items()))

    def test_different_concern_approval_appends_instead_of_replacing(self):
        sha = self.evidence()
        result = lib.approve_selection(self.state, 'replay-a', 'context-tdd', sha)
        self.assertEqual([x['option'] for x in result['selection']],
                         ['context-output', 'context-tdd'])

    def test_wrong_stored_concern_refuses_before_approval_appends(self):
        bad = self.choice()
        bad['concern'] = 'synthetic-wrong-concern'
        self.update([bad])
        sha = self.evidence()
        before = self.hashes()
        with self.assertRaisesRegex(c.Invalid, 'mismatched concern'):
            lib.selection('replay-a', self.state)
        with self.assertRaises(c.Invalid):
            lib.approve_selection(self.state, 'replay-a', 'context-output', sha)
        self.assertEqual(self.hashes(), before)

    def test_unknown_final_option_is_structured_refusal(self):
        bad = self.choice()
        bad['option'] = 'removed-synthetic-option'
        self.update([bad])
        before = self.hashes()
        with self.assertRaisesRegex(c.Invalid, 'unknown option'):
            lib.selection('replay-a', self.state)
        self.assertEqual(self.hashes(), before)

    def test_catalog_view_uses_the_same_final_selection_boundary(self):
        bad = self.choice()
        bad['concern'] = 'synthetic-wrong-concern'
        self.update([bad])
        with self.assertRaises(c.Invalid):
            lib.catalog_view(self.state)

    def test_well_formed_bad_a_does_not_block_direct_b(self):
        bad = self.choice()
        bad['option'] = 'removed-synthetic-option'
        self.update([bad], profile='replay-a')
        self.assertEqual(lib.selection('replay-b', self.state)['capabilities'],
                         ['context-output'])
        with self.assertRaises(c.Invalid):
            lib.catalog_view(self.state)

    def test_last_update_supersedes_removed_choice_and_bad_payload(self):
        bad = self.choice()
        bad['option'] = 'removed-synthetic-option'
        self.update([bad])
        self.update(None)
        self.update([self.choice('context-tdd')])
        before = self.hashes()
        self.assertEqual(lib.selection('replay-a', self.state)['capabilities'],
                         ['context-tdd'])
        self.assertEqual(self.hashes(), before)

    def test_narrowed_policy_does_not_revoke_valid_history(self):
        self.profiles['replay-a']['policy']['updates'] = []
        historical = self.choice('context-tdd')
        historical['reason'] = 'Synthetic historical decision before policy narrowed'
        self.update([historical], legacy_note={'version': 'authored'})
        sha = self.evidence()
        before = self.hashes()
        result = lib.selection('replay-a', self.state)
        self.assertEqual(result['profile']['selections'], [historical])
        self.assertEqual(result['capabilities'], ['context-tdd'])
        with self.assertRaisesRegex(c.Invalid, 'standing policy'):
            lib.approve_selection(self.state, 'replay-a', 'context-output', sha)
        self.assertEqual(self.hashes(), before)

    def test_existing_overlap_guard_is_preserved(self):
        self.update([self.choice(), self.choice()])
        with self.assertRaisesRegex(c.Invalid, 'overlapping owners'):
            lib.selection('replay-a', self.state)

    def test_final_shape_errors_are_controlled_and_preserve_input(self):
        missing = self.choice()
        del missing['reason']
        bad_type = self.choice()
        bad_type['option'] = []
        empty = self.choice()
        empty['reason'] = ''
        for choices in (None, {}, 'bad', [None], ['bad'], [missing], [bad_type], [empty]):
            with self.subTest(choices=choices):
                self.update(choices)
                before = self.hashes()
                with self.assertRaises(c.Invalid):
                    lib.selection('replay-a', self.state)
                self.assertEqual(self.hashes(), before)

    def test_global_event_shape_errors_are_controlled(self):
        lib.private_path(self.state)
        directory = self.state / 'events'
        directory.mkdir(mode=0o700)
        path = directory / 'authored-shape.json'
        for value in ([], None, {'profile_updates': None}, {'profile_updates': {}},
                      {'profile_updates': [None]}, {'profile_updates': [{}]},
                      {'profile_updates': [{'profile': 3}]},
                      {'profile_updates': [{'profile': ''}]}):
            with self.subTest(value=value):
                data = json.dumps(value).encode()
                path.write_bytes(data)
                with self.assertRaises(c.Invalid):
                    lib.selection('replay-b', self.state)
                self.assertEqual(path.read_bytes(), data)

    def test_malformed_json_diagnostic_names_file_not_body(self):
        lib.private_path(self.state)
        directory = self.state / 'events'
        directory.mkdir(mode=0o700)
        path = directory / 'authored-invalid.json'
        data = b'{"do_not_echo_synthetic_body": '
        path.write_bytes(data)
        with self.assertRaises(c.Invalid) as caught:
            lib.selection('replay-a', self.state)
        self.assertIn(path.name, str(caught.exception))
        self.assertNotIn('do_not_echo', str(caught.exception))
        self.assertEqual(path.read_bytes(), data)

    def test_optional_events_without_updates_stay_usable_and_exact(self):
        lib.private_path(self.state)
        lib.save_event(self.state, {'step': 1, 'assessment_note': 'Synthetic metadata'})
        before = self.hashes()
        self.assertEqual(lib.selection('replay-a', self.state)['capabilities'],
                         ['context-output'])
        self.assertEqual(self.hashes(), before)

    def test_fixture_mode_never_grants_approval(self):
        sha = self.evidence(mode='fixture')
        before = self.hashes()
        with self.assertRaisesRegex(c.Invalid, 'non-fixture'):
            lib.approve_selection(self.state, 'replay-a', 'context-output', sha)
        self.assertEqual(self.hashes(), before)


if __name__ == '__main__':
    unittest.main()
