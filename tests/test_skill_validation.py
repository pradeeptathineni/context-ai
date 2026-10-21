# Agent Skills package checks adapted from agentskills/agentskills@69ef37e skills-ref tests
# (Apache-2.0, sourced/agentskills/LICENSE); Context adds trust-boundary and delivery cases.
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import context_ai as c
import context_skills as s

CLI = ROOT / 'scripts' / 'context_ai.py'


def skill(name='my-skill', description='A test skill', extra=''):
    return f'---\nname: {name}\ndescription: {description}\n{extra}---\n# Body\n'.encode()


class Metadata(unittest.TestCase):
    def errors(self, data, expected='my-skill'):
        return s.check_entry(data if isinstance(data, bytes) else data.encode(), expected)

    def assertRefused(self, data, fragment, expected='my-skill'):
        errors = self.errors(data, expected)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_valid_minimal_and_all_specified_fields(self):
        self.assertEqual(self.errors(skill()), [])
        self.assertEqual(self.errors(skill(extra='license: MIT\ncompatibility: Requires Python 3.11+\n'
                                             'metadata:\n  author: Test\n  version: "1.0"\n')), [])

    def test_required_fields_and_frontmatter_shape(self):
        self.assertRefused('---\ndescription: d\n---\n', 'Missing required field in frontmatter: name')
        self.assertRefused('---\nname: my-skill\n---\n', 'Missing required field in frontmatter: description')
        self.assertRefused('# No frontmatter here', 'must start with YAML frontmatter')
        self.assertRefused('---\nname: my-skill\ndescription: d\n', 'not properly closed')
        self.assertRefused('---\n- just\n- a list\n---\n', 'must be a YAML mapping')
        self.assertRefused('---\nname: [invalid\ndescription: broken\n---\n', 'Invalid YAML')
        # Upstream splits on the first '---' anywhere; a delimiter must be its own line here.
        self.assertRefused('---\nname: my-skill\ndescription: a---b\n', 'not properly closed')
        self.assertEqual(self.errors(skill(description='"a --- b"')), [])

    def test_invalid_types_are_refused_not_coerced(self):
        self.assertRefused(skill(name='123', description='d'), "'name' must be a non-empty string", '123')
        self.assertRefused(skill(name='yes'), "'name' must be a non-empty string")
        self.assertRefused(skill(description='[a, b]'), "'description' must be a non-empty string")
        self.assertRefused(skill(description='""'), "'description' must be a non-empty string")
        self.assertRefused(skill(extra='compatibility: 3.11\n'), "'compatibility' must be a string")
        self.assertRefused(skill(extra='license: [MIT]\n'), "'license' must be a string")
        # strictyaml would coerce 1.0 to "1.0"; Context requires an explicit string.
        self.assertRefused(skill(extra='metadata:\n  version: 1.0\n'), "'metadata' must map strings")
        self.assertRefused(skill(extra='metadata: plain\n'), "'metadata' must map strings")

    def test_duplicate_aliases_and_unsafe_yaml_fail_at_the_boundary(self):
        self.assertRefused('---\nname: my-skill\nname: other\ndescription: d\n---\n', 'duplicate or non-string YAML key')
        self.assertRefused('---\nname: &n my-skill\ndescription: *n\n---\n', 'aliases are not supported')
        self.assertRefused('---\nname: !!python/object/apply:os.system ["true"]\ndescription: d\n---\n', 'Invalid YAML')
        self.assertRefused('---\n1: my-skill\nname: my-skill\ndescription: d\n---\n', 'duplicate or non-string YAML key')

    def test_name_rules_and_directory_match(self):
        self.assertRefused(skill(name='MySkill'), 'must be lowercase', 'MySkill')
        self.assertRefused(skill(name='НАВЫК'), 'must be lowercase', 'НАВЫК')
        self.assertRefused(skill(name='-my-skill'), 'cannot start or end with a hyphen', '-my-skill')
        self.assertRefused(skill(name='my--skill'), 'consecutive hyphens', 'my--skill')
        self.assertRefused(skill(name='my_skill'), 'invalid characters', 'my_skill')
        self.assertRefused(skill(name='a' * 65), 'exceeds 64 character limit', 'a' * 65)
        self.assertEqual(self.errors(skill(name='a' * 64), 'a' * 64), [])
        self.assertRefused(skill(name='correct-name'), "Directory name 'wrong-name' must match", 'wrong-name')
        for name in ('技能', 'мой-навык', 'навык'):
            self.assertEqual(self.errors(skill(name=name), name), [], name)
        self.assertEqual(self.errors(skill(name='café'), 'café'), [])

    def test_length_bounds_and_unexpected_fields(self):
        self.assertEqual(self.errors(skill(description='x' * 1024)), [])
        self.assertRefused(skill(description='x' * 1025), 'Description exceeds 1024 character limit')
        self.assertEqual(self.errors(skill(extra='compatibility: ' + 'x' * 500 + '\n')), [])
        self.assertRefused(skill(extra='compatibility: ' + 'x' * 501 + '\n'), 'Compatibility exceeds 500')
        self.assertRefused(skill(extra='unknown_field: no\n'), 'Unexpected fields in frontmatter: unknown_field')

    def test_bounded_bytes_and_encoding(self):
        limit = skill() + b'x' * (s.MAX_SKILL_BYTES - len(skill()))
        self.assertEqual(self.errors(limit), [])
        self.assertRefused(limit + b'x', f'exceeds {s.MAX_SKILL_BYTES} bytes')
        self.assertRefused(b'---\nname: my-skill\ndescription: \xff\n---\n', 'not UTF-8')

    def test_tool_pre_approval_is_specified_but_not_delivered(self):
        data = skill(extra='allowed-tools: Bash(git:*)\n')
        metadata, _ = s.parse(data)
        self.assertEqual(s.validate_metadata(metadata, 'my-skill'), [])
        self.assertRefused(data, 'allowed-tools pre-approval is not delivered by Context')
        self.assertRefused(skill(extra='allowed-tools: [Bash]\n'), "'allowed-tools' must be a string")


class Packages(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def package(self, name='my-skill', data=None, **files):
        path = self.root / name
        path.mkdir()
        (path / 'SKILL.md').write_bytes(skill(name) if data is None else data)
        for rel, value in files.items():
            (path / rel).parent.mkdir(parents=True, exist_ok=True)
            (path / rel).write_bytes(value)
        return path

    def test_valid_package_reports_exact_file_identities(self):
        path = self.package(**{'references/guide.md': b'guide\n'})
        report = s.check_package(path)
        self.assertTrue(report['valid'], report)
        self.assertEqual(report['name'], 'my-skill')
        self.assertEqual(set(report['files']), {'SKILL.md', 'references/guide.md'})
        self.assertEqual(report['files']['SKILL.md'], c.digest(skill()))
        self.assertEqual(report['package_sha256'], c.digest(c.encoded(report['files'])))

    def test_pinned_upstream_review_bytes_are_a_valid_named_package(self):
        data = (ROOT / 'sourced/mattpocock/code-review/instruction.md').read_bytes()
        self.assertEqual(c.digest(data), '09eb147f793e4647949edd32dbad278f0554dfb56e0d46b699cd4c2c55bf0357')
        self.assertEqual(s.check_entry(data, 'code-review'), [])
        self.assertTrue(s.check_package(self.package('code-review', data))['valid'])
        self.assertFalse(s.check_package(self.package('review', data))['valid'])

    def test_refusals(self):
        missing = self.root / 'empty'
        missing.mkdir()
        cases = {
            'missing': (missing, 'Missing required file: SKILL.md'),
            'relative': (Path('my-skill'), 'absolute'),
            'absent': (self.root / 'absent', 'absolute'),
            'mismatch': (self.package('wrong-name', skill('right-name')), 'must match skill name'),
            'activation': (self.package('activation', **{'AGENTS.md': b'x'}), 'active instruction filename'),
            'lowercase-entry': (self.root / 'lower', 'Missing required file: SKILL.md'),
        }
        (self.root / 'lower').mkdir()
        (self.root / 'lower/skill.md').write_bytes(skill('lower'))
        link = self.package('linked')
        os.symlink(ROOT / 'LICENSE', link / 'LICENSE')
        cases['symlink'] = (link, 'symlink in package: LICENSE')
        big = self.package('big', **{f'r{i}.md': b'x' * 20000 for i in range(30)})
        cases['bytes'] = (big, f'package exceeds {s.MAX_PACKAGE_BYTES} bytes')
        many = self.package('many', **{f'r{i}.md': b'x' for i in range(s.MAX_PACKAGE_FILES)})
        cases['count'] = (many, f'package exceeds {s.MAX_PACKAGE_FILES} files')
        for label, (path, fragment) in cases.items():
            with self.subTest(label):
                report = s.check_package(path)
                self.assertFalse(report['valid'])
                self.assertTrue(any(fragment in e for e in report['errors']), report['errors'])
                self.assertNotIn('package_sha256', report)

    def test_cli_reports_and_refuses_without_writing(self):
        good = self.package()
        bad = self.package('bad-skill', skill('bad-skill', extra='allowed-tools: Bash\n'))
        before = sorted(p.as_posix() for p in self.root.rglob('*'))
        run = lambda *a: subprocess.run([sys.executable, str(CLI), *map(str, a)], capture_output=True, text=True, timeout=60)
        result = run('validate-skill', '--package', good)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['valid'])
        result = run('validate-skill', '--package', bad)
        self.assertEqual(result.returncode, 2)
        self.assertIn('allowed-tools pre-approval', json.loads(result.stdout)['errors'][0])
        for args in (('validate-skill',), ('validate-skill', '--package', good, '--project', self.root),
                     ('list', '--package', good)):
            result = run(*args)
            self.assertEqual(result.returncode, 1, args)
            self.assertIn('context-ai:', result.stderr)
        self.assertEqual(sorted(p.as_posix() for p in self.root.rglob('*')), before)


class Delivery(unittest.TestCase):
    def test_resolution_refuses_a_rehashed_but_invalid_pinned_package(self):
        # Hash agreement alone is not enough: the pinned entry must still be a valid package.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ('sourced/mattpocock', 'procedures', 'core', 'sourced/ponytail'):
                shutil.copytree(ROOT / name, root / name)
            for name in ('resources.yaml', 'LICENSE'):
                shutil.copyfile(ROOT / name, root / name)
            entry = root / 'sourced/mattpocock/code-review/instruction.md'
            entry.write_bytes(entry.read_bytes().replace(b'name: code-review', b'name: review', 1))
            lock = json.loads((ROOT / 'sources.lock.json').read_text())
            pin = next(x for x in lock['sources'] if x['id'] == 'mattpocock')
            pin['files']['sourced/mattpocock/code-review/instruction.md'] = c.digest(entry.read_bytes())
            (root / 'sources.lock.json').write_text(json.dumps(lock))
            with patch.object(c, 'ROOT', root):
                files = c.resources(['procedures/review.md'])
                with self.assertRaisesRegex(c.Invalid, "invalid skill package .*must match skill name 'review'"):
                    c.source_notices(files)

    def test_generated_routers_are_valid_named_packages(self):
        with tempfile.TemporaryDirectory() as td:
            lock, files = c.resolve(['essentials'], Path(td).resolve(), 'both', extras=['context-output'])
            routers = {k: v for k, v in c.materialized(lock, files).items() if k.endswith('/SKILL.md')}
            self.assertTrue(routers)
            for name, data in routers.items():
                self.assertEqual(s.check_entry(data, Path(name).parent.name), [], name)
            lock['capabilities']['context-output']['definition']['description'] = 'x' * 1025
            with self.assertRaisesRegex(c.Invalid, 'invalid skill package router context-output: Description exceeds'):
                c.materialized(lock, files)


class ReviewEquipment(unittest.TestCase):
    """The public review-equipment profile through the real CLI and lifecycle."""
    PROFILE = ROOT / 'examples/library-profiles/review-equipment.yaml'
    AGENTS = b'# Shop\nRun python3 -m unittest. Authored instructions stay exact.\n'

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def consumer(self, name):
        path = self.root / name
        path.mkdir()
        (path / 'AGENTS.md').write_bytes(self.AGENTS)
        (path / 'app.py').write_bytes(b'print("owned by the project")\n')
        return path

    def cli(self, *args, code=0):
        result = subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, code, result.stderr)
        return json.loads(result.stdout) if code == 0 else result.stderr

    def test_comparison_distinguishes_choices_and_evidence_scope(self):
        picked = self.cli('select', '--library-profile', self.PROFILE)
        self.assertEqual(picked['capabilities'], ['context-code-review', 'context-tdd'])
        review = next(row for row in picked['comparison'] if row['concern'] == 'code-review')
        self.assertEqual(review['selected'], 'matt-pocock-code-review')
        options = {o['id']: o for o in review['options']}
        self.assertEqual(set(options), {'matt-pocock-code-review', 'context-review'})
        for option in options.values():
            scopes = [e['scope'] for e in option['evidence']]
            self.assertTrue(any(s.startswith('Source-supported') for s in scopes), scopes)
            self.assertTrue(any(s.startswith('Locally tested') for s in scopes), scopes)
        observed = options['matt-pocock-code-review']['evidence'][-1]
        self.assertTrue(observed['scope'].startswith('Native pair observed'), observed)
        self.assertEqual(observed['checked_ref'], '0042b0c6b1cc4b35ea8fd14f2916e6a02331dc83')
        self.assertIn('no quality uplift', ' '.join(observed['weaknesses']).lower())
        self.assertIn('does not judge other tasks', ' '.join(observed['weaknesses']))

    def test_preview_apply_verify_refresh_and_undo_preserve_authored_bytes(self):
        project = self.consumer('consumer')
        args = ('--library-profile', self.PROFILE, '--project', project, '--provider', 'both')
        preview = self.cli('plan', *args)['delivery']
        resources = preview['resolution']['resources']
        self.assertEqual(resources['sourced/mattpocock/code-review/instruction.md'],
                         '09eb147f793e4647949edd32dbad278f0554dfb56e0d46b699cd4c2c55bf0357')
        self.assertIn('sourced/mattpocock/LICENSE', resources)
        self.assertIn('procedures/code-review.md', resources)
        self.assertIn('mattpocock', {pin['id'] for pin in preview['upstream_pins']})
        for host in ('.agents', '.claude'):
            self.assertIn(host + '/skills/context-code-review/SKILL.md', preview['additions'])
        # No host settings, hooks, permissions or MCP configuration are proposed.
        self.assertFalse([w for w in preview['writes'] if 'settings' in w or w.startswith('.codex') or 'mcp' in w.lower()])
        self.assertEqual(preview['conflicts'], [])
        self.cli('apply', *args)
        self.assertEqual(self.cli('verify', '--project', project)['owned_files'], len(resources) + 4)
        for host in ('.agents', '.claude'):
            for name in ('context-code-review', 'context-tdd'):
                self.assertTrue(s.check_package(project / host / 'skills' / name)['valid'])
        installed = project / '.context-ai/resources/sourced/mattpocock/code-review/instruction.md'
        self.assertEqual(c.digest(installed.read_bytes()), resources['sourced/mattpocock/code-review/instruction.md'])
        refreshed = self.cli('refresh', *args)['delivery']
        self.assertEqual([refreshed[k] for k in ('additions', 'replacements', 'removals', 'changes', 'conflicts')],
                         [[], [], [], [], []])
        # Authored instructions outside the managed block survive an exact undo.
        agents = project / 'AGENTS.md'
        agents.write_bytes(agents.read_bytes() + b'\n## Team note\nAuthored after apply.\n')
        authored = agents.read_bytes()
        self.assertEqual(self.cli('undo', '--project', project), {'undone': True, 'preserved_conflicts': []})
        block = authored[authored.index(c.BEGIN.encode()):authored.index(c.END.encode()) + len(c.END) + 1]
        self.assertEqual(agents.read_bytes(), authored.replace(block, b'', 1))
        # Empty directories may remain after undo; no owned file does.
        self.assertEqual(sorted(p.relative_to(project).as_posix() for p in project.rglob('*') if p.is_file()),
                         ['AGENTS.md', 'app.py'])
        self.assertEqual((project / 'app.py').read_bytes(), b'print("owned by the project")\n')

    def test_owned_alternative_installs_and_foreign_edits_are_preserved(self):
        value = c.parse_yaml(self.PROFILE.read_text())
        value['id'] = 'review-owned'
        value['selections'][0] = {'option': 'context-review', 'concern': 'code-review',
                                  'reason': 'Owned consequential-change review.'}
        alternative = self.root / 'owned.yaml'
        alternative.write_text(json.dumps(value))
        project = self.consumer('owned')
        args = ('--library-profile', alternative, '--project', project, '--provider', 'codex')
        applied = self.cli('apply', *args)
        self.assertEqual(applied['selection']['capabilities'], ['context-review', 'context-tdd'])
        self.cli('verify', '--project', project)
        self.assertTrue(s.check_package(project / '.agents/skills/context-review')['valid'])
        edited = project / '.context-ai/resources/procedures/review.md'
        edited.write_bytes(edited.read_bytes() + b'\nLocal reviewer note.\n')
        before = edited.read_bytes()
        self.assertIn('managed file drift', self.cli('verify', '--project', project, code=1))
        self.assertIn('user file conflict: .context-ai/resources/procedures/review.md', self.cli('apply', *args, code=1))
        result = self.cli('undo', '--project', project)
        self.assertEqual(result, {'undone': False, 'preserved_conflicts': ['.context-ai/resources/procedures/review.md']})
        self.assertEqual(edited.read_bytes(), before)
        self.assertEqual((project / 'AGENTS.md').read_bytes(), self.AGENTS)
        self.assertFalse((project / '.agents/skills/context-review/SKILL.md').exists())
        self.assertTrue(json.loads((project / '.context-ai/lock.json').read_text())['undo_pending'])


if __name__ == '__main__':
    unittest.main()
