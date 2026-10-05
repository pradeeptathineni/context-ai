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
        self.assertEqual(view['D-004']['revision'],2)
        self.assertNotIn('D-008',view)
        for d in c.current_decisions().values():
            self.assertNotIn('v1 consumers',d['applicability'])
            self.assertFalse(any(e.startswith('kit:') for e in d['evidence']))
            for field in ('alternatives','unknowns','validation','rollback'):
                self.assertTrue(d[field])
