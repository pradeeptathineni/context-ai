"""Real subprocess contention and SIGKILL checks against disposable consumers."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import context_ai as c

CHILD = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import context_ai as c
project, operation, boundary = Path(sys.argv[2]), sys.argv[3], sys.argv[4]
def pause():
    print('READY', flush=True)
    sys.stdin.read(1)
if boundary == 'preflight':
    original = c.preflight
    def preflight(*args):
        result = original(*args)
        pause()
        return result
    c.preflight = preflight
elif operation == 'undo':
    original = Path.unlink
    def unlink(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path.relative_to(project).as_posix() == boundary:
            pause()
        return result
    Path.unlink = unlink
else:
    original = c.atomic
    def atomic(path, data):
        original(path, data)
        if path.relative_to(project).as_posix() == boundary:
            pause()
    c.atomic = atomic
if operation == 'undo':
    c.undo(project)
else:
    lock, files = c.resolve(['essentials'], project, 'both')
    c.apply(project, lock, files)
'''


def inventory(project):
    return {p.relative_to(project).as_posix(): c.digest(p.read_bytes())
            for p in project.rglob('*') if p.is_file() and not p.is_symlink()
            and '.git' not in p.relative_to(project).parts}


class LifecycleRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name).resolve() / 'consumer'
        self.project.mkdir()
        (self.project / 'AGENTS.md').write_bytes('User é\r\nNo newline'.encode())
        (self.project / 'CLAUDE.md').write_bytes(b'Claude rules\r\n')
        (self.project / 'unrelated.bin').write_bytes(bytes(range(256)))

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, operation, boundary):
        child = subprocess.Popen([sys.executable, '-B', '-c', CHILD, str(ROOT / 'scripts'),
                                  str(self.project), operation, boundary],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True)
        self.addCleanup(self.finish, child)
        ready, _, _ = select.select([child.stdout], [], [], 20)
        if not ready or child.stdout.readline().strip() != 'READY':
            self.stop(child)
            self.fail('child did not reach publish boundary: ' + child.stderr.read())
        return child

    @staticmethod
    def stop(child):
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)

    @classmethod
    def finish(cls, child):
        cls.stop(child)
        for stream in (child.stdin, child.stdout, child.stderr):
            stream.close()

    def cli(self, command):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/context_ai.py'),
                               command, '--project', str(self.project)],
                              capture_output=True, text=True, timeout=20)

    def test_live_writer_excludes_apply_undo_recover_refresh_verify_and_rebind(self):
        lock, files = c.resolve([], self.project, 'codex')
        c.apply(self.project, lock, files)
        before = inventory(self.project)
        child = self.start('apply', 'preflight')
        os.utime(self.project, (1, 1))  # age never grants permission to break a live writer
        outcomes = {name: self.cli(name) for name in ('apply', 'undo', 'recover', 'refresh', 'verify', 'rebind')}
        self.assertTrue(all(r.returncode != 0 and 'lifecycle operation active' in r.stderr
                            for r in outcomes.values()),
                        {name: (r.returncode, r.stderr) for name, r in outcomes.items()})
        self.assertEqual(inventory(self.project), before)
        other = self.project.parent / 'other'
        other.mkdir()
        other_lock, other_files = c.resolve([], other, 'codex')
        c.apply(other, other_lock, other_files)
        self.assertTrue(c.undo(other)['undone'])
        self.stop(child)
        c.apply(self.project, lock, files)

    def test_edit_after_preflight_is_not_overwritten(self):
        lock, files = c.resolve([], self.project, 'codex')
        original = c.preflight
        foreign = 'Foreign é\r\n'.encode()
        def changed(*args):
            check = original(*args)
            (self.project / 'AGENTS.md').write_bytes(foreign)
            return check
        with patch.object(c, 'preflight', side_effect=changed):
            with self.assertRaisesRegex(c.Invalid, 'changed during lifecycle'):
                c.apply(self.project, lock, files)
        self.assertEqual((self.project / 'AGENTS.md').read_bytes(), foreign)

    def test_receipt_edit_after_preflight_is_not_overwritten(self):
        lock, files = c.resolve([], self.project, 'codex')
        c.apply(self.project, lock, files)
        original = c.preflight
        receipt = self.project / '.context-ai/lock.json'
        foreign = receipt.read_bytes() + b'\n'
        def changed(*args):
            check = original(*args)
            receipt.write_bytes(foreign)
            return check
        with patch.object(c, 'preflight', side_effect=changed):
            with self.assertRaisesRegex(c.Invalid, 'changed during lifecycle'):
                c.apply(self.project, lock, files)
        self.assertEqual(receipt.read_bytes(), foreign)

    def test_killed_apply_recovers_every_publish_boundary(self):
        lock, files = c.resolve(['essentials'], self.project, 'both')
        first = next(iter(c.materialized(lock, files)))
        for boundary in ('.context-ai/pending.json', first,
                         '.context-ai/lock.json', 'AGENTS.md', 'CLAUDE.md'):
            with self.subTest(boundary=boundary):
                before = inventory(self.project)
                child = self.start('apply', boundary)
                os.kill(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
                self.assertEqual(child.returncode, -signal.SIGKILL)
                self.assertTrue(c.recover(self.project)['recovered'])
                self.assertEqual(inventory(self.project), before)
                self.assertIsNone(c.installed(self.project))

    def test_killed_replacement_apply_restores_previous_installation(self):
        lock, files = c.resolve([], self.project, 'codex')
        c.apply(self.project, lock, files)
        before = inventory(self.project)
        child = self.start('apply', 'AGENTS.md')
        self.stop(child)
        recovered = self.cli('recover')
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertTrue(json.loads(recovered.stdout)['recovered'])
        self.assertEqual(inventory(self.project), before)
        self.assertEqual(c.installed(self.project)['resolution'], lock)
        c.verify(self.project)

    def test_foreign_edit_during_publish_survives_rollback(self):
        lock, files = c.resolve(['essentials'], self.project, 'both')
        original = c.atomic
        foreign = 'User changed instructions é\r\n'.encode()
        def edited(path, data):
            original(path, data)
            if path.relative_to(self.project).as_posix().startswith('.context-ai/resources/'):
                (self.project / 'AGENTS.md').write_bytes(foreign)
        with patch.object(c, 'atomic', side_effect=edited):
            with self.assertRaisesRegex(c.Invalid, 'changed during lifecycle'):
                c.apply(self.project, lock, files)
        self.assertEqual((self.project / 'AGENTS.md').read_bytes(), foreign)
        self.assertTrue((self.project / '.context-ai/pending.json').exists())
        self.assertEqual(c.recover(self.project)['preserved_conflicts'], ['AGENTS.md'])

    def test_killed_undo_recovers_deleted_resources_and_receipt(self):
        lock, files = c.resolve(['essentials'], self.project, 'both')
        c.apply(self.project, lock, files)
        state = c.installed(self.project)
        for boundary in (next(iter(state['owned'])), '.context-ai/lock.json'):
            with self.subTest(boundary=boundary):
                before = inventory(self.project)
                child = self.start('undo', boundary)
                self.stop(child)
                self.assertTrue(c.recover(self.project)['recovered'])
                self.assertEqual(inventory(self.project), before)
                c.verify(self.project)

    def test_recovery_preserves_foreign_edit_and_retains_actionable_journal(self):
        before = inventory(self.project)
        child = self.start('apply', 'AGENTS.md')
        self.stop(child)
        foreign = 'Post-crash user é\r\n'.encode()
        (self.project / 'AGENTS.md').write_bytes(foreign)
        result = c.recover(self.project)
        self.assertFalse(result['recovered'])
        self.assertEqual(result['preserved_conflicts'], ['AGENTS.md'])
        self.assertEqual((self.project / 'AGENTS.md').read_bytes(), foreign)
        self.assertEqual(inventory(self.project)['unrelated.bin'], before['unrelated.bin'])
        journal = self.project / '.context-ai/pending.json'
        self.assertTrue(journal.exists())
        self.assertIn('AGENTS.md', json.loads(journal.read_text())['before'])
        with self.assertRaisesRegex(c.Invalid, 'run recover'):
            c.installed(self.project)

    def test_symlink_ownership_directory_is_refused(self):
        outside = self.project.parent / 'outside'
        outside.mkdir()
        (outside / 'foreign.bin').write_bytes(b'foreign bytes')
        lock, files = c.resolve([], self.project, 'codex')
        (self.project / '.context-ai').symlink_to(outside)
        with self.assertRaisesRegex(c.Invalid, 'symlink'):
            c.apply(self.project, lock, files)
        self.assertEqual(list(outside.iterdir()), [outside / 'foreign.bin'])
        self.assertEqual((outside / 'foreign.bin').read_bytes(), b'foreign bytes')


if __name__ == '__main__':
    unittest.main()
