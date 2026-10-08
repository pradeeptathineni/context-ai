import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import context_ai as c
from evidence import inspect_bundle
from adoption import decide

FIXTURE=ROOT/'tests/fixtures/evidence-recommendation-v1.fixture.json'
OLD=ROOT/'tests/fixtures/evidence-bundle-v1.fixture.json'

def admit(path):
    return inspect_bundle(path,hashlib.sha256(path.read_bytes()).hexdigest(),allow_fixture=True)

class Adoption(unittest.TestCase):
    def write(self,bundle):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        path=Path(self.tmp.name)/'bundle.json';path.write_text(json.dumps(bundle));return path

    def test_frozen_v1_bundle_still_reads_without_recommendations(self):
        admitted=admit(OLD)
        self.assertIsNone(admitted['contextual_recommendations'])
        self.assertEqual(admitted['input_schema_version'],1)

    def test_recommendation_envelope_round_trips_and_stays_advisory(self):
        admitted=admit(FIXTURE)
        rec=admitted['contextual_recommendations']
        self.assertEqual(rec['version'],'signals-recommendation-v1')
        self.assertIn('advisory',rec['authority']);self.assertFalse(admitted['activation'])
        copy_path=self.write(json.loads(FIXTURE.read_text()))
        self.assertEqual(admit(copy_path)['contextual_recommendations']['items'],rec['items'])

    def test_unsupported_or_dangling_recommendations_are_rejected(self):
        bundle=json.loads(FIXTURE.read_text())
        bad=copy.deepcopy(bundle);bad['extensions']['signals.recommendations']['version']='signals-recommendation-v2'
        with self.assertRaisesRegex(c.Invalid,'unsupported recommendation extension version'):admit(self.write(bad))
        bad=copy.deepcopy(bundle);bad['extensions']['signals.recommendations']['items'][0]['candidate_id']='nope'
        with self.assertRaisesRegex(c.Invalid,'unknown candidate'):admit(self.write(bad))
        bad=copy.deepcopy(bundle);bad['extensions']['signals.recommendations']['items'][0]['action']='install'
        with self.assertRaises(Exception):admit(self.write(bad))

    def test_high_score_wrong_fit_is_not_adopted(self):
        result=decide(admit(FIXTURE),{'capability':'http-retry','runtimes':['python'],'licenses_allowed':['MIT','Apache-2.0','BSD-3-Clause']})
        by={d['candidate']:d for d in result['decisions']}
        self.assertEqual(by['cand-popular']['decision'],'reject')
        self.assertEqual(by['cand-popular']['producer_intrinsic_strength'],'high')
        self.assertEqual(by['cand-popular']['producer_disposition'],'adopt')
        self.assertIn('runtime node',by['cand-popular']['blocked_by'][0])
        self.assertEqual(by['cand-urllib3']['decision'],'trial')
        self.assertEqual(by['cand-rumor']['decision'],'study')
        self.assertFalse(result['activation'])

    def test_existing_owner_and_capability_mismatch(self):
        admitted=admit(FIXTURE)
        by={d['candidate']:d for d in decide(admitted,{'capability':'http-retry','existing_owner':'local retry loop'})['decisions']}
        self.assertEqual(by['cand-popular']['decision'],'trial')
        self.assertTrue(by['cand-popular']['notes'])
        by={d['candidate']:d for d in decide(admitted,{'capability':'rate-limiting'})['decisions']}
        self.assertEqual(by['cand-urllib3']['decision'],'reject')
        with self.assertRaisesRegex(c.Invalid,'capability'):decide(admitted,{'runtimes':['python']})

    def test_producer_adopt_without_capability_mapping_is_only_studied(self):
        result=decide(admit(OLD),{'capability':'browser-validation'})
        self.assertEqual([d['decision'] for d in result['decisions']],['study'])
        bundle=json.loads(FIXTURE.read_text());del bundle['extensions']['signals.recommendations']
        decisions=decide(admit(self.write(bundle)),{'capability':'http-retry'})['decisions']
        self.assertTrue(all(d['decision']=='study' for d in decisions))
        self.assertEqual({d['producer_disposition'] for d in decisions},{'adopt','consider'})

    def test_context_assessment_maps_capability_and_overrides_producer_facts(self):
        bundle=json.loads(FIXTURE.read_text());del bundle['extensions']['signals.recommendations']
        admitted=admit(self.write(bundle))
        need={'capability':'http-retry','runtimes':['python'],'licenses_allowed':['MIT'],
              'assessments':{'cand-urllib3':{'capability':'http-retry','revision':'2.8.0','facts':{'runtime':'python','license':'MIT'},
                                             'verified':['installed Retry signature']},
                             'cand-popular':{'capability':'http-retry','revision':'9.9.9','facts':{'runtime':'node','license':'MIT'},
                                             'verified':['package.json engines']}}}
        result=decide(admitted,need);by={d['candidate']:d for d in result['decisions']}
        self.assertEqual(by['cand-urllib3']['decision'],'trial');self.assertEqual(by['cand-popular']['decision'],'reject')
        self.assertEqual(by['cand-rumor']['decision'],'study')
        self.assertIn('not granted',result['trial_authorization'])
        for bad in ({'nope':{'capability':'x','revision':'1','verified':['y']}},{'cand-urllib3':{'capability':'x'}},
                    {'cand-urllib3':{'capability':'x','revision':'1','verified':[]}}):
            with self.assertRaises(c.Invalid):decide(admitted,{'capability':'http-retry','assessments':bad})

    def test_incomplete_assessment_does_not_claim_license_or_runtime_verification(self):
        bundle=json.loads(FIXTURE.read_text())
        admitted=admit(self.write(bundle))
        base={'capability':'http-retry','revision':'2.8.0','verified':['installed Retry signature']}
        need=lambda facts,**extra:{'capability':'http-retry','runtimes':['python'],'licenses_allowed':['MIT'],
                                   'assessments':{'cand-urllib3':{**base,**({'facts':facts} if facts is not None else {})}},**extra}
        def verdict(n):
            return {d['candidate']:d for d in decide(admitted,n)['decisions']}['cand-urllib3']
        # capability-only: producer fills the fields, labelled as producer-reported, state partial
        for facts in (None,{}):
            with self.subTest(facts=facts):
                d=verdict(need(facts))
                self.assertEqual(d['decision'],'trial');self.assertEqual(d['verification']['state'],'partial')
                self.assertEqual(d['verification']['fact_origin'],{'license':'producer','runtime':'producer'})
                text=' '.join(d['notes'])
                self.assertIn('capability verified by Context',text);self.assertIn('license MIT is producer-reported and not verified by Context',text)
                self.assertNotIn('license verified by Context',text);self.assertNotIn('runtime python verified by Context',text)
        # partial: only runtime inspected
        d=verdict(need({'runtime':'python'}))
        self.assertEqual(d['verification']['fact_origin'],{'license':'producer','runtime':'context'})
        self.assertEqual((d['verification']['state'],d['verification']['unverified_constraints']),('partial',['license']))
        # complete
        d=verdict(need({'runtime':'python','license':'MIT'}))
        self.assertEqual((d['verification']['state'],d['verification']['unverified_constraints']),('complete',[]))
        # assessed fact overrides a conflicting producer value
        d=verdict(need({'runtime':'python','license':'GPL-3.0-only'}))
        self.assertEqual(d['decision'],'reject');self.assertEqual(d['verification']['fact_origin']['license'],'context')
        # no producer facts and no assessed facts: unknown, study, never "verified"
        bare=json.loads(FIXTURE.read_text());del bare['extensions']['signals.recommendations']
        d={x['candidate']:x for x in decide(admit(self.write(bare)),need(None))['decisions']}['cand-urllib3']
        self.assertEqual(d['decision'],'study');self.assertEqual(d['verification']['fact_origin'],{'license':'unknown','runtime':'unknown'})
        self.assertEqual(d['verification']['state'],'partial');self.assertNotIn('verified by Context at',' '.join(n for n in d['notes'] if 'license' in n or 'runtime' in n))
        # unassessed candidates report no verification at all
        none=[x for x in decide(admitted,need({}))['decisions'] if x['candidate']=='cand-popular'][0]
        self.assertEqual(none['verification']['state'],'none')
        for bad in ({'license':''},{'runtime':'  '},{'license':3},{'owner':'x'}):
            with self.subTest(bad=bad),self.assertRaises(c.Invalid):decide(admitted,need(bad))

    def test_research_route_does_not_require_signals(self):
        text=(ROOT/'procedures/research-evidence.md').read_text()
        self.assertIn('never blocks a decision',text)
        with tempfile.TemporaryDirectory() as tmp:
            lock,files=c.resolve(['research-evidence'],Path(tmp),'codex')
        self.assertIn('procedures/current-docs.md',files)
        self.assertFalse(any('signals' in p.lower() for p in files if p.startswith(('scripts/','signals/'))))

if __name__=='__main__':
    unittest.main()
