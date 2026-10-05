import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import context_ai as c

class Loadouts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.project=Path(self.tmp.name).resolve()
        subprocess.run(['git','init','-q',str(self.project)],check=True)
        (self.project/'AGENTS.md').write_text('User instructions\n')
    def tearDown(self):self.tmp.cleanup()
    def test_every_advertised_loadout_materializes_verifies_and_undoes(self):
        self.assertEqual(len(c.catalogue()),8)
        for id in c.catalogue():
            with self.subTest(id=id):
                lock,files=c.resolve([id],self.project,'codex')
                self.assertTrue(lock['checks']);self.assertTrue(lock['stages'])
                c.apply(self.project,lock,files);c.verify(self.project)
                c.apply(self.project,lock,files)
                self.assertTrue(c.undo(self.project)['undone'])
                self.assertEqual((self.project/'AGENTS.md').read_text(),'User instructions\n')
    def test_plan_is_read_only_and_refresh_preserves_active_lock(self):
        before=list(self.project.rglob('*'))
        run=subprocess.run([sys.executable,str(ROOT/'scripts/context_ai.py'),'plan','standard','react-web','--project',str(self.project),'--brand','expressive'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(list(self.project.rglob('*')),before)
        lock,files=c.resolve(['standard','react-web'],self.project,'codex',{'brand':'expressive'})
        c.apply(self.project,lock,files);pin=(self.project/'.context-ai/lock.json').read_bytes()
        run=subprocess.run([sys.executable,str(ROOT/'scripts/context_ai.py'),'refresh','--project',str(self.project)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(run.stdout)['resolution']['options']['brand'],'expressive')
        self.assertEqual(pin,(self.project/'.context-ai/lock.json').read_bytes())
    def test_plan_discloses_owned_files_removed_by_selection_change(self):
        lock,files=c.resolve(['react-web'],self.project,'codex')
        c.apply(self.project,lock,files)
        old_owned=set(c.installed(self.project)['owned'])
        before=(self.project/'.context-ai/lock.json').read_bytes()
        command=[sys.executable,str(ROOT/'scripts/context_ai.py'),'plan','service-api',
                 '--project',str(self.project)]
        run=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        proposed=json.loads(run.stdout)
        self.assertEqual(proposed['removals'],sorted(old_owned-set(proposed['writes'])))
        self.assertIn('.agents/skills/context-react-review/SKILL.md',proposed['removals'])
        self.assertEqual(before,(self.project/'.context-ai/lock.json').read_bytes())
        next_lock,next_files=c.resolve(['service-api'],self.project,'codex')
        c.apply(self.project,next_lock,next_files)
        self.assertFalse(any((self.project/name).exists() for name in proposed['removals']))
        c.verify(self.project)
    def test_composition_deduplicates_and_non_ui_keeps_design_out(self):
        lock,files=c.resolve(['standard','context-authoring','research-evidence','standard'],self.project,'codex')
        for modules in lock['stages'].values():self.assertEqual(len(modules),len(set(modules)))
        self.assertFalse(any(p.startswith('sourced/') for p in files))
        self.assertNotIn('context-web-design',lock['skills'])
    def test_cycle_and_conflicting_options(self):
        loads=c.catalogue();a=copy.deepcopy(loads['standard']);a['compose']=['standard'];loads['standard']=a
        with patch.object(c,'catalogue',return_value=loads):
            with self.assertRaisesRegex(c.Invalid,'cycle'):c.resolve(['standard'],self.project,'codex')
        loads=c.catalogue();loads['react-web']['options']={'brand':'expressive'}
        with patch.object(c,'catalogue',return_value=loads):
            with self.assertRaisesRegex(c.Invalid,'conflicting'):c.resolve(['react-web'],self.project,'codex')
    def test_missing_required_optional_and_provider(self):
        original=shutil.which
        with patch.object(c.shutil,'which',side_effect=lambda x:None if x=='playwright' else original(x)):
            lock,_=c.resolve(['web-experience'],self.project,'codex')
            self.assertFalse(lock['capabilities']['browser']['available'])
        with patch.object(c.shutil,'which',return_value=None):
            with self.assertRaisesRegex(c.Invalid,'required'):c.resolve(['standard'],self.project,'codex')
        with self.assertRaisesRegex(c.Invalid,'adapter'):c.resolve(['standard'],self.project,'unknown')
    def test_conflicts_are_preflighted_before_writes(self):
        lock,files=c.resolve(['standard'],self.project,'codex')
        target=self.project/'.agents/skills/context-loadout/SKILL.md';target.parent.mkdir(parents=True);target.write_text('User skill')
        with self.assertRaisesRegex(c.Invalid,'conflict'):c.apply(self.project,lock,files)
        self.assertFalse((self.project/'.context-ai/lock.json').exists());self.assertEqual(target.read_text(),'User skill')
    def test_root_and_resource_symlinks_and_forged_owned_paths(self):
        lock,files=c.resolve(['standard'],self.project,'codex')
        (self.project/'.context-ai').symlink_to('/tmp')
        with self.assertRaisesRegex(c.Invalid,'symlink'):c.apply(self.project,lock,files)
        (self.project/'.context-ai').unlink();c.apply(self.project,lock,files)
        p=self.project/'.context-ai/lock.json';state=json.loads(p.read_text());state['owned']['../../other']='0'*64;p.write_bytes(c.encoded(state))
        with self.assertRaisesRegex(c.Invalid,'unapproved'):c.undo(self.project)
    def test_user_changes_outside_router_survive_reapply_and_undo(self):
        lock,files=c.resolve(['standard'],self.project,'codex');c.apply(self.project,lock,files)
        p=self.project/'AGENTS.md';p.write_text('New user preface\n'+p.read_text()+'New user footer\n')
        c.apply(self.project,lock,files);c.undo(self.project)
        self.assertEqual(p.read_text(),'New user preface\nUser instructions\nNew user footer\n')
    def test_router_edit_and_source_pin_tampering_fail(self):
        lock,files=c.resolve(['standard'],self.project,'codex');c.apply(self.project,lock,files)
        p=self.project/'AGENTS.md';p.write_text(p.read_text().replace('Current stage','current stage').replace('Project instructions','Edited instructions'))
        with self.assertRaisesRegex(c.Invalid,'edited'):c.apply(self.project,lock,files)
        statepath=self.project/'.context-ai/lock.json';state=json.loads(statepath.read_text());state['resolution']['source_tree_sha256']='0'*64;statepath.write_bytes(c.encoded(state))
        with self.assertRaisesRegex(c.Invalid,'digest'):c.verify(self.project)
    def test_decision_successor_and_old_lock_replay(self):
        self.assertEqual(c.current_decisions()['D-007']['revision'],2)
        lock,files=c.resolve(['web-experience'],self.project,'codex');original=copy.deepcopy(lock)
        c.apply(self.project,lock,files)
        with patch.object(c,'current_decisions',return_value={}):c.verify(self.project)
        self.assertEqual(json.loads((self.project/'.context-ai/lock.json').read_text())['resolution'],original)

    def test_undo_restores_file_without_original_newline(self):
        (self.project/'AGENTS.md').write_text('No newline')
        lock,files=c.resolve(['standard'],self.project,'codex')
        c.apply(self.project,lock,files);c.undo(self.project)
        self.assertEqual((self.project/'AGENTS.md').read_bytes(),b'No newline')

    def test_explicit_refresh_and_retry_after_undo_conflict(self):
        lock,files=c.resolve(['standard'],self.project,'codex');c.apply(self.project,lock,files)
        run=subprocess.run([sys.executable,str(ROOT/'scripts/context_ai.py'),'refresh','standard','context-authoring','--project',str(self.project)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        p=self.project/'.context-ai/resources/core/testing.md';original=p.read_bytes();p.write_text('User edit')
        self.assertFalse(c.undo(self.project)['undone'])
        self.assertEqual(p.read_text(),'User edit')
        p.write_bytes(original)
        self.assertTrue(c.undo(self.project)['undone'])
        c.apply(self.project,lock,files);c.verify(self.project)

    def test_project_brand_intent_and_primary_procedure_change_actual_closure(self):
        intent='Paper maps, warm ink, restrained motion; preserve the existing wordmark'
        guided,guided_files=c.resolve(['web-experience'],self.project,'codex',{'brand':intent,'design_procedure':'guided'})
        light,light_files=c.resolve(['web-experience'],self.project,'codex',{'brand':intent,'design_procedure':'lightweight'})
        self.assertEqual(light['options']['brand'],intent)
        self.assertIn('procedures/web-design-lightweight.md',light_files)
        self.assertIn('sourced/anthropic/design/LICENSE.txt',light_files)
        self.assertNotIn('sourced/impeccable/design/reference/new-work.md',light_files)
        self.assertIn('sourced/impeccable/design/reference/new-work.md',guided_files)
        self.assertLess(len(light_files),len(guided_files))
        c.apply(self.project,light,light_files);c.verify(self.project)
        self.assertTrue(c.undo(self.project)['undone'])
        with self.assertRaisesRegex(c.Invalid,'does not apply'):c.resolve(['service-api'],self.project,'codex',{'brand':intent})

    def test_refresh_new_selection_drops_inapplicable_inherited_options(self):
        lock,files=c.resolve(['web-experience'],self.project,'codex',{'brand':'Project intent','design_procedure':'lightweight'})
        c.apply(self.project,lock,files);before=(self.project/'.context-ai/lock.json').read_bytes()
        command=[sys.executable,str(ROOT/'scripts/context_ai.py'),'refresh','service-api','--project',str(self.project)]
        run=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(run.stdout)['resolution']['options'],{})
        self.assertEqual(before,(self.project/'.context-ai/lock.json').read_bytes())
        rejected=subprocess.run(command+['--brand','Explicit invalid override'],capture_output=True,text=True)
        self.assertNotEqual(rejected.returncode,0)
        self.assertIn('does not apply',rejected.stderr)
