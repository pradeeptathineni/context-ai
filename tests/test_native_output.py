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

    def test_short_failure_without_keywords_is_complete_even_over_line_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw'
            output=''.join(f'{i}: step\n' for i in range(45))+'invalid schema: required key absent\n'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/context_output.py'),'run','--log',str(raw),
                                   '--lines','2','--',sys.executable,'-c',f'import sys;sys.stdout.write({output!r});sys.exit(23)'],capture_output=True)
            report=json.loads(result.stdout)
            self.assertEqual(result.returncode,23)
            self.assertIn('complete',report['view'])
            self.assertEqual([row['text'] for row in report['evidence']],output.splitlines())
            self.assertEqual(raw.read_bytes(),output.encode())
            self.assertLessEqual(len(result.stdout),4097)
            self.assertEqual(json.loads(raw.with_name('raw.status.json').read_text())['exit_status'],23)

    def test_long_failure_tail_and_recovery_of_unmatched_middle_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw'
            output='error: earlier recoverable attempt\n'+'progress\n'*3000+'invalid schema: required key absent\n'+'progress\n'*3000+'process stopped with status 23\n'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/context_output.py'),'run','--log',str(raw),
                                   '--',sys.executable,'-c',f'import sys;sys.stdout.write({output!r});sys.exit(23)'],capture_output=True)
            report=json.loads(result.stdout)
            self.assertEqual(result.returncode,23)
            self.assertIn('partial',report['view'])
            self.assertIn('failure tail',report['tail']['label'])
            self.assertEqual(report['tail']['evidence'][-1]['text'],'process stopped with status 23')
            self.assertEqual(report['tail']['evidence'][-1]['line'],6003)
            self.assertIn('earlier recoverable',str(report['evidence']))
            self.assertIn('inspect',report['retrieval'])
            self.assertLessEqual(len(result.stdout),4097)
            recovered=o.inspect(raw,queries=['required key'])
            self.assertIn('required key absent',str(recovered['evidence']))
            self.assertEqual(raw.read_bytes(),output.encode())

    def test_long_single_line_failure_keeps_final_suffix_with_multibyte_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw'
            output='error: '+'雪'*10000+' opaque terminal diagnosis\n'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/context_output.py'),'run','--log',str(raw),
                                   '--max-bytes','2048','--',sys.executable,'-c',f'import sys;sys.stdout.write({output!r});sys.exit(17)'],capture_output=True)
            report=json.loads(result.stdout)
            self.assertEqual(result.returncode,17)
            self.assertIn('error:',str(report['evidence']))
            self.assertIn('opaque terminal diagnosis',str(report['tail']['evidence']))
            self.assertTrue(report['tail']['evidence'][-1]['line_suffix_only'])
            self.assertLessEqual(len(result.stdout),2049)
            self.assertEqual(raw.read_bytes(),output.encode())

    def test_escaped_short_raw_that_cannot_fit_is_truthfully_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw'
            output=b'\x00'*700+b' terminal diagnosis\n'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/context_output.py'),'run','--log',str(raw),
                                   '--max-bytes','2048','--',sys.executable,'-c',f'import sys;sys.stdout.buffer.write({output!r});sys.exit(9)'],capture_output=True)
            report=json.loads(result.stdout)
            self.assertIn('partial',report['view'])
            self.assertIn('terminal diagnosis',str(report['tail']['evidence']))
            self.assertTrue(report['tail']['evidence'][-1]['line_suffix_only'])
            self.assertLessEqual(len(result.stdout),2049)
            self.assertEqual(raw.read_bytes(),output)

    def test_signal_status_is_retained_in_receipt_and_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw'
            code="import os,signal,sys;print('terminal diagnosis',flush=True);os.kill(os.getpid(),signal.SIGTERM)"
            result=subprocess.run([sys.executable,str(ROOT/'scripts/context_output.py'),'run','--log',str(raw),
                                   '--',sys.executable,'-c',code],capture_output=True)
            report=json.loads(result.stdout)
            self.assertEqual(result.returncode,143)
            self.assertEqual(report['exit_status'],-15)
            self.assertEqual(json.loads(raw.with_name('raw.status.json').read_text())['exit_status'],-15)
            self.assertEqual(report['evidence'][0]['text'],'terminal diagnosis')

    def test_failed_start_is_durable_without_fabricating_child_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/context_output.py'),'run','--log',str(raw),
                                   '--',str(Path(tmp)/'nonexistent')],capture_output=True)
            self.assertEqual(result.returncode,2)
            receipt=json.loads(raw.with_name('raw.status.json').read_text())
            self.assertEqual(receipt['execution'],'failed_to_start')
            self.assertIsNone(receipt['exit_status'])
            self.assertEqual(raw.read_bytes(),b'')

    def test_view_failure_cannot_replace_producer_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);raw=p/'raw';counter=p/'count'
            code=f"from pathlib import Path;import sys;Path({str(counter)!r}).write_text('once');print('FAILED cause');sys.exit(17)"
            args=[sys.executable,str(ROOT/'scripts/context_output.py'),'run','--log',str(raw),'--max-bytes','512','--query','x'*600,'--',sys.executable,'-c',code]
            result=subprocess.run(args,capture_output=True)
            self.assertEqual(result.returncode,17);self.assertEqual(counter.read_text(),'once')
            self.assertEqual(json.loads(result.stdout)['exit_status'],17)
            self.assertLessEqual(len(result.stdout),513)
            receipt=raw.with_name('raw.status.json');self.assertEqual(json.loads(receipt.read_text())['exit_status'],17)
            self.assertEqual(raw.read_bytes(),b'FAILED cause\n')
    def test_existing_receipt_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);raw=p/'raw';receipt=p/'raw.status.json';receipt.write_text('user data')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/context_output.py'),'run','--log',str(raw),'--',sys.executable,'-c',"raise SystemExit(23)"],capture_output=True)
            self.assertEqual(result.returncode,2);self.assertEqual(receipt.read_text(),'user data');self.assertFalse(raw.exists())
