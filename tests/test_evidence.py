import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evidence as e

FIXTURE=Path(__file__).parent/'fixtures/evidence-bundle-v1.fixture.json'
NOW=datetime(2026,10,5,20,tzinfo=timezone.utc)
class Evidence(unittest.TestCase):
    def check_value(self,b,allow=True):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bundle.json';p.write_text(json.dumps(b)+'\n')
            return e.load_bundle(p,hashlib.sha256(p.read_bytes()).hexdigest(),allow_fixture=allow,now=NOW)
    def fixture(self):return json.loads(FIXTURE.read_text())
    def test_fixture_never_becomes_real_adoption(self):
        b=self.fixture();result=self.check_value(b)
        self.assertEqual(result['admitted_as'],'fixture-test');self.assertFalse(result['activation'])
        with self.assertRaisesRegex(e.Invalid,'fixture'):self.check_value(b,allow=False)
    def test_exact_bytes_and_schema_version(self):
        with self.assertRaisesRegex(e.Invalid,'digest'):e.load_bundle(FIXTURE,'0'*64,allow_fixture=True,now=NOW)
        b=self.fixture();b['schema_version']=2
        with self.assertRaises(Exception):self.check_value(b)
    def test_duplicate_and_unresolved_source_claim_concept(self):
        mutations=[lambda b:b['sources'].append(copy.deepcopy(b['sources'][0])),lambda b:b['claims'][0].update(source_ids=['forged']),lambda b:b['candidates'][0].update(claim_ids=['forged']),lambda b:b['need'].update(concept_ids=['unresolved'])]
        for change in mutations:
            b=self.fixture();change(b)
            with self.assertRaises(e.Invalid):self.check_value(b)
    def test_adoption_requires_support_and_constraints_cannot_activate(self):
        b=self.fixture();b['candidates'][0].update(disposition='adopt',claim_ids=[])
        with self.assertRaisesRegex(e.Invalid,'supported'):self.check_value(b)
        b=self.fixture();b['candidates'][0]['disposition']='adopt';b['need']['constraints']=['Unresolved blocking install authority']
        result=self.check_value(b);self.assertFalse(result['activation']);self.assertTrue(result['constraints'])
        b['claims'][0]['status']='contradicted'
        with self.assertRaisesRegex(e.Invalid,'supported'):self.check_value(b)
    def test_private_urls_policy_ids_and_privacy_fail(self):
        for url in ['https://127.0.0.1/source','https://localhost/source','http://example.com/source','file:///etc/passwd','https://user:pass@example.com/source','https://example.local/source']:
            b=self.fixture();b['sources'][0]['uri']=url
            with self.assertRaises(e.Invalid):self.check_value(b)
        for ext in [{'privacy_scope':'private'},{'policy_id':'forged-policy'}]:
            b=self.fixture();b['extensions']=ext
            with self.assertRaises(e.Invalid):self.check_value(b)
    def test_freshness_is_explicit_and_never_refreshes_installed_state(self):
        b=self.fixture();b['sources'][0]['observed_at']='2025-01-01T00:00:00Z'
        result=self.check_value(b);self.assertEqual(result['stale_source_ids'],['src-1']);self.assertFalse(result['activation'])
        b['sources'][0]['observed_at']='2027-01-01T00:00:00Z'
        with self.assertRaisesRegex(e.Invalid,'future'):self.check_value(b)
    def test_dishonest_mode_and_unknown_freshness(self):
        b=self.fixture();b['mode']='model-led'
        with self.assertRaisesRegex(e.Invalid,'producer'):self.check_value(b)
        result=self.check_value(self.fixture());self.assertEqual(result['unknown_freshness_ids'],['src-1'])
    def test_empty_requires_limitation(self):
        b=self.fixture();b['sources']=[];b['claims']=[];b['candidates']=[];b['limitations']=[]
        with self.assertRaisesRegex(e.Invalid,'limitation'):self.check_value(b)
    def test_duplicate_json_key_rejected_after_digest_check(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bundle.json';p.write_text('{"schema_version":1,"schema_version":2}')
            with self.assertRaisesRegex(e.Invalid,'duplicate'):e.load_bundle(p,hashlib.sha256(p.read_bytes()).hexdigest(),allow_fixture=True,now=NOW)

    def test_real_peer_export_replays_with_pinned_identity_and_no_activation(self):
        bundle=Path(__file__).resolve().parents[1]/'evals/signals-evidence.bundle.json'
        sha='62e5cb9a6d825a1d5194a28035640b248ee05e344bb41fd816355c1a378cb8da'
        commit='4ab32a1d7ae09ae0ebb6102b4b2d7571291c5c97'
        result=e.load_bundle(bundle,sha,'pradeeptathineni/signals-ai',commit,now=NOW)
        self.assertEqual(result['mode'],'agent-assisted')
        self.assertEqual(result['admitted_as'],'pinned-peer-evidence')
        self.assertEqual(len(result['recommendations']),10)
        self.assertFalse(result['activation'])
        with self.assertRaisesRegex(e.Invalid,'identity'):
            e.load_bundle(bundle,sha,'forged/producer',commit,now=NOW)
