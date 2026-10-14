# Authored external recurring-profile regression tests.
#
# Every profile is authored here against the real catalog options; no committed
# profile YAML or private consumer is read as a template. The tests drive the
# actual source CLI in a subprocess and use disposable consumers only.
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts' / 'context_ai.py'

# Concerns of the existing catalog options used below (library/catalog.yaml).
CONCERNS = {
    'context-output': 'output-handling',
    'context-tdd': 'test-first-development',
    'matt-pocock-tdd': 'test-first-development',
    'ecc-whole-harness': 'engineering-harness',
}

AGENTS = b'# Authored consumer\nUser-owned instructions without a trailing newline'
CLAUDE = b'# Authored Claude notes\nUser-owned Claude instructions\n'
NOTES = b'unmanaged \xff bytes \r\n kept exactly\n'


def choice(option, reason='Authored recurring selection'):
    return {'option': option, 'concern': CONCERNS[option], 'reason': reason}


def document(options=('context-output', 'context-tdd'), id='caller-equipment', **extra):
    value = {'schema_version': 1, 'id': id, 'project': None,
             'snapshot': {'revision': None, 'files': []},
             'purpose': 'Authored caller-owned recurring setup', 'environment': {},
             'priorities': ['bounded command output'],
             'policy': {'trials': [], 'updates': [], 'schedule': False},
             'selections': [choice(option) for option in options]}
    value.update(extra)
    return value


def tree(path):
    path = Path(path)
    if not path.exists():
        return None
    return {p.relative_to(path).as_posix(): (p.read_bytes() if p.is_file() else None)
            for p in sorted(path.rglob('*'))}


class ExternalProfileCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.profiles = self.root / 'profiles'
        self.profiles.mkdir()
        self.state = self.root / 'state'  # never created by a refused command
        self.consumer = self.consumer_at('consumer')

    def consumer_at(self, name):
        path = self.root / name
        path.mkdir()
        (path / 'AGENTS.md').write_bytes(AGENTS)
        (path / 'CLAUDE.md').write_bytes(CLAUDE)
        (path / 'notes').mkdir()
        (path / 'notes' / 'user.bin').write_bytes(NOTES)
        return path

    def write(self, name, value):
        path = self.profiles / name
        path.write_text(yaml.safe_dump(value, sort_keys=False))
        return path

    def raw(self, name, data):
        path = self.profiles / name
        path.write_bytes(data if isinstance(data, bytes) else data.encode())
        return path

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], cwd=self.root,
                              capture_output=True, text=True, timeout=120)

    def ok(self, *args):
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def watch(self):
        return {'consumer': tree(self.consumer), 'state': tree(self.state),
                'profiles': tree(self.profiles)}

    def refused(self, *args):
        before = self.watch()
        result = self.cli(*args)
        self.assertNotEqual(result.returncode, 0, args)
        self.assertEqual(result.stdout, '', args)
        self.assertIn('context-ai:', result.stderr, args)
        self.assertEqual(self.watch(), before, args)
        return result.stderr

    def lock(self, consumer=None):
        return ((consumer or self.consumer) / '.context-ai' / 'lock.json').read_bytes()


class SelectionAndEquivalence(ExternalProfileCase):
    def test_exact_file_identity_survives_a_committed_basename(self):
        # 'labs' is a committed example name; only the file's own content applies.
        path = self.write('labs.yaml', document(purpose='Authored caller purpose only'))
        before = path.read_bytes()
        picked = self.ok('select', '--library-profile', path)
        self.assertEqual(picked['profile']['id'], 'caller-equipment')
        self.assertEqual(picked['profile']['purpose'], 'Authored caller purpose only')
        self.assertEqual(picked['capabilities'], ['context-output', 'context-tdd'])
        self.assertEqual(picked['loadouts'], [])
        self.assertEqual(picked['origin']['path'], str(path))
        self.assertEqual(picked['origin']['sha256'], hashlib.sha256(before).hexdigest())
        self.assertIn('not permission', picked['origin']['authority'])
        # Legacy lookup by the same basename is untouched and does not see the file.
        legacy = self.ok('select', 'labs')
        self.assertEqual(legacy['profile']['id'], 'labs')
        self.assertNotEqual(legacy['profile']['purpose'], 'Authored caller purpose only')
        planned = self.ok('plan', '--profile', path, '--project', self.consumer, '--provider', 'both')
        self.assertEqual(planned['profile_id'], 'labs')
        self.assertEqual(path.read_bytes(), before)

    def test_legacy_profile_option_still_ignores_directory_and_unknown_basename(self):
        path = self.write('caller-equipment.yaml', document())
        self.refused('plan', '--profile', path, '--project', self.consumer, '--provider', 'both')

    def test_plan_matches_explicit_with_resource_map_and_writes_nothing(self):
        path = self.write('caller.yaml', document())
        before = self.watch()
        external = self.ok('plan', '--library-profile', path, '--project', self.consumer,
                           '--provider', 'both')
        explicit = self.ok('plan', '--with', 'context-output', '--with', 'context-tdd',
                           '--project', self.consumer, '--provider', 'both')
        self.assertEqual(external['profile_id'], 'caller-equipment')
        self.assertEqual(external['external_delivery'], [])
        plan = external['delivery']
        self.assertEqual(plan['resolution']['resources'], explicit['resolution']['resources'])
        self.assertEqual(plan['resolution'], explicit['resolution'])
        self.assertEqual(plan['writes'], explicit['writes'])
        self.assertIn('context-output', plan['resolution']['capabilities'])
        self.assertIn('context-tdd', plan['resolution']['capabilities'])
        self.assertEqual(self.watch(), before)

    def test_declared_policy_and_snapshot_are_preserved_data_only(self):
        value = document(
            snapshot={'revision': 'authored-rev', 'files': [{'path': 'notes.md', 'sha256': 'a' * 64}]},
            policy={'trials': ['output-helper'], 'updates': ['context-output'], 'schedule': False})
        path = self.write('policy.yaml', value)
        picked = self.ok('select', '--library-profile', path)
        self.assertEqual(picked['profile']['policy'], value['policy'])
        self.assertEqual(picked['profile']['snapshot'], value['snapshot'])
        before = self.watch()
        self.ok('plan', '--library-profile', path, '--project', self.consumer)
        self.assertEqual(self.watch(), before)
        self.assertFalse(self.state.exists())


class Lifecycle(ExternalProfileCase):
    def test_apply_verify_export_undo_preserve_user_bytes_and_source(self):
        path = self.write('caller.yaml', document())
        source = path.read_bytes()
        stamp = path.stat().st_mtime_ns
        applied = self.ok('apply', '--library-profile', path, '--project', self.consumer,
                          '--provider', 'both')
        self.assertEqual(applied['profile_id'], 'caller-equipment')
        self.assertEqual(applied['delivery']['provider'], 'both')
        installed = self.lock()
        # Native resource equivalence with explicit --with delivery.
        twin = self.consumer_at('twin')
        self.ok('apply', '--with', 'context-output', '--with', 'context-tdd',
                '--project', twin, '--provider', 'both')
        mine = tree(self.consumer / '.context-ai' / 'resources')
        self.assertTrue(mine)
        self.assertEqual(mine, tree(twin / '.context-ai' / 'resources'))
        exported = self.ok('export', '--project', self.consumer)
        self.assertEqual(exported, self.ok('export', '--project', twin))
        self.assertEqual(exported['loadouts'], [])
        # Read-only lifecycle commands neither change the lock nor the source file.
        self.ok('verify', '--project', self.consumer)
        self.assertEqual(self.lock(), installed)
        self.assertEqual(path.read_bytes(), source)
        # Managed instruction blocks leave the user's own bytes in place.
        agents = (self.consumer / 'AGENTS.md').read_bytes()
        self.assertIn(AGENTS, agents)
        self.ok('undo', '--project', self.consumer)
        self.assertEqual((self.consumer / 'AGENTS.md').read_bytes(), AGENTS)
        self.assertEqual((self.consumer / 'CLAUDE.md').read_bytes(), CLAUDE)
        self.assertEqual((self.consumer / 'notes' / 'user.bin').read_bytes(), NOTES)
        self.assertFalse((self.consumer / '.context-ai' / 'lock.json').exists())
        self.assertEqual(path.read_bytes(), source)
        self.assertEqual(path.stat().st_mtime_ns, stamp)

    def test_refresh_previews_and_source_edits_need_new_explicit_apply(self):
        path = self.write('caller.yaml', document(options=('context-output',)))
        self.ok('apply', '--library-profile', path, '--project', self.consumer, '--provider', 'both')
        installed = self.lock()
        consumer = tree(self.consumer)
        # The caller changes its own file; nothing installed moves.
        self.write('caller.yaml', document(options=('context-output', 'context-tdd')))
        self.assertEqual(tree(self.consumer), consumer)
        refreshed = self.ok('refresh', '--library-profile', path, '--project', self.consumer)
        self.assertIn('context-tdd', refreshed['delivery']['resolution']['capabilities'])
        self.assertEqual(self.lock(), installed)
        self.assertEqual(tree(self.consumer), consumer)
        self.assertEqual(self.ok('export', '--project', self.consumer)['extra_capabilities'],
                         ['context-output'])
        self.ok('verify', '--project', self.consumer)
        # A separate, explicit apply adopts the edit; undo still restores user bytes.
        self.ok('apply', '--library-profile', path, '--project', self.consumer)
        self.assertNotEqual(self.lock(), installed)
        self.assertEqual(self.ok('export', '--project', self.consumer)['extra_capabilities'],
                         ['context-output', 'context-tdd'])
        self.ok('undo', '--project', self.consumer)
        self.assertEqual((self.consumer / 'AGENTS.md').read_bytes(), AGENTS)

    def test_flag_is_refused_on_installed_consumer_by_other_commands(self):
        path = self.write('caller.yaml', document())
        self.ok('apply', '--library-profile', path, '--project', self.consumer, '--provider', 'both')
        installed = self.lock()
        for command in ('verify', 'export', 'undo', 'recover', 'rebind', 'tools'):
            with self.subTest(command=command):
                self.refused(command, '--library-profile', path, '--project', self.consumer)
        self.assertEqual(self.lock(), installed)
        self.ok('undo', '--project', self.consumer)


class Refusals(ExternalProfileCase):
    def test_mixed_and_ambiguous_arguments_write_nothing(self):
        path = self.write('caller.yaml', document())
        lock_file = self.root / 'unused.lock.json'
        lock_file.write_text('{}')
        flag = ('--library-profile', path, '--project', self.consumer)
        cases = {
            'profile': ('plan', *flag, '--profile', 'labs'),
            'positional': ('plan', 'standard', *flag),
            'lock': ('apply', *flag, '--lock', lock_file),
            'with': ('apply', *flag, '--with', 'context-tdd'),
            'option': ('plan', *flag, '--option', 'brand=authored'),
            'brand': ('plan', *flag, '--brand', 'authored'),
            'design': ('plan', *flag, '--design-procedure', 'lightweight'),
            'state': ('apply', *flag, '--state', self.state),
            'select-state': ('select', '--library-profile', path, '--state', self.state),
            'select-positional': ('select', 'labs', '--library-profile', path),
            'select-project': ('select', '--library-profile', path, '--project', self.consumer),
            'no-project': ('apply', '--library-profile', path),
            'empty-sha': ('select', '--library-profile', path, '--sha256', ''),
            'empty-producer': ('select', '--library-profile', path, '--producer', ''),
            'empty-commit': ('select', '--library-profile', path, '--commit', ''),
            'empty-interest': ('select', '--library-profile', path, '--interest', ''),
        }
        for name, args in cases.items():
            with self.subTest(name=name):
                self.refused(*args)

    def test_unsupported_commands_refuse_before_any_work(self):
        path = self.write('caller.yaml', document())
        for command in ('verify', 'export', 'undo', 'packet', 'catalog', 'profiles', 'handoff',
                        'trial', 'evolve', 'decide', 'pause', 'resume', 'assess', 'suggestions',
                        'list', 'explain', 'decisions', 'owners', 'recover', 'rebind', 'tools'):
            with self.subTest(command=command):
                self.refused(command, '--library-profile', path, '--project', self.consumer)

    def test_missing_unsafe_and_unreadable_files(self):
        real = self.write('real.yaml', document())
        link = self.profiles / 'link.yaml'
        link.symlink_to(real)
        binary = self.raw('binary.yaml', b'\xff\xfe\x00bad')
        cases = {
            'missing': self.profiles / 'absent.yaml',
            'directory': self.profiles,
            'symlink': link,
            'relative': Path('profiles/real.yaml'),
            'binary': binary,
        }
        for name, target in cases.items():
            for command in ('select', 'plan'):
                with self.subTest(name=name, command=command):
                    extra = ('--project', self.consumer) if command == 'plan' else ()
                    self.refused(command, '--library-profile', target, *extra)

    def test_malformed_and_invalid_profiles_refuse_before_writes(self):
        base = document()
        good = yaml.safe_dump(base, sort_keys=False)
        cases = {
            'not-yaml': 'selections: [unterminated',
            'list-root': '- one\n- two\n',
            'empty': '',
            'duplicate-key': good + 'purpose: Another\n',
            'alias': 'schema_version: &v 1\nid: *v\n',
            'wrong-version': good.replace('schema_version: 1', 'schema_version: 2'),
            'unsafe-id': yaml.safe_dump(document(id='Bad Id'), sort_keys=False),
            'extra-field': good + 'authority: granted\n',
            'unknown-option': yaml.safe_dump(
                document(selections=[{'option': 'no-such-option', 'concern': 'output-handling',
                                      'reason': 'Authored unknown'}]), sort_keys=False),
            'wrong-concern': yaml.safe_dump(
                document(selections=[{'option': 'context-output', 'concern': 'test-first-development',
                                      'reason': 'Authored mismatch'}]), sort_keys=False),
            'same-option-twice': yaml.safe_dump(
                document(options=('context-output', 'context-output')), sort_keys=False),
            'overlapping-owner': yaml.safe_dump(
                document(options=('context-tdd', 'matt-pocock-tdd')), sort_keys=False),
            'missing-reason': yaml.safe_dump(
                document(selections=[{'option': 'context-output', 'concern': 'output-handling'}]),
                sort_keys=False),
        }
        for name, text in cases.items():
            path = self.raw(name + '.yaml', text)
            for command in ('select', 'plan', 'apply'):
                with self.subTest(name=name, command=command):
                    extra = ('--project', self.consumer) if command != 'select' else ()
                    self.refused(command, '--library-profile', path, *extra)

    def test_direct_upstream_previews_but_never_applies(self):
        path = self.write('harness.yaml', document(options=('context-output', 'ecc-whole-harness')))
        planned = self.ok('plan', '--library-profile', path, '--project', self.consumer,
                          '--provider', 'both')
        self.assertEqual([row['option'] for row in planned['external_delivery']],
                         ['ecc-whole-harness'])
        self.assertEqual(planned['external_delivery'][0]['status'], 'native-installer-required')
        message = self.refused('apply', '--library-profile', path, '--project', self.consumer,
                               '--provider', 'both')
        self.assertIn('direct-upstream', message)
        self.assertFalse((self.consumer / '.context-ai').exists())


class SourceByteBinding(unittest.TestCase):
    def test_origin_and_selection_share_one_captured_source(self):
        # Authored changing-view simulation: three file reads can parse a
        # different transient value while both surrounding digests stay equal.
        sys.path.insert(0, str(ROOT / 'scripts'))
        import context_library as lib
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp).resolve() / 'caller.yaml'
            raw = json.dumps(document(id='captured-source')).encode()
            path.write_bytes(raw)
            different = json.dumps(document(id='different-transient-view'))
            original = Path.read_text

            def changing_text(value, *args, **kwargs):
                return different if value == path else original(value, *args, **kwargs)

            with patch.object(Path, 'read_text', changing_text):
                picked = lib.external_selection(path)
            self.assertEqual(picked['profile']['id'], 'captured-source')
            self.assertEqual(picked['origin']['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(path.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
