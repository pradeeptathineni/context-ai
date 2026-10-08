"""Meaningful zero-selection lifecycle and pre-exposure capture/retrieval checks."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import context_ai as c
import context_output as o
ROOT=Path(__file__).resolve().parents[1]

class NativeOutput(unittest.TestCase):
    def test_zero_selection_keeps_lifecycle_and_no_task_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'AGENTS.md').write_text('Keep my project.\n')
            with patch.object(c,'discover_command',side_effect=AssertionError('unneeded probe')):
                lock,files=c.resolve([],p,'both')
                self.assertEqual(set(files),{'LICENSE'})
                self.assertEqual(c.plan(p,lock,files)['selection_outcome'],'native-sufficient')
                c.apply(p,lock,files);c.verify(p)
                self.assertFalse(list((p/'.agents').rglob('SKILL.md')) if (p/'.agents').exists() else [])
                self.assertNotIn('read',c.router(lock).lower())
                c.undo(p)
            self.assertEqual((p/'AGENTS.md').read_text(),'Keep my project.\n')
    def test_native_packet_needs_no_prior_art_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(c,'discover_command',side_effect=AssertionError('unneeded probe')):
                result=c.task_packet({'schema_version':1,'task':'Fix existing spelling','verification':['Check changed text']},Path(tmp))
            self.assertEqual(result['selection_outcome'],'native-sufficient');self.assertEqual(result['context']['reads'],[])
            self.assertEqual(result['writes'],[])
    def test_narrow_resource_delivery_is_usable_and_edited_file_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);lock,files=c.resolve([],p,'both',extras=['context-output'])
            self.assertEqual(set(files),{'LICENSE','procedures/output.md','scripts/context_output.py'})
            c.apply(p,lock,files)
            script=p/'.context-ai/resources/scripts/context_output.py'
            raw=p/'raw.log';raw.write_text('noise\nCaused by invalid header\nnoise\n')
            result=subprocess.run([sys.executable,str(script),'inspect',str(raw),'--query','invalid'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0);self.assertIn('invalid header',result.stdout)
            script.write_text(script.read_text()+'# user edit\n')
            c.undo(p);self.assertTrue(script.exists());self.assertTrue(raw.exists())
    def test_capture_once_nonzero_and_raw_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);counter=p/'calls';raw=p/'raw'
            code=f"from pathlib import Path; import sys; Path({str(counter)!r}).write_text('1'); print('noise\\n'*3000+'Caused by invalid schema\\nassertion failed'); sys.stderr.write('stderr preserved\\n');sys.exit(23)"
            args=[sys.executable,str(ROOT/'scripts/context_output.py'),'run','--log',str(raw),'--',sys.executable,'-c',code]
            result=subprocess.run(args,capture_output=True)
            self.assertEqual(result.returncode,23);self.assertEqual(counter.read_text(),'1')
            view=json.loads(result.stdout);self.assertEqual(view['exit_status'],23)
            self.assertLessEqual(len(result.stdout),4097);self.assertIn(b'stderr preserved',raw.read_bytes())
            self.assertIn('invalid schema',str(view['evidence']))
            again=subprocess.run(args,capture_output=True);self.assertEqual(again.returncode,2)
            self.assertEqual(counter.read_text(),'1')
            retrieved=o.inspect(raw,start=3001,lines=5);self.assertTrue(retrieved['evidence'])
    def test_giant_line_bounded_and_partial_truthful(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw';raw.write_bytes(b'x'*2000000+b'error hidden suffix\nerror visible\n')
            result=o.inspect(raw,queries=['error'],max_bytes=1024)
            self.assertLessEqual(len(json.dumps(result,ensure_ascii=False).encode()),1024)
            self.assertEqual(result['raw_lines'],2);self.assertEqual(result['matches_in_scanned_prefixes'],1)
            self.assertIn('partial',result['view'])
