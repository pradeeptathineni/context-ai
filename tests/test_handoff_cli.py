"""Exercise the trusted CLI boundary without granting request-side apply authority."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HandoffCommand(unittest.TestCase):
    def test_read_only_request_cannot_apply_or_expand_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp).resolve()
            request = target / 'request.json'
            value = {'schema_version': 1, 'request_id': 'cli-preview', 'method': 'plan',
                     'profile_id': 'home-lab', 'project_ref': {'id': 'fixture', 'source_ref': 'https://github.com/example/fixture'},
                     'constraints': [], 'findings': [{'id': 'context-opportunity:home-lab:fe1fe811eabab52d',
                                                     'outcome': 'Consider the retained observation', 'evidence_refs': ['README.md']}]}
            request.write_text(json.dumps(value))
            command = [sys.executable, str(ROOT / 'scripts/context_ai.py'), 'handoff', '--input', str(request),
                       '--project', str(target), '--allow-root', str(target), '--project-id', 'fixture',
                       '--profile', 'home-lab', '--source-ref', value['project_ref']['source_ref']]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            preview = json.loads(result.stdout)
            self.assertEqual(preview['status'], 'planned')
            self.assertFalse(preview['applied'])
            self.assertFalse((target / '.context-ai').exists())
            public = subprocess.run(command + ['--public'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(public.returncode, 0, public.stderr)
            exported = json.loads(public.stdout)
            self.assertEqual(exported['local_state'], 'unknown')
            self.assertNotIn(str(target), public.stdout)
            self.assertNotIn('plan_id', exported)
            value['method'] = 'apply'
            request.write_text(json.dumps(value))
            denied = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("plan and status only", denied.stderr)
            value['method'] = 'plan'
            request.write_text(json.dumps(value))
            execute = subprocess.run(command + ['--execute'], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(execute.returncode, 0)
            self.assertIn("read-only", execute.stderr)
            self.assertFalse((target / '.context-ai').exists())
