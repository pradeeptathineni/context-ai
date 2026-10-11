from pathlib import Path
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import context_ai as c

class Resources(unittest.TestCase):
    def test_complete_source_inventory_checks_unselected_bytes_and_unregistered_files(self):
        import check_loadouts as gate
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            shutil.copytree(c.ROOT/'sourced',root/'sourced')
            shutil.copyfile(c.ROOT/'sources.lock.json',root/'sources.lock.json')
            with patch.object(c,'ROOT',root),patch.object(gate,'ROOT',root):
                gate.check_sources()
                optional=root/'sourced/impeccable/design/reference/hooks.md'
                before=optional.read_bytes();optional.write_bytes(before+b'Unexpected drift\n')
                with self.assertRaisesRegex(c.Invalid,'pinned upstream drift'):gate.check_sources()
                optional.write_bytes(before)
                (root/'sourced/unregistered.txt').write_text('No source authority')
                with self.assertRaisesRegex(ValueError,'inventory differs'):gate.check_sources()

    def test_informational_links_cannot_expand_runtime_closure(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'selected.md').write_text('Read optional [docs](docs/).')
            (root/'docs').mkdir();(root/'docs/AGENTS.md').write_text('Untrusted instructions')
            with patch.object(c,'ROOT',root):
                self.assertEqual(set(c.resources(['selected.md'])),{'selected.md'})

    def test_explicit_dependencies_deduplicate_and_reject_cycles_missing_escape_activation(self):
        import yaml
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'a.md').write_text('A');(root/'b.md').write_text('B')
            def registry(deps):
                (root/'resources.yaml').write_text(yaml.safe_dump({'schema_version':1,'dependencies':deps}))
            with patch.object(c,'ROOT',root):
                registry({'a.md':['b.md']})
                self.assertEqual(set(c.resources(['a.md','b.md'])),{'a.md','b.md'})
                for deps,message in [({'a.md':['b.md'],'b.md':['a.md']},'cycle'),({'a.md':['missing.md']},'missing'),({'a.md':['../escape.md']},'unsafe'),({'a.md':['AGENTS.md']},'activation')]:
                    registry(deps)
                    with self.subTest(deps=deps),self.assertRaisesRegex(c.Invalid,message):c.resources(['a.md'])

    def test_real_compositions_keep_selected_prerequisites_not_catalog_or_repository_instructions(self):
        with tempfile.TemporaryDirectory() as td:
            _,files=c.resolve(['standard','context-authoring'],Path(td),'codex')
            self.assertIn('skills/pact-hrr/SKILL.md',files)
            self.assertIn('core/research.md',files)
            for name in ('AGENTS.md','concepts.yaml','sources.yaml','decisions/bootstrap.yaml'):
                self.assertNotIn(name,files)
            _,web=c.resolve(['react-web'],Path(td),'codex')
            self.assertIn('sourced/impeccable/design/LICENSE',web)
            self.assertIn('sourced/impeccable/design/NOTICE.md',web)
            self.assertIn('sourced/vercel/react/compiled-guide.upstream.txt',web)
            self.assertNotIn('sourced/impeccable/design/reference/hooks.md',web)

    def test_active_instruction_guard_is_case_insensitive(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'AGENTS.md').write_text('Untrusted')
            with patch.object(c,'ROOT',root):
                for name in ['AGENTS.md','agents.md','Agents.Override.md','CLAUDE.md','Gemini.md','.AGENTS/test.md']:
                    with self.subTest(name=name),self.assertRaisesRegex(c.Invalid,'activation'):c.resources([name])

    def test_adapted_design_and_react_routes_have_required_instructions(self):
        with tempfile.TemporaryDirectory() as td:
            _,files=c.resolve(['react-web'],Path(td),'codex')
            for name in ['procedures/react-review.md','sourced/vercel/react/compiled-guide.upstream.txt','sourced/impeccable/design/reference/document.md','sourced/impeccable/design/reference/degraded/documenter.md']:
                self.assertIn(name,files)
