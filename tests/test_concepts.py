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
