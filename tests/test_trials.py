"""Trusted trial permissions, retained records, and actual native isolation."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import shutil
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import context_trials as trials
import context_trial_wheels as wheels


class ControlledTrials(unittest.TestCase):
    def test_plan_is_read_only_and_exactly_identified(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/'consumer'
            with patch.object(trials, '_run', side_effect=AssertionError('plan must not execute')):
                record = trials.run_trial('output-helper', dest)
            self.assertFalse(dest.exists())
            self.assertEqual(record['status'], 'planned')
            self.assertFalse(record['isolation']['verified'])
            self.assertEqual(record['commands'], [])
            self.assertEqual(record['policy']['network'], 'denied')
            for item in record['resources']:
                self.assertEqual(item['sha256'], hashlib.sha256((trials.ROOT/item['path']).read_bytes()).hexdigest())
            self.assertEqual(set(record['environment']), {'HOME', 'TMPDIR', 'PATH', 'PYTHONNOUSERSITE',
                                                         'PYTHONDONTWRITEBYTECODE', 'LC_ALL', 'LANG'})

    def test_never_accepts_model_command_or_unknown_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'unknown trusted'):
                trials.run_trial('python -c "print(1)"', Path(tmp)/'consumer', True)

    def test_unavailable_sandbox_is_retained_as_blocked_without_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/'consumer'
            with patch.object(trials.platform, 'system', return_value='Linux'), \
                 patch.object(trials, '_run', side_effect=AssertionError('unavailable boundary must not execute')):
                record = trials.run_trial('output-helper', dest, True)
            self.assertEqual(record['status'], 'blocked')
            self.assertIsNone(record['result'])
            self.assertFalse((dest/'recipe.py').exists())
            self.assertEqual(json.loads((dest/'trial.json').read_text()), record)

    def test_existing_data_and_symlink_destination_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            occupied = root/'occupied'
            occupied.mkdir()
            (occupied/'user.txt').write_text('keep me')
            linked = root/'linked'
            linked.symlink_to(occupied, target_is_directory=True)
            for dest in [occupied, linked]:
                with self.assertRaises(ValueError):
                    trials.run_trial('output-helper', dest, True)
            self.assertEqual((occupied/'user.txt').read_text(), 'keep me')
            self.assertEqual(list(occupied.iterdir()), [occupied/'user.txt'])

    def test_tdd_guidance_pin_is_retained_without_executable_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = trials.run_trial('tdd-consumer', Path(tmp)/'consumer')
            self.assertEqual(record['upstream']['revision'], 'f3fc5632f401156837ee3872f14fe33ccf1024ea')
            self.assertFalse(record['upstream']['executed'])
            self.assertIn('fixture', record['evidence_class'])

    def test_hypothesis_plan_pins_source_and_never_acquires_or_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)/'consumer'
            with patch.object(wheels, 'prepare', side_effect=AssertionError('plan must not acquire')):
                record = trials.run_trial('hypothesis-undo', destination)
            self.assertFalse(destination.exists())
            self.assertFalse(record['preparation']['ready'])
            self.assertEqual(len(record['preparation']['required_wheels']), 9)
            self.assertEqual(record['source_snapshot_sha256'], record['snapshot']['tree_sha256'])
            self.assertTrue(any(row.get('role') == 'trial-source-snapshot-manifest' for row in record['resources']))
            self.assertIn('-S', record['planned_command'])
            self.assertEqual(record['environment']['HYPOTHESIS_NO_PLUGINS'], '1')

    def test_missing_reviewed_wheels_cannot_execute_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(trials, '_run', side_effect=AssertionError('missing wheels must not execute')):
                record = trials.run_trial('hypothesis-undo', Path(tmp)/'consumer', True)
            self.assertEqual(record['status'], 'blocked')
            self.assertIsNone(record['result'])

    def test_wheel_boundary_rejects_changed_bytes_hooks_and_escaping_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'fixture.whl'
            for member in ['../../outside', 'package/startup.pth', 'package.data/scripts/installer']:
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr(member, 'untrusted payload')
                expected = {'filename': 'fixture.whl', 'sha256': wheels.sha(path)}
                with self.assertRaises(ValueError):
                    wheels.inspect_wheel(path, expected)
            with self.assertRaisesRegex(ValueError, 'missing or changed'):
                wheels.inspect_wheel(path, {'filename': 'fixture.whl', 'sha256': '0'*64})

    @unittest.skipUnless(platform.system() == 'Darwin' and shutil.which('sandbox-exec'), 'macOS native sandbox required')
    def test_destination_node_resolution_preserves_outside_read_denial(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('existing approved Node runtime unavailable')
        version = subprocess.run([node, '--version'], capture_output=True, text=True, timeout=3)
        if version.returncode or int(version.stdout.strip().lstrip('v').split('.')[0]) < 20:
            self.skipTest('existing Node20+ runtime required')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            destination = root / 'consumer'
            destination.mkdir()
            runtime = Path(sys.base_prefix).resolve()
            outside = root / 'outside.txt'
            outside.write_text('non-secret read canary')
            local_node = destination / 'node'
            shutil.copy2(Path(node).resolve(), local_node)
            driver = destination / 'main.js'
            driver.write_text('const fs=require("node:fs"); let denied=false; '
                              'try{fs.readFileSync(' + json.dumps(str(outside)) + ');}'
                              'catch(e){denied=["EPERM","EACCES"].includes(e.code);}'
                              'process.stdout.write("resolved:"+denied);')
            policy = destination / 'sandbox.sb'
            policy.write_text(trials._profile(destination, runtime))
            result = trials._run(['/usr/bin/sandbox-exec', '-f', str(policy),
                                  str(local_node), str(driver)], destination,
                                 {'HOME': str(destination), 'PATH': '/usr/bin:/bin'}, 'node-resolution')
            self.assertEqual(result['exit_status'], 0)
            self.assertEqual(Path(result['stdout']).read_text(), 'resolved:true')

    def test_cache_replacement_cannot_change_inspected_or_extracted_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root/'cache'
            cache.mkdir()
            path = cache/'fixture.whl'
            original_zip = zipfile.ZipFile
            with original_zip(path, 'w') as archive:
                archive.writestr('fixture-1.dist-info/METADATA', 'Name: fixture\nVersion: 1\n')
                archive.writestr('fixture.py', 'approved bytes\n')
            expected = {'filename': path.name, 'sha256': wheels.sha(path), 'name': 'fixture',
                        'version': '1', 'license': 'MIT', 'license_files': [],
                        'native': [], 'scripts': []}
            replaced = False
            def replace_cache_before_archive_read(source, *args, **kwargs):
                nonlocal replaced
                if not replaced:
                    replaced = True
                    with original_zip(path, 'w') as malicious:
                        malicious.writestr('../escaped-canary', 'unapproved payload')
                return original_zip(source, *args, **kwargs)
            destination = root/'vendor'
            with patch.object(wheels, 'WHEELS', [expected]), \
                 patch.object(wheels.zipfile, 'ZipFile', side_effect=replace_cache_before_archive_read):
                report = wheels.extract(cache, destination)
            self.assertTrue(replaced)
            self.assertNotEqual(wheels.sha(path), expected['sha256'])
            self.assertEqual((destination/'fixture.py').read_text(), 'approved bytes\n')
            self.assertFalse((root/'escaped-canary').exists())
            self.assertEqual(report[0]['sha256'], expected['sha256'])

    @unittest.skipUnless(platform.system() == 'Darwin' and shutil.which('sandbox-exec'), 'macOS native sandbox required')
    def test_failed_probe_cannot_run_a_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/'consumer'
            with patch.object(trials, '_run', return_value={'exit_status': 3, 'timed_out': False}) as run:
                record = trials.run_trial('output-helper', dest, True)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(record['status'], 'blocked')
            self.assertFalse(record['isolation']['verified'])
            self.assertFalse((dest/'recipe.py').exists())

    @unittest.skipUnless(platform.system() == 'Darwin' and shutil.which('sandbox-exec'), 'macOS native sandbox required')
    def test_real_native_boundary_and_both_trusted_recipes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for recipe in ['output-helper', 'tdd-consumer']:
                record = trials.run_trial(recipe, Path(tmp)/recipe, True)
                self.assertEqual(record['status'], 'passed', record)
                self.assertEqual(record['isolation']['checks'], {
                    'outside_read_denied': True, 'outside_write_denied': True,
                    'personal_home_denied': True, 'network_denied': True})
                self.assertTrue(record['isolation']['verified'])
                self.assertEqual([item['exit_status'] for item in record['commands']], [0, 0])
                self.assertTrue(Path(record['destination'], 'trial.json').is_file())
                if recipe == 'output-helper':
                    result = record['result']
                    self.assertEqual(result['short_failed_log']['exit_status'], 7)
                    self.assertEqual(result['long_filtered_view']['exit_status'], 9)
                    self.assertEqual(result['labeled_tail']['view']['evidence'][-1]['line'], 201)
                    self.assertIn('required id absent', str(result['recovered_cause']))
                else:
                    self.assertNotEqual(record['result']['red']['exit_status'], 0)
                    self.assertEqual(record['result']['green']['exit_status'], 0)


if __name__ == '__main__':
    unittest.main()
