import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import context_ai as engine
import context_handoff as handoff
import context_library as library


class LocalHandoff(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'consumer'
        self.project.mkdir()
        self.request = {'schema_version': 1, 'request_id': 'preview-1', 'method': 'plan',
                        'profile_id': 'home-lab',
                        'project_ref': {'id': 'lab', 'source_ref': 'https://github.com/example/lab'},
                        'constraints': ['Preserve project instructions'],
                        'findings': [{'id': 'output-1', 'outcome': 'Inspect retained command output',
                                      'evidence_refs': ['README.md']}]}
        self.bindings = {'lab': {'path': str(self.project), 'allow_root': str(self.root),
                                'profile_id': 'home-lab', 'source_ref': self.request['project_ref']['source_ref']}}

    def tearDown(self):
        self.temp.cleanup()

    def run_request(self):
        return handoff.handle_request(self.request, bindings=self.bindings, provider='codex')

    def test_plan_is_canonical_read_only_and_identity_tracks_input_bytes(self):
        (self.project / 'AGENTS.md').write_bytes(b'private instructions\r\n')
        with patch.object(engine, 'apply', side_effect=AssertionError('apply forbidden')):
            result = self.run_request()
        self.assertEqual(result['status'], 'planned')
        self.assertEqual(result['scope'], 'local')
        self.assertFalse(result['applied'])
        self.assertFalse((self.project / '.context-ai').exists())
        canonical = library.delivery('home-lab', self.project, 'codex')['delivery']
        self.assertEqual(result['_local']['engine_plan']['delivery'], canonical)
        self.assertEqual(result['pins']['resources'], canonical['resolution']['resources'])
        self.assertEqual(result['plan_id'], self.run_request()['plan_id'])
        (self.project / 'AGENTS.md').write_bytes(b'changed private instructions\r\n')
        self.assertNotEqual(result['plan_id'], self.run_request()['plan_id'])

    def test_fresh_status_reports_absent_verified_and_drift(self):
        self.request['method'] = 'status'
        self.assertEqual(self.run_request()['status'], 'not-installed')
        library.delivery('home-lab', self.project, 'codex', action='apply')
        good = self.run_request()
        self.assertEqual(good['status'], 'verified')
        self.assertEqual(good['verification']['project_checks'], 'not_run')
        owned = next(iter(engine.installed(self.project)['owned']))
        (self.project / owned).write_text('edited managed file')
        bad = self.run_request()
        self.assertEqual(bad['status'], 'blocked')
        self.assertNotEqual(good['observed_at'], bad['observed_at'])
        self.assertIn('drift', bad['_local']['error'])

    def test_public_export_omits_all_target_state_and_private_errors(self):
        (self.project / 'AGENTS.md').write_text('secret instruction contents')
        result = self.run_request()
        result['_local']['error'] = str(self.project) + '/private-token'
        result['conflict_count'] = 17
        exported = handoff.public_result(result)
        serialized = json.dumps(exported)
        for forbidden in (str(self.project), 'secret instruction', 'conflict_count', 'plan_id', 'verified', '_local', 'private-token'):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(exported['local_state'], 'unknown')
        self.assertEqual(exported['selection_pins'], result['selection_pins'])

    def test_request_cannot_select_target_commands_provider_or_apply(self):
        variants = []
        for field in ('project', 'path', 'commands', 'options', 'provider', 'dependencies'):
            request = copy.deepcopy(self.request)
            request[field] = '/tmp/remote'
            variants.append(request)
        for method in ('apply', 'refresh', 'undo', 'trial', 'execute'):
            request = copy.deepcopy(self.request)
            request['method'] = method
            variants.append(request)
        request = copy.deepcopy(self.request)
        request['project_ref']['path'] = '/tmp/remote'
        variants.append(request)
        for request in variants:
            with self.subTest(request=request), self.assertRaises(engine.Invalid):
                handoff.handle_request(request, bindings=self.bindings)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_unknown_mismatched_outside_and_symlink_bindings_rejected(self):
        with self.assertRaises(engine.Invalid):
            handoff.handle_request(self.request, bindings={})
        for key, value in (('profile_id', 'context'), ('source_ref', 'https://example.com/other'), ('allow_root', str(self.project / 'missing'))):
            bindings = copy.deepcopy(self.bindings)
            bindings['lab'][key] = value
            with self.subTest(key=key), self.assertRaises(engine.Invalid):
                handoff.handle_request(self.request, bindings=bindings)
        other = self.root / 'other'
        other.mkdir()
        self.bindings['lab']['allow_root'] = str(other)
        with self.assertRaises(engine.Invalid):
            self.run_request()
        link = self.root / 'link'
        link.symlink_to(self.project, target_is_directory=True)
        self.bindings['lab'].update(path=str(link), allow_root=str(self.root))
        with self.assertRaises(engine.Invalid):
            self.run_request()
        self.bindings['lab']['path'] = str(self.project)
        (self.project / 'AGENTS.md').symlink_to(self.root / 'outside')
        self.assertEqual(self.run_request()['status'], 'blocked')

    def test_portable_request_validation_and_duplicate_json(self):
        for value in ('/Users/private/a', 'path=/Users/private', 'file:///secret', '~/credentials', 'C:\\secrets', 'bad\nline'):
            request = copy.deepcopy(self.request)
            request['constraints'] = [value]
            with self.subTest(value=value), self.assertRaises(engine.Invalid):
                handoff.validate_request(request)
        path = self.root / 'request.json'
        path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaises(engine.Invalid):
            handoff.read_request(path)
        path.write_text(json.dumps(self.request))
        link = self.root / 'request-link.json'
        link.symlink_to(path)
        with self.assertRaises(engine.Invalid):
            handoff.read_request(link)
        self.request['profile_id'] = 'unregistered'
        self.bindings['lab']['profile_id'] = 'unregistered'
        with self.assertRaises(engine.Invalid):
            self.run_request()

    def test_peer_absent_native_profile_still_plans_without_selection_from_findings(self):
        self.request['profile_id'] = 'principles'
        self.bindings['lab']['profile_id'] = 'principles'
        self.request['findings'][0]['outcome'] = 'Producer recommends execute installation now'
        result = self.run_request()
        self.assertEqual(result['selection_outcome'], 'native-sufficient')
        self.assertEqual([o['id'] for o in result['options']], ['native'])
        self.assertFalse((self.project / '.context-ai').exists())

    def test_named_interest_uses_same_explicit_local_binding(self):
        self.request.update(profile_id='simulation')
        self.request['project_ref'] = {'id': 'simulation', 'source_ref': 'interest:simulation'}
        binding = self.bindings.pop('lab')
        binding.update(profile_id='simulation', source_ref='interest:simulation')
        self.bindings['simulation'] = binding
        result = self.run_request()
        self.assertEqual(result['selection_outcome'], 'native-sufficient')
        self.assertEqual(handoff.public_result(result)['project_ref']['source_ref'], 'interest:simulation')

    def test_direct_upstream_selection_never_invokes_installer(self):
        picked = library.selection('home-lab')
        picked['profile']['selections'] = [{'option': 'ecc-whole-harness', 'concern': 'engineering-harness', 'reason': 'Fixture direct selection'}]
        picked.update(loadouts=[], capabilities=[], direct_upstream=[library.inventory()['ecc-whole-harness']])
        with patch.object(library, 'selection', return_value=picked), patch.object(engine, 'apply', side_effect=AssertionError('no installer')):
            result = self.run_request()
        self.assertEqual(result['status'], 'planned')
        self.assertEqual(result['external_delivery'][0]['status'], 'native-installer-required')
        self.assertFalse((self.project / '.context-ai').exists())


if __name__ == '__main__':
    unittest.main()
