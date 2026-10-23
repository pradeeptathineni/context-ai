"""Observed first-use and explanation/verification boundary regressions."""
import copy
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


class ConsumerPath(unittest.TestCase):
    def principle_spec(self, name='qualified', intent='inspect', profile='verification'):
        folder=ROOT/'tests/fixtures/principles-export'/name
        path=folder/(profile+'.json')
        return {'export':str(path),'sha256':c.digest(path.read_bytes()),
                'revision':json.loads(path.read_text())['source_revision'],'source_root':str(folder/'source'),'intent':intent}

    def test_native_principles_selection_survives_preview_apply_reopen_refresh_and_undo(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve()
            original='Keep user é\r\nNo newline'.encode()
            (project/'AGENTS.md').write_bytes(original);(project/'AGENTS.md').chmod(0o600)
            (project/'CLAUDE.md').write_bytes(original);(project/'CLAUDE.md').chmod(0o755)
            spec=self.principle_spec()
            before={p.name:(p.read_bytes(),p.stat().st_mode&0o7777) for p in project.iterdir()}
            preview=c.principles_delivery(project,spec,provider='both')
            self.assertEqual({p.name:(p.read_bytes(),p.stat().st_mode&0o7777) for p in project.iterdir()},before)
            entries=preview['principles']['entries']
            self.assertEqual([entry['status'] for entry in entries],['active','active','draft'])
            self.assertIn('qualified teacher or coach',preview['principles']['guidance'])
            self.assertIn('superseded',preview['principles']['guidance'])
            self.assertIn('moved',preview['principles']['guidance'])
            with self.assertRaisesRegex(c.Invalid,'unreviewed'):
                c.principles_delivery(project,spec,action='apply',provider='both')
            c.principles_delivery(project,spec,action='apply',provider='both',expected_plan=preview['plan_id'])
            reopened=c.installed(project)['resolution']['principles']
            self.assertEqual(reopened,preview['resolution']['principles'])
            self.assertEqual(c.pinned_files(preview['resolution'])['principles/selected.md'].decode(),preview['principles']['guidance'])
            run=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/context_ai.py'),'verify','--project',str(project)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            refreshed=c.principles_delivery(project,self.principle_spec('withdrawn'),action='refresh',provider='both')
            self.assertIn('source/input changed',refreshed['principles_review_conflict'])
            with self.assertRaisesRegex(c.Invalid,'changed or unreviewed'):
                c.principles_delivery(project,self.principle_spec('withdrawn'),action='apply',provider='both',expected_plan=preview['plan_id'])
            self.assertEqual(c.installed(project)['resolution']['principles'],reopened)
            c.principles_delivery(project,self.principle_spec('withdrawn'),action='apply',provider='both',expected_plan=refreshed['plan_id'])
            foreign=project/'.context-ai/resources/principles/selected.md'
            foreign.write_bytes(b'User changed selected guidance\r\n');foreign.chmod(0o600)
            for name in ('AGENTS.md','CLAUDE.md'):
                path=project/name;path.write_bytes(b'Preface\r\n'+path.read_bytes()+b'Footer\r\n')
            result=c.undo(project)
            self.assertIn('.context-ai/resources/principles/selected.md',result['preserved_conflicts'])
            self.assertEqual(foreign.read_bytes(),b'User changed selected guidance\r\n')
            self.assertEqual(foreign.stat().st_mode&0o7777,0o600)
            for name in ('AGENTS.md','CLAUDE.md'):
                self.assertEqual((project/name).read_bytes(),b'Preface\r\n'+original+b'Footer\r\n')
                self.assertEqual((project/name).stat().st_mode&0o7777,before[name][1])

    def test_principles_operational_default_and_zero_guidance_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve()
            preview=c.principles_delivery(project,self.principle_spec(intent='operational'))
            self.assertEqual(preview['principles']['selected_ids'],['PRN-000010'])
            self.assertNotIn('PRN-000014 —',preview['principles']['guidance'])
            lock,files=c.resolve([],project,'codex')
            self.assertNotIn('principles',lock)
            self.assertFalse(any(path.startswith('principles/') for path in files))

    def test_principles_minimal_needs_bound_full_and_versions_or_incomplete_blocks_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve()
            spec=self.principle_spec(profile='minimal')
            with self.assertRaisesRegex(c.Invalid,'reference-only'):
                c.principles_delivery(project,spec)
            full=self.principle_spec()
            for profile in ('standard','learning','verification'):
                selected=c.principles_delivery(project,self.principle_spec(profile=profile))
                self.assertIn('qualified teacher or coach',selected['principles']['guidance'])
                self.assertIn('Declared omissions:',selected['principles']['guidance'])
            spec.update(full_export=full['export'],full_sha256=full['sha256'])
            self.assertEqual(c.principles_delivery(project,spec)['principles']['entries'],c.principles_delivery(project,full)['principles']['entries'])
            stale=self.principle_spec('withdrawn')
            spec.update(full_export=stale['export'],full_sha256=stale['sha256'])
            with self.assertRaisesRegex(c.Invalid,'stale full fetch'):
                c.principles_delivery(project,spec)
            for mutation,message in ((lambda x:x.update(schema_version=1),'unsupported derived version'),
                                     (lambda x:x['entries'][0].pop('applicability'),'incomplete'),
                                     (lambda x:x['entries'][0].update(status='deprecated'),'unsupported corpus')):
                value=json.loads(Path(full['export']).read_text());mutation(value)
                path=project/'bad-export.json';path.write_bytes(c.encoded(value))
                bad={**full,'export':str(path),'sha256':c.digest(path.read_bytes())}
                with self.assertRaisesRegex(c.Invalid,message):c.principles_delivery(project,bad)
            self.assertFalse((project/'.context-ai').exists())

    def test_principles_changed_native_input_refuses_before_any_write(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();project=root/'consumer';project.mkdir()
            spec=self.principle_spec()
            shutil.copytree(spec['source_root'],root/'source')
            spec['source_root']=str(root/'source')
            preview=c.principles_delivery(project,spec)
            path=root/'source/domains/coding/personal-growth.md';path.write_bytes(path.read_bytes()+b'\n')
            with self.assertRaisesRegex(c.Invalid,'source input digest changed'):
                c.principles_delivery(project,spec,action='apply',expected_plan=preview['plan_id'])
            self.assertEqual(list(project.iterdir()),[])

    def test_principles_sigkill_delivery_restores_bytes_and_modes(self):
        import select
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp).resolve()
            agents=project/'AGENTS.md';agents.write_bytes('User é\r\n'.encode());agents.chmod(0o600)
            before=agents.read_bytes()
            code='''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import context_ai as c
project=Path(sys.argv[2]);spec=json.loads(sys.argv[3]);preview=c.principles_delivery(project,spec)
original=c.atomic
def atomic(path,data,**kwargs):
 original(path,data,**kwargs)
 if path.name=='AGENTS.md':
  print('READY',flush=True)
  sys.stdin.read(1)
c.atomic=atomic
c.principles_delivery(project,spec,action='apply',expected_plan=preview['plan_id'])
'''
            child=subprocess.Popen([sys.executable,'-B','-c',code,str(ROOT/'scripts'),str(project),json.dumps(self.principle_spec())],
                                   stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                ready,_,_=select.select([child.stdout],[],[],20)
                self.assertTrue(ready)
                self.assertEqual(child.stdout.readline().strip(),'READY')
                child.kill();child.wait(timeout=10)
                self.assertEqual(child.returncode,-9)
            finally:
                if child.poll() is None:child.kill()
                child.wait(timeout=10)
                for stream in (child.stdin,child.stdout,child.stderr):stream.close()
            self.assertTrue(c.recover(project)['recovered'])
            self.assertEqual(agents.read_bytes(),before)
            self.assertEqual(agents.stat().st_mode&0o7777,0o600)
            self.assertFalse((project/'.context-ai/lock.json').exists())

    def test_explanation_resolves_inherited_web_selection_and_effective_options(self):
        command=[sys.executable,str(ROOT/'scripts/context_ai.py'),'explain','react-web',
                 '--brand','Keep the existing wordmark','--design-procedure','lightweight']
        run=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        explained=json.loads(run.stdout)
        with tempfile.TemporaryDirectory() as td:
            lock,files=c.resolve(['react-web'],Path(td),'codex',explained['options'])
        self.assertEqual(explained['composition'],lock['loadouts'])
        self.assertIn('web-experience',explained['loadouts'])
        self.assertEqual(explained['stages'],lock['stages'])
        self.assertEqual(explained['checks'],lock['checks'])
        self.assertEqual(explained['decisions'],lock['decisions'])
        self.assertEqual(explained['capabilities']['context-web-design']['path'],
                         'procedures/web-design-lightweight.md')
        self.assertIn(explained['capabilities']['context-web-design']['path'],files)
        self.assertNotIn('procedures/web-experience.md',files)
        self.assertEqual(explained['capability_requirements']['browser'],'optional')

    def test_explanation_is_declarative_without_runtime_discovery_and_validates_selection(self):
        with patch.object(c.shutil,'which',side_effect=AssertionError('explain must not probe')):
            result=c.explain(['standard'])
        self.assertNotIn('available',result['capabilities']['python-runtime'])
        for ids,options,message in [(['unknown'],{},'unknown loadout'),
                                    (['standard'],{'brand':'Web only'},'does not apply'),
                                    (['react-web'],{'design_procedure':'unknown'},'unsupported')]:
            with self.subTest(ids=ids,options=options),self.assertRaisesRegex(c.Invalid,message):
                c.explain(ids,options)
        loads=copy.deepcopy(c.catalogue());loads['standard']['capabilities']['unknown']='optional'
        with patch.object(c,'catalogue',return_value=loads),self.assertRaisesRegex(c.Invalid,'unknown capability'):
            c.explain(['standard'])

    def test_verify_reports_project_checks_unrun_and_missing_optional_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            project=Path(td).resolve();(project/'AGENTS.md').write_text('Keep my instructions\n')
            lock,files=c.resolve(['web-experience'],project,'codex')
            c.apply(project,lock,files)
            original=c.shutil.which
            with patch.object(c.shutil,'which',side_effect=lambda name:None if name=='playwright' else original(name)):
                result=c.verify(project)
            self.assertEqual(result['project_checks'],'not_run')
            self.assertEqual(result['suggested_checks'],lock['checks'])
            self.assertTrue(result['optional_unavailable'])
            self.assertEqual(result['optional_unavailable'][0]['id'],'browser')
            self.assertEqual(result['optional_unavailable'][0]['boundary'],
                             lock['capabilities']['browser']['definition']['boundary'])
            self.assertCountEqual(result['required_command_probes'],['git --version','python3 --version'])
            self.assertTrue(c.undo(project)['undone'])
            self.assertEqual((project/'AGENTS.md').read_text(),'Keep my instructions\n')

    def test_current_view_expands_defaults_and_excludes_predecessors(self):
        run=subprocess.run([sys.executable,str(ROOT/'scripts/context_ai.py'),'decisions','standard'],
                           capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        view=json.loads(run.stdout)
        self.assertEqual(view,c.explain(['standard'])['decisions'])
        self.assertEqual(view['D-004']['revision'],3)
        self.assertNotIn('D-008',view)
        for d in c.current_decisions().values():
            self.assertNotIn('v1 consumers',d['applicability'])
            self.assertFalse(any(e.startswith('kit:') for e in d['evidence']))
            for field in ('alternatives','unknowns','validation','rollback'):
                self.assertTrue(d[field])

    def test_native_archive_pin_does_not_inherit_consumer_git_revision(self):
        import io
        import tarfile
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'source';source.mkdir()
            for name in ['REVISION','.gitattributes']:
                (source/name).write_bytes((ROOT/name).read_bytes())
            subprocess.run(['git','init','-q',str(source)],check=True)
            subprocess.run(['git','-C',str(source),'add','.'],check=True)
            subprocess.run(['git','-C',str(source),'-c','user.name=Fixture','-c',
                            'user.email=fixture@example.invalid','commit','-qm','Source fixture'],check=True)
            revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
            with patch.object(c,'ROOT',source):
                self.assertEqual(c.source_revision(),revision)
            archive=subprocess.check_output(['git','-C',str(source),'archive','HEAD'])
            consumer=root/'consumer';consumer.mkdir()
            subprocess.run(['git','init','-q',str(consumer)],check=True)
            subprocess.run(['git','-C',str(consumer),'-c','user.name=Fixture','-c',
                            'user.email=fixture@example.invalid','commit','--allow-empty','-qm','Consumer fixture'],check=True)
            exported=consumer/'library';exported.mkdir()
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                # Only the two known fixture files are extracted; Python 3.10 compatible.
                for name in ['REVISION','.gitattributes']:
                    (exported/name).write_bytes(tar.extractfile(name).read())
            self.assertEqual((exported/'REVISION').read_text().strip(),revision)
            with patch.object(c,'ROOT',exported):
                self.assertEqual(c.source_revision(),revision)
                (exported/'REVISION').write_bytes((ROOT/'REVISION').read_bytes())
                self.assertEqual(c.source_revision(),'exported-tree')
                (exported/'REVISION').unlink()
                self.assertEqual(c.source_revision(),'exported-tree')
