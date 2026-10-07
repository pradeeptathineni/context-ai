import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import context_ai as c

def cli(*args):
    return subprocess.run([sys.executable,str(ROOT/'scripts/context_ai.py'),*args],capture_output=True,text=True)

class ClaudeAndBothHosts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.project=Path(self.tmp.name).resolve()/'consumer'
        self.project.mkdir()
        subprocess.run(['git','init','-q',str(self.project)],check=True)
        (self.project/'AGENTS.md').write_text('User instructions\n')
    def tearDown(self):
        for path in self.project.rglob('*'):
            if not path.is_symlink():os.chmod(path,stat.S_IRWXU)
        os.chmod(self.project,stat.S_IRWXU)
        self.tmp.cleanup()

    def test_every_loadout_delivers_to_claude_and_both_and_undoes(self):
        for provider in ('claude','both'):
            for id in c.catalogue():
                with self.subTest(provider=provider,id=id):
                    lock,files=c.resolve([id],self.project,provider)
                    c.apply(self.project,lock,files);c.verify(self.project)
                    for skill in lock['skills']:
                        self.assertTrue((self.project/'.claude/skills'/skill/'SKILL.md').is_file())
                        self.assertEqual((self.project/'.agents/skills'/skill/'SKILL.md').is_file(),provider=='both')
                    self.assertIn('providers/anthropic/claude-code.md',files)
                    c.apply(self.project,lock,files)
                    self.assertTrue(c.undo(self.project)['undone'])
                    self.assertEqual((self.project/'AGENTS.md').read_text(),'User instructions\n')
                    self.assertFalse((self.project/'CLAUDE.md').exists())

    def test_apply_preserves_user_file_modes_and_uses_umask_for_new_files(self):
        agents=self.project/'AGENTS.md';os.chmod(agents,0o644)
        (self.project/'CLAUDE.md').write_text('Rules\n');os.chmod(self.project/'CLAUDE.md',0o640)
        lock,files=c.resolve(['essentials'],self.project,'both');c.apply(self.project,lock,files)
        self.assertEqual(agents.stat().st_mode&0o777,0o644)
        self.assertEqual((self.project/'CLAUDE.md').stat().st_mode&0o777,0o640)
        umask=os.umask(0);os.umask(umask)
        self.assertEqual((self.project/'.claude/skills/context-tdd/SKILL.md').stat().st_mode&0o777,0o666&~umask)
        c.undo(self.project)
        self.assertEqual(agents.stat().st_mode&0o777,0o644)

    def test_source_checkout_under_codex_worktree_still_delivers(self):
        source=Path(self.tmp.name)/'.codex/worktrees/x/context-ai'
        archive=subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z'],text=True).split('\0')
        for name in filter(None,archive):
            target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
            if (ROOT/name).is_file():shutil.copy2(ROOT/name,target)
        run=subprocess.run([sys.executable,str(source/'scripts/context_ai.py'),'plan','essentials','--project',str(self.project),'--provider','both'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        with self.assertRaisesRegex(c.Invalid,'untrusted instruction activation'):c.resource_path(c.ROOT,'.codex/core.md')
        with self.assertRaisesRegex(c.Invalid,'untrusted instruction activation'):c.resource_path(c.ROOT,'core/AGENTS.md')

    def test_router_points_to_single_canonical_copy(self):
        lock,files=c.resolve(['essentials'],self.project,'both');c.apply(self.project,lock,files)
        codex=(self.project/'.agents/skills/context-tdd/SKILL.md').read_text()
        claude=(self.project/'.claude/skills/context-tdd/SKILL.md').read_text()
        self.assertEqual(codex,claude)
        self.assertIn('../../../.context-ai/resources/procedures/tdd.md',claude)
        self.assertTrue((self.project/'.claude/skills/context-tdd/../../../.context-ai/resources/procedures/tdd.md').resolve().is_file())
        self.assertEqual(len(list(self.project.rglob('tdd.md'))),1)

    def test_native_agents_read_writes_no_claude_md(self):
        lock,files=c.resolve(['essentials'],self.project,'claude')
        preview=c.plan(self.project,lock,files)
        self.assertEqual(preview['host_routing']['claude']['mode'],'native-agents')
        self.assertNotIn('CLAUDE.md',preview['writes'])

    def test_claude_md_importing_agents_is_left_alone(self):
        (self.project/'CLAUDE.md').write_text('Team notes\n@AGENTS.md\n')
        lock,files=c.resolve(['essentials'],self.project,'claude');c.apply(self.project,lock,files)
        self.assertEqual((self.project/'CLAUDE.md').read_text(),'Team notes\n@AGENTS.md\n')
        self.assertEqual(c.verify(self.project)['host_routing']['claude']['mode'],'imports-agents')

    def test_shadowing_claude_md_gets_owned_block_preserving_user_edits(self):
        (self.project/'CLAUDE.md').write_text('Claude-only user rules\n')
        lock,files=c.resolve(['essentials'],self.project,'claude');c.apply(self.project,lock,files)
        text=(self.project/'CLAUDE.md').read_text()
        self.assertTrue(text.startswith('Claude-only user rules\n'+c.BEGIN))
        self.assertIn('.context-ai/resources/procedures/tdd.md',text)
        c.apply(self.project,lock,files);c.verify(self.project)
        p=self.project/'CLAUDE.md';p.write_text('Preface\n'+p.read_text()+'Footer\n')
        c.apply(self.project,lock,files)
        self.assertTrue(c.undo(self.project)['undone'])
        self.assertEqual(p.read_text(),'Preface\nClaude-only user rules\nFooter\n')

    def test_edited_claude_block_is_preserved_on_undo_and_refused_on_apply(self):
        (self.project/'CLAUDE.md').write_text('Rules\n')
        lock,files=c.resolve(['essentials'],self.project,'claude');c.apply(self.project,lock,files)
        p=self.project/'CLAUDE.md';p.write_text(p.read_text().replace('Load only','Edited: load only'))
        with self.assertRaisesRegex(c.Invalid,'edited managed CLAUDE.md block'):c.apply(self.project,lock,files)
        result=c.undo(self.project)
        self.assertFalse(result['undone']);self.assertIn('CLAUDE.md',result['preserved_conflicts'])
        self.assertIn('Edited: load only',p.read_text())

    def test_new_shadowing_claude_md_is_detected_and_refresh_routes_it(self):
        lock,files=c.resolve(['essentials'],self.project,'claude');c.apply(self.project,lock,files)
        (self.project/'CLAUDE.md').write_text('Added later\n')
        with self.assertRaisesRegex(c.Invalid,'shadows'):c.verify(self.project)
        run=cli('refresh','--project',str(self.project))
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(run.stdout)['resolution']['provider'],'claude')
        self.assertIn('CLAUDE.md',json.loads(run.stdout)['writes'])
        c.apply(self.project,lock,files);c.verify(self.project)
        self.assertTrue(c.undo(self.project)['undone'])
        self.assertEqual((self.project/'CLAUDE.md').read_text(),'Added later\n')

    def test_ancestor_claude_md_routes_through_project_block(self):
        (self.project.parent/'CLAUDE.md').write_text('Parent rules\n')
        lock,files=c.resolve(['essentials'],self.project,'claude');c.apply(self.project,lock,files)
        self.assertIn(c.BEGIN,(self.project/'CLAUDE.md').read_text())
        self.assertEqual((self.project.parent/'CLAUDE.md').read_text(),'Parent rules\n')
        self.assertTrue(c.undo(self.project)['undone'])
        self.assertFalse((self.project/'CLAUDE.md').exists())

    def test_duplicate_native_skill_name_and_concern_owner_are_refused(self):
        skill=self.project/'.claude/skills/my-review/SKILL.md';skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: context-review\ndescription: user copy\n---\nUser text\n')
        lock,files=c.resolve(['essentials'],self.project,'claude')
        self.assertTrue(any('skill name conflict' in x for x in c.plan(self.project,lock,files)['conflicts']))
        with self.assertRaisesRegex(c.Invalid,'skill name conflict'):c.apply(self.project,lock,files)
        skill.write_text('---\nname: tdd\ndescription: user TDD\n---\nUser text\n')
        preview=c.plan(self.project,lock,files)
        self.assertEqual(preview['duplicate_concern_owners'][0]['concern'],'test-first-loop')
        with self.assertRaisesRegex(c.Invalid,'duplicate concern owner: test-first-loop'):c.apply(self.project,lock,files)
        self.assertFalse((self.project/'.context-ai').exists())
        self.assertEqual(skill.read_text(),'---\nname: tdd\ndescription: user TDD\n---\nUser text\n')
        # Codex-only delivery ignores the Claude folder name collision but not the concern overlap.
        lock,files=c.resolve(['essentials'],self.project,'codex')
        self.assertTrue(c.plan(self.project,lock,files)['duplicate_concern_owners'])

    def test_native_plugins_are_inventoried_and_never_written(self):
        settings=self.project/'.claude/settings.json';settings.parent.mkdir()
        settings.write_text(json.dumps({'enabledPlugins':{'superpowers@market':True,'off@market':False}}))
        (self.project/'.codex').mkdir();(self.project/'.codex/config.toml').write_text('[plugins."code-review@openai"]\nenabled = true\n')
        lock,files=c.resolve(['essentials'],self.project,'both')
        preview=c.plan(self.project,lock,files)
        self.assertEqual({p['plugin'] for p in preview['native_managed']['plugins']},{'superpowers@market','code-review@openai'})
        before=settings.read_bytes();c.apply(self.project,lock,files)
        self.assertEqual(settings.read_bytes(),before)
        self.assertFalse(any(name.startswith(('.claude/settings','.codex/')) for name in preview['writes']))

    def test_plan_previews_additions_replacements_removals_pins_and_runs_no_code(self):
        lock,files=c.resolve(['essentials'],self.project,'both')
        preview=c.plan(self.project,lock,files)
        self.assertIn('.claude/skills/context-tdd/SKILL.md',preview['additions'])
        self.assertEqual(preview['removals'],[]);self.assertFalse(preview['runs_code']['apply'])
        pins={p['id']:p for p in preview['upstream_pins']}
        self.assertEqual(pins['mattpocock']['revision'],'f3fc5632f401156837ee3872f14fe33ccf1024ea')
        self.assertEqual(pins['mattpocock']['license'],'MIT')
        self.assertEqual(preview['prerequisites']['context-tdd']['requirement'],'required')
        c.apply(self.project,lock,files)
        nxt,nfiles=c.resolve(['standard'],self.project,'claude')
        preview=c.plan(self.project,nxt,nfiles)
        self.assertIn('.agents/skills/context-tdd/SKILL.md',preview['removals'])
        self.assertIn('.claude/skills/context-diagnose/SKILL.md',preview['additions'])
        self.assertTrue(set(preview['replacements'])<=set(c.installed(self.project)['owned']))
        c.apply(self.project,nxt,nfiles);c.verify(self.project)
        self.assertFalse((self.project/'.agents/skills/context-tdd/SKILL.md').exists())

    def test_unsupported_host_and_lock_provider_mismatch(self):
        with self.assertRaisesRegex(c.Invalid,'supported adapters'):c.resolve(['essentials'],self.project,'gemini')
        self.assertNotEqual(cli('plan','essentials','--project',str(self.project),'--provider','cursor').returncode,0)

    def test_moved_checkout_with_claude_routing(self):
        (self.project/'CLAUDE.md').write_text('Rules\n')
        lock,files=c.resolve(['essentials'],self.project,'claude');c.apply(self.project,lock,files)
        exported=cli('export','--project',str(self.project));self.assertEqual(exported.returncode,0,exported.stderr)
        moved=Path(self.tmp.name)/'moved';shutil.copytree(self.project,moved)
        with self.assertRaisesRegex(c.Invalid,'another project'):c.verify(moved.resolve())
        self.assertTrue(c.rebind(moved.resolve())['rebound'])
        self.assertTrue(c.undo(moved.resolve())['undone'])
        self.assertEqual((moved/'CLAUDE.md').read_text(),'Rules\n')
        pin=Path(self.tmp.name)/'pin.json';pin.write_text(exported.stdout)
        fresh=Path(self.tmp.name)/'fresh';fresh.mkdir();(fresh/'CLAUDE.md').write_text('Other rules\n')
        run=cli('apply','--lock',str(pin),'--project',str(fresh))
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertTrue((fresh/'.claude/skills/context-tdd/SKILL.md').is_file())

    def test_interrupted_write_recovers_claude_block(self):
        (self.project/'CLAUDE.md').write_text('Rules\n')
        lock,files=c.resolve(['essentials'],self.project,'claude')
        original=c.atomic;calls=[]
        def failing(path,data):
            calls.append(path)
            if path.name=='CLAUDE.md':raise OSError('disk full')
            return original(path,data)
        with patch.object(c,'atomic',side_effect=failing):
            with self.assertRaises(OSError):c.apply(self.project,lock,files)
        self.assertEqual((self.project/'CLAUDE.md').read_text(),'Rules\n')
        self.assertFalse((self.project/'.context-ai/pending.json').exists())
        self.assertFalse((self.project/'.claude/skills').exists() and any((self.project/'.claude/skills').rglob('SKILL.md')))

    def test_read_only_project_fails_without_partial_ownership(self):
        lock,files=c.resolve(['essentials'],self.project,'claude')
        os.chmod(self.project,stat.S_IRUSR|stat.S_IXUSR)
        try:
            with self.assertRaises((OSError,c.Invalid)):c.apply(self.project,lock,files)
        finally:
            os.chmod(self.project,stat.S_IRWXU)
        self.assertFalse((self.project/'.context-ai/lock.json').exists())

    def test_symlinked_claude_skills_and_traversal_are_refused(self):
        outside=Path(self.tmp.name)/'outside';outside.mkdir()
        (self.project/'.claude').mkdir();(self.project/'.claude/skills').symlink_to(outside)
        lock,files=c.resolve(['essentials'],self.project,'claude')
        with self.assertRaisesRegex(c.Invalid,'symlink'):c.apply(self.project,lock,files)
        self.assertEqual(list(outside.iterdir()),[])
        with self.assertRaisesRegex(c.Invalid,'unapproved'):c.transaction_path(self.project,'.claude/settings.json')
        with self.assertRaisesRegex(c.Invalid,'unsafe'):c.inside(self.project,'.claude/../../x')

    def test_import_detection_follows_claude_resolution_rules(self):
        cases=[('CLAUDE.md','Examples:\n```md\n@AGENTS.md\n```\n','managed-block'),
               ('CLAUDE.md','Mention `@AGENTS.md` literally\n','managed-block'),
               ('.claude/CLAUDE.md','@AGENTS.md\n','managed-block'),
               ('.claude/CLAUDE.md','@../AGENTS.md\n','imports-agents'),
               ('CLAUDE.md','See @./AGENTS.md for shared rules\n','imports-agents')]
        for name,text,mode in cases:
            with self.subTest(name=name,text=text):
                for leftover in ('CLAUDE.md','.claude/CLAUDE.md'):
                    if (self.project/leftover).exists():(self.project/leftover).unlink()
                path=self.project/name;path.parent.mkdir(exist_ok=True);path.write_text(text)
                lock,files=c.resolve(['essentials'],self.project,'claude')
                self.assertEqual(c.plan(self.project,lock,files)['host_routing']['claude']['mode'],mode)

    def test_symlinked_claude_md_to_agents_counts_as_import(self):
        (self.project/'CLAUDE.md').symlink_to('AGENTS.md')
        lock,files=c.resolve(['essentials'],self.project,'claude')
        self.assertEqual(c.plan(self.project,lock,files)['host_routing']['claude']['mode'],'imports-agents')
        c.apply(self.project,lock,files);c.verify(self.project)
        self.assertTrue((self.project/'CLAUDE.md').is_symlink())
        self.assertTrue(c.undo(self.project)['undone'])

if __name__=='__main__':
    unittest.main()
