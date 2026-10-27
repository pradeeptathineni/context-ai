"""Whole-workflow qualification of the named-project loadout portfolio owner."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import context_ai as ai
import context_portfolio as portfolio


class PortfolioWorkflow(unittest.TestCase):
    def test_create_revise_preview_subset_apply_cold_read_status_rollback(self):
        with tempfile.TemporaryDirectory(prefix='context-portfolio-') as temporary:
            root = Path(temporary)
            project_a, project_b = root / 'project-a', root / 'project-b'
            project_a.mkdir(); project_b.mkdir()
            project_a, project_b = project_a.resolve(), project_b.resolve()
            store = root / 'private-store'; store.mkdir(mode=0o700)
            projects = {
                'alpha': {'label': 'Synthetic alpha', 'path': str(project_a)},
                'beta': {'label': 'Synthetic beta', 'path': str(project_b)},
            }

            # Establish each project's independently managed prior selection.
            for project in (project_a, project_b):
                lock, files = ai.resolve(['release-review'], project, 'codex')
                ai.apply(project, lock, files)

            created = portfolio.create(store, projects, {'projects': {
                'alpha': {'loadouts': ['service-api'], 'provider': 'codex'},
                'beta': {'loadouts': ['research-evidence'], 'provider': 'codex'},
            }})
            self.assertTrue(created['created'])
            revised = portfolio.revise(store, projects, created['portfolio_id'], created['version'], created['digest'],
                                       {'projects': {
                                           'alpha': {'loadouts': ['service-api'], 'provider': 'codex'},
                                           'beta': {'loadouts': ['research-evidence'], 'provider': 'codex'},
                                       }})
            with self.assertRaisesRegex(portfolio.Invalid, 'stale portfolio basis'):
                portfolio.revise(store, projects, created['portfolio_id'], created['version'], created['digest'],
                                 {'projects': {'alpha': {'loadouts': ['service-api']}}})

            preview = portfolio.preview(store, projects, created['portfolio_id'], revised['version'], revised['digest'], ['alpha', 'beta'])
            self.assertEqual(set(preview['items']), {'alpha', 'beta'})
            self.assertNotEqual(preview['items']['alpha']['plan_id'], preview['items']['beta']['plan_id'])
            self.assertEqual(preview['items']['alpha']['old_scope']['loadouts'], ['release-review'])
            self.assertEqual(preview['items']['alpha']['new_scope']['loadouts'], ['service-api'])

            applied = portfolio.apply(store, projects, preview['preview_id'], ['alpha'])
            self.assertEqual(applied['projects']['alpha']['status'], 'applied')
            self.assertNotIn('beta', applied['projects'])
            # A second apply with the same identity is a receipt read, never a replay.
            replay = portfolio.apply(store, projects, preview['preview_id'], ['alpha'])
            self.assertTrue(replay['replayed'])
            self.assertEqual(portfolio.status(store, projects, applied['operation_id'])['projects']['alpha']['status'], 'current')

            owned_name = next(iter(ai.installed(project_a)['owned']))
            owned_path = ai.inside(project_a, owned_name)
            original = owned_path.read_bytes()
            owned_path.write_bytes(original + b'\noperator edit')
            self.assertEqual(portfolio.status(store, projects, applied['operation_id'])['projects']['alpha']['status'], 'drifted')
            refused = portfolio.rollback(store, projects, applied['operation_id'], ['alpha'])
            self.assertEqual(refused['projects']['alpha']['status'], 'refused')
            self.assertEqual(owned_path.read_bytes(), original + b'\noperator edit')
            owned_path.write_bytes(original)

            unrelated = project_a / 'user-notes.txt'
            unrelated.write_text('keep this independent user file')
            rolled = portfolio.rollback(store, projects, applied['operation_id'], ['alpha'])
            self.assertEqual(rolled['projects']['alpha']['status'], 'rolled_back')
            self.assertEqual(portfolio.status(store, projects, applied['operation_id'])['projects']['alpha']['status'], 'rolled_back')
            self.assertEqual(unrelated.read_text(), 'keep this independent user file')
            self.assertEqual(ai.installed(project_a)['resolution']['loadouts'], ['release-review'])
            self.assertEqual(ai.installed(project_b)['resolution']['loadouts'], ['release-review'])


if __name__ == '__main__':
    unittest.main()
