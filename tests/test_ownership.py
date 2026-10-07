import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import context_ai as c

class Ownership(unittest.TestCase):
    def test_every_active_file_has_exactly_one_owner(self):
        concerns,owner_of=c.ownership()
        self.assertEqual(c.active_files()-set(owner_of),set())
        self.assertEqual(owner_of['core/prior-art.md'],'prior-art')
        self.assertEqual(concerns['test-first-loop']['upstream'],'mattpocock')
        self.assertTrue(any(spec['owner_kind']=='native' for spec in concerns.values()))

    def test_two_owners_for_one_file_fail(self):
        document=c.read_yaml(ROOT/'ownership.yaml')
        document['concerns']['writing']['files'].append('core/testing.md')
        with patch.object(c,'read_yaml',side_effect=lambda p:document if p.name=='ownership.yaml' else original(p)):
            with self.assertRaisesRegex(c.Invalid,'two concern owners'):c.ownership()

    def test_uncovered_active_file_and_archive_route_fail(self):
        document=c.read_yaml(ROOT/'ownership.yaml')
        document['concerns']['verification']['files']=['core/testing.md']
        missing=copy.deepcopy(document);del missing['concerns']['writing']
        with patch.object(c,'read_yaml',side_effect=lambda p:missing if p.name=='ownership.yaml' else original(p)):
            with self.assertRaisesRegex(c.Invalid,'without a concern owner: .*overlays/writing.md'):c.ownership()
        loads=c.catalogue();loads['standard']=copy.deepcopy(loads['standard'])
        loads['standard']['stages']['inspect'].append('archive/overlays/prior-art.md')
        document['concerns']['writing']['files'].append('archive/overlays/prior-art.md')
        with patch.object(c,'catalogue',return_value=loads),patch.object(c,'read_yaml',side_effect=lambda p:document if p.name=='ownership.yaml' else original(p)):
            with self.assertRaisesRegex(c.Invalid,'archived file on an active route'):c.ownership()

    def test_unpinned_upstream_fails(self):
        document=c.read_yaml(ROOT/'ownership.yaml')
        document['concerns']['test-first-loop']['upstream']='unpinned'
        with patch.object(c,'read_yaml',side_effect=lambda p:document if p.name=='ownership.yaml' else original(p)):
            with self.assertRaisesRegex(c.Invalid,'not pinned'):c.ownership()

    def test_explain_reports_concern_owners_for_essentials(self):
        concerns=c.explain(['essentials'])['concerns']
        self.assertEqual(set(concerns),{'prior-art','test-first-loop','verification','code-review','current-docs','product-decision'})
        self.assertEqual(concerns['code-review']['selected'],['procedures/review.md'])

    def test_essentials_materializes_selected_upstream_closure_and_notices(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock,files=c.resolve(['essentials'],Path(tmp),'codex')
        for path in ['sourced/mattpocock/tdd/instruction.md','sourced/mattpocock/tdd/tests.md','sourced/mattpocock/tdd/mocking.md',
                     'sourced/mattpocock/LICENSE','sourced/ponytail/reuse/review.md','sourced/ponytail/reuse/LICENSE']:
            self.assertIn(path,files)
        self.assertNotIn('sourced/ecc/search-first/instruction.md',files)
        self.assertNotIn('archive/overlays/prior-art.md',files)

    def test_web_catalog_is_generated_from_current_loadouts(self):
        import subprocess
        run=subprocess.run([sys.executable,str(ROOT/'scripts/build_catalog.py'),'--check'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)

original=c.read_yaml

if __name__=='__main__':
    unittest.main()
