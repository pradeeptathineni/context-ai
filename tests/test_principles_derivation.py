"""A correctly rehashed export must still derive completely from native bytes."""
import base64
import copy
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import context_ai as engine
import context_principles as reader


class NativeDerivation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name).resolve()
        self.project=self.root/'consumer';self.project.mkdir()
        self.fixture=ROOT/'tests/fixtures/principles-export/baseline'
        self.original=json.loads((self.fixture/'verification.json').read_text())

    def tearDown(self):self.tmp.cleanup()

    def spec(self,value,folder=None):
        folder=folder or self.fixture
        path=self.root/'export.json';path.write_bytes(engine.encoded(value))
        return {'export':str(path),'sha256':engine.digest(path.read_bytes()),'revision':value['source_revision'],
                'source_root':str(folder/'source'),'intent':'operational'}

    def rejected_before_write(self,value):
        self.assertEqual(value['inputs'],self.original['inputs'])
        self.assertEqual(value['input_sha256'],self.original['input_sha256'])
        spec=self.spec(value)
        with self.assertRaisesRegex(engine.Invalid,'native derivation mismatch'):
            reader.read(spec)
        for action in ('plan','apply'):
            with self.assertRaisesRegex(engine.Invalid,'native derivation mismatch'):
                engine.principles_delivery(self.project,spec,action=action,expected_plan='old-plan')
            self.assertEqual(list(self.project.iterdir()),[])
        # Reopen/derived-resource validation must not bypass the same check.
        selection=reader.read(self.spec(self.original))
        malformed=engine.encoded(value)
        selection['artifact_sha256']=engine.digest(malformed)
        selection['bundle']['artifact']=base64.b64encode(malformed).decode()
        with self.assertRaisesRegex(engine.Invalid,'native derivation mismatch'):
            reader.resources(selection)

    def target(self,value):
        return next(entry for entry in value['entries'] if entry['id']=='PRN-000012')

    @staticmethod
    def reword(claim,plain):
        suffix=re.search(r'\s+\[[^\]]+:\d+\](?:, \[[^\]]+:\d+\])*$',claim['text']).group(0)
        claim['text']=plain+suffix
        claim['claim_sha256']=engine.digest(plain.encode())

    def test_entire_applicability_and_nonempty_shortened_exception_are_rejected(self):
        for kind in ('empty','shortened'):
            with self.subTest(kind=kind):
                value=copy.deepcopy(self.original);entry=self.target(value)
                if kind=='empty':entry['applicability']=[]
                else:self.reword(entry['applicability'][0],'A complete change may be large when its parts cannot work or be evaluated independently.')
                self.rejected_before_write(value)

    def test_changed_statement_or_omitted_practice_with_correct_hashes_are_rejected(self):
        for kind in ('statement','practice'):
            with self.subTest(kind=kind):
                value=copy.deepcopy(self.original);entry=self.target(value)
                if kind=='statement':self.reword(entry['statement'],'This replacement statement is absent from the bound native source.')
                else:entry['practices'].pop()
                self.rejected_before_write(value)

    def test_ordered_roles_and_citations_must_match_native_entry(self):
        for kind in ('order','citation','role'):
            with self.subTest(kind=kind):
                value=copy.deepcopy(self.original);entry=self.target(value)
                if kind=='order':
                    entry['practices'].reverse()
                    for index,claim in enumerate(entry['practices'],1):claim['role']='practice-'+str(index)
                elif kind=='role':entry['statement']['role']='statement-replacement'
                else:
                    claim=entry['statement']
                    claim['text']=re.sub(r'\s+\[[^\]]+:\d+\](?:, \[[^\]]+:\d+\])*$', ' [coding.principles:4]',claim['text'])
                    claim['source_ids']=['SRC-000027']
                self.rejected_before_write(value)

    def test_verification_evidence_must_equal_retained_native_record(self):
        for kind in ('empty','none','shortened','reviewer'):
            with self.subTest(kind=kind):
                value=copy.deepcopy(self.original);entry=self.target(value)
                if kind=='empty':entry['evidence']={}
                elif kind=='none':entry['evidence']=None
                elif kind=='shortened':entry['evidence']['claims'].pop()
                else:entry['evidence']['reviewer']['type']='human'
                self.rejected_before_write(value)

    def test_learning_goal_and_tags_cannot_be_substituted(self):
        for kind in ('goals','tags'):
            with self.subTest(kind=kind):
                value=copy.deepcopy(self.original)
                entry=next(entry for entry in value['entries'] if entry['id']=='PRN-000014')
                if kind=='goals':entry['goals']=[]
                else:entry['tags']=['invented-tag']
                self.rejected_before_write(value)

    def test_real_profile_lifecycle_and_bound_minimal_full_controls(self):
        for variant in ('baseline','qualified','withdrawn'):
            folder=ROOT/'tests/fixtures/principles-export'/variant
            for profile in ('standard','learning','verification'):
                with self.subTest(variant=variant,profile=profile):
                    value=json.loads((folder/(profile+'.json')).read_text())
                    spec=self.spec(value,folder);spec['intent']='inspect'
                    selected=reader.read(spec)
                    self.assertEqual(selected['selected_ids'],[entry['id'] for entry in value['entries']])
                    self.assertIn('principles/selected.md',reader.resources(selected))
            minimal=json.loads((folder/'minimal.json').read_text())
            spec=self.spec(minimal,folder)
            full=folder/'verification.json'
            spec.update(full_export=str(full),full_sha256=engine.digest(full.read_bytes()),intent='inspect')
            self.assertEqual(reader.read(spec)['input_sha256'],minimal['input_sha256'])

    def test_exact_plain_inline_code_projection_and_unsupported_markup_control(self):
        raw=(self.fixture/'source/domains/coding/principles.md').read_bytes()
        expected=reader.native_entry(raw,'PRN-000012','coding.principles')
        code=raw.replace(b'Separate decisions that',b'Separate `decisions` that')
        self.assertEqual(reader.native_entry(code,'PRN-000012','coding.principles'),expected)
        emphasis=raw.replace(b'Separate decisions that',b'Separate **decisions** that')
        with self.assertRaisesRegex(engine.Invalid,'unsupported native inline Markdown'):
            reader.native_entry(emphasis,'PRN-000012','coding.principles')
