import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('context_ai',ROOT/'scripts/context_ai.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class Bootstrap(unittest.TestCase):
    def test_composition_and_owned_replay(self):
        with tempfile.TemporaryDirectory() as td:
            project=Path(td).resolve()
            subprocess.run(['git','init','-q',str(project)],check=True)
            (project/'AGENTS.md').write_text('User instructions\n')
            lock,files=c.resolve(['standard','context-authoring','standard'],project,'codex')
            self.assertEqual(lock['loadouts'],['standard','context-authoring'])
            self.assertNotIn('design',lock['stages'])
            c.apply(project,lock,files)
            first=(project/'.context-ai/lock.json').read_bytes()
            c.apply(project,lock,files)
            self.assertEqual(first,(project/'.context-ai/lock.json').read_bytes())
            c.verify(project)
            c.undo(project)
            self.assertEqual((project/'AGENTS.md').read_text(),'User instructions\n')
    def test_edited_owned_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            project=Path(td).resolve()
            lock,files=c.resolve(['research-evidence'],project,'codex')
            c.apply(project,lock,files)
            p=project/'.context-ai/resources/core/research.md'
            p.write_text('User revision')
            with self.assertRaises(c.Invalid):c.apply(project,lock,files)
            result=c.undo(project)
            self.assertIn('.context-ai/resources/core/research.md',result['preserved_conflicts'])
            self.assertEqual(p.read_text(),'User revision')
    def test_yaml_and_path_reject_unsafe_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve()
            for content in ['x: 1\nx: 2\n','x: !!python/object:bad {}','x: &a [1]\ny: *a']:
                p=root/'bad.yaml';p.write_text(content)
                with self.assertRaises(Exception):c.read_yaml(p)
            with self.assertRaises(c.Invalid):c.inside(root,'../escape')
            (root/'link').symlink_to('/tmp')
            with self.assertRaises(c.Invalid):c.inside(root,'link/escape')

if __name__=='__main__':unittest.main()

class ModelRoutes(unittest.TestCase):
    def test_retired_and_invalid_effort_fail_validator(self):
        import shutil, yaml
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td)/'repo'
            shutil.copytree(ROOT,repo,ignore=shutil.ignore_patterns('.git','.context-ai','.venv','__pycache__','node_modules'))
            path=repo/'models/routing.yaml'
            original=yaml.safe_load(path.read_text())
            original['models']['balanced']['model']='gpt-5.3-codex-spark'
            path.write_text(yaml.safe_dump(original,sort_keys=False))
            run=subprocess.run(['ruby',str(repo/'scripts/validate.rb')],capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0)
            self.assertIn('retired model',run.stderr)
            original['models']['balanced']['model']='gpt-6.1-sol'
            original['routes'][-1]['select']['reasoning']='imaginary'
            path.write_text(yaml.safe_dump(original,sort_keys=False))
            run=subprocess.run(['ruby',str(repo/'scripts/validate.rb')],capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0)
            self.assertIn('unsupported balanced reasoning',run.stderr)

class ReleaseAuthority(unittest.TestCase):
    def test_stable_tag_ref_fails_even_with_pre_one_metadata(self):
        import os
        run=subprocess.run(['ruby',str(ROOT/'scripts/validate.rb')],capture_output=True,text=True,env={**os.environ,'GITHUB_REF':'refs/tags/v1.2.3'})
        self.assertNotEqual(run.returncode,0)
        self.assertIn('stable release tags',run.stderr)
