"""Permission-aware SIGKILL and conflict regressions for lifecycle recovery."""
import base64
import copy
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import context_ai as c
from test_lifecycle_recovery import CHILD


def inventory(project):
    return {p.relative_to(project).as_posix(): (c.digest(p.read_bytes()), p.stat().st_mode & 0o7777)
            for p in project.rglob('*') if p.is_file()}


class LifecycleModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / 'CLAUDE.md').write_text('Parent instructions\n')

    def tearDown(self):
        self.tmp.cleanup()

    def consumer(self, name, selection=('essentials',)):
        project = self.root / name
        project.mkdir()
        lock, files = c.resolve(list(selection), project, 'both')
        c.apply(project, lock, files)
        return project

    def killed(self, project, operation, boundary):
        child = subprocess.Popen([sys.executable, '-B', '-c', 'import os;os.umask(0o022)\n' + CHILD,
                                  str(ROOT / 'scripts'), str(project), operation, boundary],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, _, _ = select.select([child.stdout], [], [], 20)
            self.assertTrue(ready, 'child did not reach boundary')
            self.assertEqual(child.stdout.readline().strip(), 'READY')
            child.kill()
            child.wait(timeout=10)
            self.assertEqual(child.returncode, -9)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
            for stream in (child.stdin, child.stdout, child.stderr):
                stream.close()

    def test_killed_undo_restores_router_resource_receipt_and_instruction_modes(self):
        names = ('.agents/skills/context-loadout/SKILL.md', '.context-ai/resources/core/engineering.md',
                 '.context-ai/lock.json', 'AGENTS.md', 'CLAUDE.md')
        for mode in (0o600, 0o755, 0o644):
            for index, name in enumerate(names):
                with self.subTest(mode=oct(mode), path=name):
                    project = self.consumer(f'case-{mode}-{index}')
                    (project / name).chmod(mode)
                    before = inventory(project)
                    self.killed(project, 'undo', name)
                    self.assertFalse((project / name).exists())
                    self.assertTrue(c.recover(project)['recovered'])
                    self.assertEqual(inventory(project), before)

    def test_killed_apply_restores_deleted_resource_and_existing_instruction_modes(self):
        project = self.consumer('replace')
        resource = '.context-ai/resources/core/engineering.md'
        for name, mode in ((resource, 0o600), ('AGENTS.md', 0o755), ('.context-ai/lock.json', 0o600)):
            (project / name).chmod(mode)
        before = inventory(project)
        # A selection replacement deletes resources and rewrites routing/receipt.
        self.killed(project, 'apply-empty', 'unlink:' + resource)
        self.assertTrue(c.recover(project)['recovered'])
        self.assertEqual(inventory(project), before)
        empty = self.consumer('from-empty', ())
        (empty / 'AGENTS.md').chmod(0o600)
        (empty / 'CLAUDE.md').chmod(0o755)
        (empty / '.context-ai/lock.json').chmod(0o600)
        before = inventory(empty)
        self.killed(empty, 'apply', 'AGENTS.md')
        self.assertTrue(c.recover(empty)['recovered'])
        self.assertEqual(inventory(empty), before)

    def test_foreign_mode_and_byte_changes_are_preserved(self):
        project = self.consumer('foreign')
        name = '.agents/skills/context-loadout/SKILL.md'
        path = project / name
        original = path.read_bytes()
        path.chmod(0o600)
        self.killed(project, 'undo', name)
        path.write_bytes(original)
        path.chmod(0o640)
        self.assertIn(name, c.recover(project)['preserved_conflicts'])
        self.assertEqual(path.stat().st_mode & 0o7777, 0o640)
        path.write_bytes(b'Foreign bytes\r\n')
        path.chmod(0o600)
        self.assertIn(name, c.recover(project)['preserved_conflicts'])
        self.assertEqual(path.read_bytes(), b'Foreign bytes\r\n')
        path.write_bytes(original)
        self.assertTrue(c.recover(project)['recovered'])
        self.assertEqual(path.stat().st_mode & 0o7777, 0o600)

    def test_mode_change_after_journal_is_a_conflict(self):
        project = self.consumer('during', ())
        agents = project / 'AGENTS.md'
        agents.chmod(0o600)
        before = agents.read_bytes()
        lock, files = c.resolve(['essentials'], project, 'both')
        original = c.atomic
        def changed(path, data, **kwargs):
            original(path, data, **kwargs)
            if path.name == 'pending.json':
                agents.chmod(0o640)
        with patch.object(c, 'atomic', side_effect=changed):
            with self.assertRaisesRegex(c.Invalid, 'changed during lifecycle'):
                c.apply(project, lock, files)
        self.assertEqual(agents.read_bytes(), before)
        self.assertEqual(agents.stat().st_mode & 0o7777, 0o640)
        self.assertIn('AGENTS.md', c.recover(project)['preserved_conflicts'])

    def test_killed_recovery_can_repeat_without_losing_restored_modes(self):
        project = self.consumer('repeat')
        resource = '.context-ai/resources/core/engineering.md'
        (project / resource).chmod(0o600)
        (project / 'AGENTS.md').chmod(0o755)
        before = inventory(project)
        self.killed(project, 'undo', '.context-ai/lock.json')
        self.killed(project, 'recover', resource)
        self.assertEqual((project / resource).stat().st_mode & 0o7777, 0o600)
        self.assertTrue(c.recover(project)['recovered'])
        self.assertEqual(inventory(project), before)

    def test_invalid_mode_metadata_and_legacy_records_preserve_all_state(self):
        project = self.root / 'records'
        project.mkdir()
        name = '.context-ai/resources/file.md'
        path = project / name
        path.parent.mkdir(parents=True)
        path.write_bytes(b'new')
        path.chmod(0o600)
        journal = project / '.context-ai/pending.json'
        valid = {'schema_version': 2, 'bound_project': str(project),
                 'before': {name: base64.b64encode(b'old').decode()}, 'after': {name: c.digest(b'new')},
                 'before_modes': {name: 0o600}, 'after_modes': {name: 0o600}}
        variants = []
        for value in (True, -1, 0o10000, '0600', None):
            data = copy.deepcopy(valid)
            data['before_modes'][name] = value
            variants.append(data)
        missing = copy.deepcopy(valid)
        missing['after_modes'] = {}
        variants.append(missing)
        for data in variants:
            with self.subTest(data=data):
                journal.write_bytes(c.encoded(data))
                before = inventory(project)
                with self.assertRaisesRegex(c.Invalid, 'invalid recovery mode'):
                    c.recover(project)
                self.assertEqual(inventory(project), before)
        legacy = {key: value for key, value in valid.items() if key not in ('before_modes', 'after_modes')}
        legacy['schema_version'] = 1
        journal.write_bytes(c.encoded(legacy))
        before = inventory(project)
        with self.assertRaisesRegex(c.Invalid, 'legacy.*original modes.*unknown'):
            c.recover(project)
        self.assertEqual(inventory(project), before)


if __name__ == '__main__':
    unittest.main()
