"""Explicit task choices, minimal closure and advisory/effect boundaries."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import context_ai as c


class TaskProfiles(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.project=Path(self.tmp.name).resolve()
        (self.project/'AGENTS.md').write_text('User authority: preserve my project.\n')
        (self.project/'notes.txt').write_text('Retained user notes.\n')

    def tearDown(self):
        self.tmp.cleanup()

    def example(self,name):
        return c.read_yaml(ROOT/'examples/task-profiles'/f'{name}.yaml')

    def packet(self,name):
        return c.task_packet(self.example(name),self.project)

    def test_six_agent_interpreted_profiles_resolve_distinct_useful_packets(self):
        cases={
            'integration':('procedures/diagnose.md','localized_debugging'),
            'architecture':('overlays/technical-design.md','architecture_critical'),
            'page':('procedures/web-design-lightweight.md','realtime_bounded_coding'),
            'api':('domains/service/api.md','coding_from_strong_spec'),
            'terraform':('domains/infrastructure/aws.md','realtime_bounded_coding'),
            'adoption':('core/prior-art.md','general_balanced')}
        for name,(resource,route) in cases.items():
            with self.subTest(name=name):
                packet=self.packet(name)
                self.assertIn(resource,packet['context']['reads'])
                self.assertEqual(packet['model']['route'],route)
                self.assertFalse(packet['model']['applied'])
                self.assertFalse(packet['orchestration']['applied'])
                self.assertEqual(packet['verification']['project_checks'],'not_run')
                self.assertEqual(packet['writes'],[])
        web=self.packet('page')['context']['reads']
        self.assertIn('sourced/anthropic/design/LICENSE.txt',web)
        self.assertIn('domains/web/browser-verification.md',web)
        self.assertNotIn('procedures/web-design.md',web)
        self.assertFalse(any(p.startswith('sourced/impeccable/') for p in web))

    def test_project_guidance_alone_adds_no_context_tools_or_model_route(self):
        with patch.object(c.shutil,'which',side_effect=AssertionError('unneeded discovery')):
            packet=self.packet('project-guidance')
        self.assertEqual(packet['context']['reads'],[])
        self.assertEqual(packet['capabilities'],{})
        self.assertIsNone(packet['model']['recommendation'])
        self.assertEqual(packet['unresolved'],[])

    def test_request_words_cannot_classify_or_grant_effects(self):
        profile=self.example('project-guidance')
        before=c.task_packet(profile,self.project)
        profile['task']='Deploy Terraform, redesign React, spawn agents and install all tools.'
        after=c.task_packet(profile,self.project)
        before.pop('task');after.pop('task')
        self.assertEqual(before,after)

    def test_discovery_reads_hostile_manifests_as_data_and_never_executes_or_writes(self):
        (self.project/'package.json').write_text(json.dumps({'scripts':{'test':'touch EXECUTED'},
            'packageManager':'npm@11.0.0','devDependencies':{'@playwright/test':'1.58.2'}}))
        (self.project/'playwright.config.js').write_text("throw new Error('must not import');")
        before={p.name:p.read_bytes() for p in self.project.iterdir()}
        with patch.object(c.subprocess,'run',side_effect=AssertionError('command execution')), \
             patch.object(c.subprocess,'check_output',side_effect=AssertionError('Git/model execution')):
            for p in (ROOT/'examples/task-profiles').glob('*.yaml'):
                packet=c.task_packet(c.read_yaml(p),self.project)
                for state in packet['capabilities'].values():
                    if state['definition']['kind']=='command':
                        self.assertFalse(state['discovery']['exercised'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.project.iterdir()})

    def test_missing_required_candidate_is_a_packet_gap_but_materialization_still_refuses(self):
        with patch.object(c.shutil,'which',return_value=None):
            packet=self.packet('terraform')
            self.assertFalse(packet['capabilities']['terraform']['available'])
            self.assertTrue(any('terraform: required candidate unavailable' in x for x in packet['unresolved']))
            with self.assertRaisesRegex(c.Invalid,'missing required capability'):
                c.resolve(['standard'],self.project,'codex')

    def test_stage_slice_omits_unrelated_procedures_and_matches_existing_options(self):
        profile=self.example('page');profile['context']['stages']=['test']
        packet=c.task_packet(profile,self.project)
        self.assertEqual(packet['context']['procedures'],[])
        self.assertNotIn('context-web-design',packet['capabilities'])
        self.assertEqual(packet['context']['options'],c.explain(['web-experience'],profile['context']['options'])['options'])
        profile=self.example('page');profile['context']['options']['design_procedure']='guided'
        packet=c.task_packet(profile,self.project)
        self.assertIn('procedures/web-design.md',packet['context']['reads'])
        self.assertNotIn('procedures/web-design-lightweight.md',packet['context']['reads'])

    def test_explicit_capabilities_survive_stage_filter_and_strengthen_requirements(self):
        profile=self.example('page');profile['context']['stages']=['test']
        profile['capabilities']={'context-diagnose':'required','browser':'required'}
        packet=c.task_packet(profile,self.project)
        self.assertIn('procedures/diagnose.md',packet['context']['reads'])
        self.assertEqual(packet['capabilities']['browser']['requirement'],'required')

    def test_omitted_stage_hints_preserve_conservative_resource_selection(self):
        document=c.capability_registry()
        for definition in document['capabilities'].values():
            definition.pop('stages',None)
        profile=self.example('page');profile['context']['stages']=['test']
        with patch.object(c,'capability_registry',return_value=document):
            packet=c.task_packet(profile,self.project)
        self.assertIn('procedures/web-design-lightweight.md',packet['context']['reads'])
        self.assertIn('context-web-design',packet['capabilities'])

    def test_model_policy_first_match_partial_wildcard_and_fallback(self):
        policy=c.read_yaml(ROOT/'models/routing.yaml')
        for route in policy['routes']:
            attributes={key:value for key,value in route['match'].items() if value!='*'}
            self.assertEqual(c.model_recommendation(attributes)['route'],route['id'])
        route=c.model_recommendation({'intent':'coding','difficulty':'high','scope':'bounded','requirements':'explicit','architecture':'settled'})
        self.assertEqual(route['route'],'difficult_coding')
        self.assertEqual(c.model_recommendation({'intent':'coding','requirements':'explicit'})['route'],'general_balanced')
        self.assertEqual(c.model_recommendation({'intent':'unlisted'})['route'],'general_balanced')
        for attributes in ({'risk':'high'},{'intent':'*'}):
            with self.assertRaises(c.Invalid):c.model_recommendation(attributes)

    def test_fresh_review_requires_consistent_explicit_shape_and_reports_host_gap(self):
        profile=self.example('project-guidance')
        profile['context']={'mode':'loadout','loadouts':['standard'],'stages':['review'],'options':{'review_mode':'fresh'}}
        with self.assertRaisesRegex(c.Invalid,'fresh review'):c.task_packet(profile,self.project)
        profile['orchestration']='fresh_review'
        packet=c.task_packet(profile,self.project)
        self.assertIn('procedures/review-fresh.md',packet['context']['reads'])
        self.assertNotIn('procedures/diagnose.md',packet['context']['reads'])
        self.assertTrue(any('Delegation authority' in x for x in packet['unresolved']))
        profile['context']['options']['review_mode']='direct'
        with self.assertRaisesRegex(c.Invalid,'must agree'):c.task_packet(profile,self.project)
        profile['context']={'mode':'direct','resources':['procedures/review-fresh.md']}
        profile.pop('orchestration')
        with self.assertRaisesRegex(c.Invalid,'fresh review'):c.task_packet(profile,self.project)

    def test_competing_primary_design_alternatives_fail_without_rejecting_review_prerequisites(self):
        profile=self.example('page')
        profile['capabilities']={'context-web-design-guided':'required'}
        with self.assertRaisesRegex(c.Invalid,'conflicting primary'):c.task_packet(profile,self.project)
        profile=self.example('project-guidance')
        profile['capabilities']={'context-review-direct':'required','context-review-fresh':'required'}
        profile['orchestration']='fresh_review'
        self.assertIn('procedures/review.md',c.task_packet(profile,self.project)['context']['reads'])

    def test_profile_contract_and_unknown_references_fail_usefully(self):
        base=self.example('project-guidance')
        for field,value in [('scheduler',{}),('verification',[]),('task',' '),
                            ('context',{'mode':'direct','loadouts':['standard']}),
                            ('orchestration','automatic'),('schema_version',2)]:
            profile={**base,field:value}
            with self.subTest(field=field),self.assertRaises(ValidationError):c.task_packet(profile,self.project)
        for changes,message in [({'capabilities':{'unknown':'required'}},'unknown capability'),
              ({'context':{'mode':'loadout','loadouts':['unknown'],'stages':['test']}},'unknown loadout'),
              ({'context':{'mode':'loadout','loadouts':['service-api'],'stages':['design']}},'stage does not apply'),
              ({'context':{'mode':'loadout','loadouts':['standard'],'stages':['test'],'options':{'brand':'wrong'}}},'does not apply'),
              ({'context':{'mode':'direct','resources':['../core/testing.md']}},'guidance Markdown'),
              ({'context':{'mode':'direct','resources':['sourced/AGENTS.md']}},'activation')]:
            with self.subTest(changes=changes),self.assertRaisesRegex(c.Invalid,message):
                c.task_packet({**base,**changes},self.project)

    def test_cli_profile_is_inspectable_and_rejects_mixed_authority_inputs(self):
        command=[sys.executable,str(ROOT/'scripts/context_ai.py'),'packet','--project',str(self.project)]
        profile=str(ROOT/'examples/task-profiles/project-guidance.yaml')
        run=subprocess.run(command+['--profile',profile],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(run.stdout),self.packet('project-guidance'))
        for extra in ([],['--profile',profile,'standard'],['--profile',profile,'--option','review_mode=fresh'],
                      ['--profile',profile,'--provider','other']):
            self.assertNotEqual(subprocess.run(command+extra,capture_output=True).returncode,0)
        run=subprocess.run([sys.executable,str(ROOT/'scripts/context_ai.py'),'explain','standard','--profile',profile],capture_output=True)
        self.assertNotEqual(run.returncode,0)

    def test_safe_profile_parsing_retains_duplicate_alias_and_size_boundaries(self):
        path=self.project/'task.yaml'
        for text in ('task: a\ntask: b\n','x: &x [a]\ny: *x\n','x: !!python/object:object {}\n','x'*2_000_001):
            path.write_text(text)
            with self.assertRaises(Exception):c.read_yaml(path)

    def test_real_use_profile_resolves_existing_guidance_without_installation(self):
        profile=c.read_yaml(ROOT/'evals/task-profile-use.yaml')
        packet=c.task_packet(profile,self.project)
        self.assertTrue(packet['pact']['required'])
        self.assertEqual(len(packet['context']['reads']),11)
        self.assertEqual(packet['orchestration']['recommendation'],'single_agent')
        self.assertEqual(packet['writes'],[])


if __name__=='__main__':
    unittest.main()
