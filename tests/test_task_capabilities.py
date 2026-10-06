"""Task options, static local discovery and honest readiness boundaries."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import context_ai as c

class TaskCapabilities(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.project=Path(self.tmp.name).resolve()
    def tearDown(self):self.tmp.cleanup()
    def manifest(self,data,root=None):
        root=root or self.project
        (root/'package.json').write_text(json.dumps(data))
    def package(self,root=None):
        root=root or self.project
        p=root/'node_modules/@playwright/test';p.mkdir(parents=True)
        (p/'package.json').write_text(json.dumps({'name':'@playwright/test','version':'1.58.2','bin':{'playwright':'cli.js'}}))
        (p/'cli.js').write_text("require('node:fs').writeFileSync('EXECUTED', 'unsafe');\n")
        return p
    def browser(self):return c.discover_command(c.capability_registry()['capabilities']['browser'],self.project)
    def test_new_option_is_data_and_selected_closure_agrees(self):
        document=c.capability_registry();loads=c.catalogue()
        document['options']['investigation']={'description':'Meaningful failure diagnosis choice','default':'focused','alternatives':{'focused':{'description':'Use diagnosis','aliases':{'context-review':'context-diagnose'}}}}
        loads['standard']['options']={'investigation':'focused'}
        with patch.object(c,'capability_registry',return_value=document),patch.object(c,'catalogue',return_value=loads):
            explained=c.explain(['standard']);lock,files=c.resolve(['standard'],self.project,'codex')
        self.assertEqual(explained['capabilities']['context-review']['path'],'procedures/diagnose.md')
        self.assertEqual(explained['options'],lock['options'])
        self.assertIn('procedures/diagnose.md',files)
        self.assertNotIn('procedures/review-fresh.md',files)
    def test_direct_fresh_and_incompatible_selection(self):
        direct,files=c.resolve(['standard'],self.project,'codex')
        fresh,other=c.resolve(['standard'],self.project,'codex',{'review_mode':'fresh'})
        self.assertNotIn('procedures/review-fresh.md',files)
        self.assertIn('procedures/review-fresh.md',other)
        self.assertIn('overlays/orchestration.md',other)
        self.assertEqual(c.explain(['standard'],fresh['options'])['capabilities']['context-review'],fresh['capabilities']['context-review']['definition'])
        document=c.capability_registry()
        document['options']['review_mode']['alternatives']['fresh']['incompatible']=[{'option':'design_procedure','value':'lightweight'}]
        with patch.object(c,'capability_registry',return_value=document),self.assertRaisesRegex(c.Invalid,'incompatible'):
            c.resolve(['standard','web-experience'],self.project,'codex',{'review_mode':'fresh','design_procedure':'lightweight'})
        with self.assertRaisesRegex(c.Invalid,'unsupported option'):
            c.resolve(['standard'],self.project,'codex',{'review_mode':'unknown'})
    def test_declared_installed_and_exercised_are_separate_without_execution(self):
        self.manifest({'packageManager':'pnpm@10.0.0','devDependencies':{'@playwright/test':'1.58.2'},'scripts':{'test':'touch EXECUTED'}})
        (self.project/'playwright.config.js').write_text("require('node:fs').writeFileSync('EXECUTED', 'config');")
        with patch.object(c.shutil,'which',return_value=None),patch.object(c.subprocess,'run',side_effect=AssertionError('discovery executed')):
            absent=self.browser()
            self.assertTrue(absent['declared']);self.assertIsNone(absent['location']);self.assertFalse(absent['installed'])
            self.package();found=self.browser()
        self.assertEqual(found['source'],'installed project package')
        self.assertEqual(found['installed'][0]['version'],'1.58.2')
        self.assertFalse(found['exercised']);self.assertIn('Browser binaries',found['uncertainty'])
        self.assertFalse((self.project/'EXECUTED').exists())
    def test_workspace_hoist_and_pnpm_symlink_stay_in_declared_owner(self):
        member=self.project/'packages/ui';member.mkdir(parents=True)
        self.manifest({'workspaces':['packages/*'],'packageManager':'yarn@4.0.0'})
        self.manifest({'devDependencies':{'@playwright/test':'1.58.2'}},member)
        package=self.package()
        store=self.project/'node_modules/.pnpm/test';store.parent.mkdir(parents=True);package.rename(store);package.symlink_to(store,target_is_directory=True)
        report=c.discover_command(c.capability_registry()['capabilities']['browser'],member)
        self.assertEqual(report['workspace'],str(self.project))
        self.assertEqual(report['package_manager'],'yarn@4.0.0')
        self.assertEqual(report['source'],'installed project package')
        package.unlink();package.symlink_to('/tmp',target_is_directory=True)
        with self.assertRaisesRegex(c.Invalid,'escapes project/workspace'):c.discover_command(c.capability_registry()['capabilities']['browser'],member)
    def test_python_project_environment_is_not_context_interpreter(self):
        (self.project/'pyproject.toml').write_text('[project]\nname="sample"\n')
        item=c.capability_registry()['capabilities']['python-runtime']
        report=c.discover_command(item,self.project)
        self.assertIsNone(report['location']);self.assertIn('not substituted',report['uncertainty'])
        env=self.project/'.venv';(env/'bin').mkdir(parents=True);(env/'pyvenv.cfg').write_text('managed\n')
        (env/'bin/python').symlink_to(sys.executable)
        report=c.discover_command(item,self.project)
        self.assertEqual(report['source'],'project .venv');self.assertEqual(report['location'],str(env/'bin/python'))
        self.assertFalse(report['exercised'])
        self.assertTrue(c.probe_command('python3',report['location']).startswith('Python '))
    def test_local_locations_do_not_enter_portable_pin_and_skill_conflicts_refuse(self):
        self.manifest({'devDependencies':{'@playwright/test':'1.58.2'}});self.package()
        lock,files=c.resolve(['web-experience'],self.project,'codex')
        self.assertTrue(lock['capabilities']['browser']['available'])
        self.assertNotIn(str(self.project),json.dumps(lock))
        existing=self.project/'.agents/skills/other';existing.mkdir(parents=True)
        existing.joinpath('SKILL.md').write_text('---\nname: context-loadout\ndescription: User-owned skill\n---\nUser instructions\n')
        with self.assertRaisesRegex(c.Invalid,'skill name conflict'):c.apply(self.project,lock,files)
        self.assertFalse((self.project/'.context-ai/lock.json').exists())
    def test_generic_flags_preserve_legacy_and_refresh_choice(self):
        base=[sys.executable,str(ROOT/'scripts/context_ai.py'),'explain','web-experience']
        a=subprocess.run(base+['--design-procedure','lightweight'],capture_output=True,text=True,check=True)
        b=subprocess.run(base+['--option','design_procedure=lightweight'],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(a.stdout),json.loads(b.stdout))
        conflict=subprocess.run(base+['--design-procedure','guided','--option','design_procedure=lightweight'],capture_output=True,text=True)
        self.assertNotEqual(conflict.returncode,0);self.assertIn('conflicting',conflict.stderr)
        lock,files=c.resolve(['standard'],self.project,'codex',{'review_mode':'fresh'});c.apply(self.project,lock,files)
        command=[sys.executable,str(ROOT/'scripts/context_ai.py'),'refresh','--project',str(self.project)]
        result=subprocess.run(command,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout)['resolution']['options']['review_mode'],'fresh')
    def test_unsafe_or_ambiguous_declarations_do_not_become_commands(self):
        self.manifest({'packageManager':'npm; touch EXECUTED'})
        with self.assertRaisesRegex(c.Invalid,'packageManager'):self.browser()
        self.manifest({});(self.project/'yarn.lock').write_text('');(self.project/'package-lock.json').write_text('{}')
        report=c.discover_command(c.capability_registry()['capabilities']['package-manager'],self.project)
        self.assertIsNone(report['location']);self.assertEqual(report['lockfile_managers'],['npm','yarn'])
        package=self.package();(package/'package.json').write_text(json.dumps({'name':'@playwright/test','bin':{'playwright':'../../../evil.js'}}))
        with self.assertRaisesRegex(c.Invalid,'unsafe local Playwright'):self.browser()
    def test_clean_source_archive_and_selected_router_references(self):
        import io
        import shutil
        import tarfile
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'source'
            shutil.copytree(ROOT,source,ignore=shutil.ignore_patterns('.git','.context-ai','.venv','node_modules','.examples-output','.ruff_cache','__pycache__','.agents'))
            subprocess.run(['git','init','-q',str(source)],check=True)
            subprocess.run(['git','-C',str(source),'add','.'],check=True)
            subprocess.run(['git','-C',str(source),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Isolated source'],check=True)
            data=subprocess.check_output(['git','-C',str(source),'archive','HEAD'])
            exported=root/'archive';exported.mkdir()
            with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                for entry in archive:
                    target=exported/entry.name
                    if entry.isdir():target.mkdir(parents=True,exist_ok=True)
                    elif entry.isfile():
                        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.extractfile(entry).read())
                    else:self.fail('Unexpected archive type')
            consumer=root/'consumer';consumer.mkdir()
            with patch.object(c,'ROOT',exported):
                lock,files=c.resolve(['standard','web-experience'],consumer,'codex',{'review_mode':'fresh','design_procedure':'lightweight'})
                c.apply(consumer,lock,files)
            for skill in lock['skills']:
                router=consumer/'.agents/skills'/skill/'SKILL.md'
                self.assertTrue(router.is_file())
                text=router.read_text()
                link=text.split('[pinned instructions](',1)[1].split(')',1)[0]
                self.assertTrue((router.parent/link).resolve().is_file())
            self.assertIn('procedures/review.md',files)
            self.assertIn('core/review.md',files)
            self.assertIn('sourced/anthropic/design/LICENSE.txt',files)
            self.assertNotIn('sourced/impeccable/design/instruction.md',files)
            self.assertNotIn('.context-ai',files)
    def test_workspace_star_cannot_admit_nested_nonmembers_or_overexclude(self):
        self.manifest({'workspaces':['packages/*'],'packageManager':'pnpm@10.0.0'})
        self.package()
        nested=self.project/'packages/ui/nested';nested.mkdir(parents=True)
        self.manifest({'devDependencies':{'@playwright/test':'1.58.2'}},nested)
        report=c.discover_command(c.capability_registry()['capabilities']['browser'],nested)
        self.assertEqual(report['workspace'],str(nested))
        self.assertEqual(report['installed'],[])
        self.manifest({'workspaces':['packages/**','!packages/*'],'packageManager':'pnpm@10.0.0'})
        report=c.discover_command(c.capability_registry()['capabilities']['browser'],nested)
        self.assertEqual(report['workspace'],str(self.project))
        self.assertTrue(report['installed'])
        self.manifest({'workspaces':['packages/**','!packages/**']})
        self.assertEqual(c.node_project(nested)[1],nested)
        self.manifest({'workspaces':['packages/{ui,api}']})
        with self.assertRaisesRegex(c.Invalid,'unsupported workspace glob'):c.node_project(nested)
