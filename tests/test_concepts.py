import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import concepts
import context_ai as c

class ConceptNeeds(unittest.TestCase):
    def test_generated_needs_cover_actual_ids_once_and_preserve_uncertainty(self):
        result = concepts.generate()
        ids = [entry['id'] for group in result['questions'] for entry in group['concepts']]
        self.assertEqual(set(ids), set(concepts.catalog()))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual({x['id'] for x in result['coverage']}, set(ids))
        for item in result['coverage']:
            if item['disposition'] == 'unresolved':
                self.assertTrue(item['next_action'])
        self.assertTrue(result['constraints'])
        self.assertLess(len(result['questions']), len(ids))

    def test_claim_bindings_cannot_use_generic_sources_or_unknown_references(self):
        import copy
        entries=concepts.catalog();decisions=c.current_decisions()
        concepts.validate_catalog(entries,decisions)
        id='context.loadouts'
        for change in [lambda x:x[id]['coverage'].update(source_refs=['agent-skills']),lambda x:x[id]['coverage'].update(claim_refs=['development-r1:forged']),lambda x:x[id]['coverage'].update(disposition='confident'),lambda x:x[id]['coverage'].update(decision_refs=['D-forged'])]:
            changed=copy.deepcopy(entries);change(changed)
            with self.assertRaises(c.Invalid):concepts.validate_catalog(changed,decisions)

    def test_options_are_contextual_and_offering_never_enables(self):
        options=concepts.offered_options()
        self.assertGreaterEqual(len(options['context.loadouts']),2)
        for candidates in options.values():
            for candidate in candidates:
                self.assertFalse(candidate['enabled'])
                self.assertTrue(candidate['use_when']);self.assertTrue(candidate['boundary'])
