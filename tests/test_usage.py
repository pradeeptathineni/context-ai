"""Native counters and opt-in delivery; no inference or session reads."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import context_usage as usage
import context_ai as c


def stream(*events):
    return ('\n'.join(json.dumps(event) for event in events) + '\n').encode()


def completed(input=100, cached=60, output=20, reasoning=5):
    return {'type': 'turn.completed', 'usage': {'input_tokens': input,
        'cached_input_tokens': cached, 'output_tokens': output, 'reasoning_output_tokens': reasoning}}


def snapshot(input, turn='turn', thread='thread'):
    values = {'inputTokens': input, 'cachedInputTokens': input // 2,
              'outputTokens': 10, 'reasoningOutputTokens': 4, 'totalTokens': input + 10}
    return {'method': 'thread/tokenUsage/updated', 'params': {
        'threadId': thread, 'turnId': turn,
        'tokenUsage': {'total': values, 'last': dict(values)}}}


class Usage(unittest.TestCase):
    def test_completed_cli_keeps_fields_without_overlapping_sum_or_identity_inference(self):
        result = usage.receipt(stream(completed()), 'codex-exec', 'gpt-6.1-sol', 'high')
        self.assertEqual([result['tokens'][k] for k in usage.FIELDS[:4]], [100, 60, 20, 5])
        for key in ('served_model', 'cost', 'stage_tokens'):
            self.assertIsNone(result[key])
        self.assertIsNone(result['tokens']['total_tokens'])

    def test_duplicate_terminal_not_added_and_equal_separate_turns_remain_distinct(self):
        end = completed()
        result = usage.receipt(stream({'type': 'turn.started'}, end, end,
                                     {'type': 'turn.started'}, end), 'codex-exec')
        self.assertEqual(result['duplicates'], 1)
        self.assertEqual(len(result['observations']), 2)
        self.assertEqual(result['tokens']['input_tokens'], 100)

    def test_missing_failed_and_interrupted_turn_do_not_inherit_prior_usage(self):
        for tail, status in [({'type': 'turn.failed'}, 'failed'), ({'type': 'turn.started'}, 'interrupted')]:
            with self.subTest(status=status):
                result = usage.receipt(stream(completed(), tail), 'codex-exec')
                self.assertEqual(result['status'], status)
                self.assertEqual(result['usage_state'], 'missing')
                self.assertEqual(result['observations'][0]['tokens']['input_tokens'], 100)
        self.assertEqual(usage.receipt(stream({'type': 'turn.completed'}), 'codex-exec')['usage_state'], 'missing')

    def test_zero_is_reported_and_partial_fields_not_filled(self):
        result = usage.receipt(stream({'type': 'turn.completed', 'usage': {'input_tokens': 0}}), 'codex-exec')
        self.assertEqual(result['usage_state'], 'reported')
        self.assertEqual(result['tokens']['input_tokens'], 0)
        self.assertIsNone(result['tokens']['output_tokens'])

    def test_cumulative_app_delta_and_duplicates(self):
        first, last = snapshot(100), snapshot(150)
        result = usage.receipt(stream(first, first, last), 'app-server')
        self.assertEqual(result['duplicates'], 1)
        self.assertEqual(result['tokens']['input_tokens'], 150)
        self.assertEqual(result['between_snapshots']['input_tokens'], 50)
        self.assertEqual(result['observations'][-1]['last']['input_tokens'], 150)
        self.assertEqual(result['status'], 'interrupted')
        self.assertIsNone(usage.receipt(stream(first), 'app-server')['between_snapshots'])

    def test_counter_decrease_prevents_delta_even_after_growth(self):
        result = usage.receipt(stream(snapshot(100), snapshot(20), snapshot(150)), 'app-server')
        self.assertTrue(result['counter_discontinuity'])
        self.assertIsNone(result['between_snapshots'])
        self.assertTrue(usage.receipt(stream(completed(100), completed(20)), 'codex-exec')['counter_discontinuity'])

    def test_no_cross_thread_aggregation(self):
        for raw in (stream(snapshot(100), snapshot(150, thread='other')),
                    stream(snapshot(100), {'method': 'turn/completed', 'params': {
                        'threadId': 'other', 'turn': {'status': 'completed'}}}),
                    stream({'method': 'turn/completed', 'params': {
                        'threadId': 'other', 'turn': {'status': 'completed'}}}, snapshot(100)),
                    stream({'type': 'thread.started', 'thread_id': 'a'}, {'type': 'thread.started', 'thread_id': 'b'})):
            with self.subTest(raw=raw), self.assertRaises(usage.Invalid):
                usage.receipt(raw, 'app-server' if b'"method"' in raw else 'codex-exec')

    def test_app_completion_then_new_turn_is_interrupted_with_thread_total_preserved(self):
        result = usage.receipt(stream(snapshot(100), {'method': 'turn/completed', 'params': {
            'threadId': 'thread', 'turn': {'status': 'completed'}}}, {'method': 'turn/started', 'params': {
            'threadId': 'thread', 'turn': {'status': 'inProgress'}}}), 'app-server')
        self.assertEqual(result['status'], 'interrupted')
        self.assertEqual(result['tokens']['input_tokens'], 100)

    def test_content_excluded_and_raw_preserved(self):
        raw = stream({'type': 'item.completed', 'item': {'text': 'PRIVATE PROMPT', 'command': 'PRIVATE COMMAND'}}, completed())
        original = raw[:]
        self.assertNotIn('PRIVATE', json.dumps(usage.receipt(raw, 'codex-exec')))
        self.assertEqual(raw, original)

    def test_negative_boolean_fractional_and_huge_counters_fail(self):
        for value in (-1, True, 1.5, '5', 2**63):
            with self.subTest(value=value), self.assertRaises(usage.Invalid):
                usage.receipt(stream({'type': 'turn.completed', 'usage': {'input_tokens': value}}), 'codex-exec')

    def test_duplicate_keys_malformed_truncated_and_future_versions_fail(self):
        for raw in (b'{"type":"turn.completed","usage":{"input_tokens":1,"input_tokens":2}}',
                    b'{"type":"turn.completed",', b'{"extra":NaN}',
                    stream({'schema_version': 2, 'type': 'turn.completed'})):
            with self.subTest(raw=raw), self.assertRaises(usage.Invalid):
                usage.receipt(raw, 'codex-exec')
        self.assertRaises(usage.Invalid, usage.receipt, b' ' * (usage.MAX_BYTES + 1), 'codex-exec')

    def metric(self):
        return {'schema_version': 1, 'runId': 'run', 'status': 'completed', 'usage': {
            'elapsedMs': 64000, 'providerUsage': {'provider': completed()['usage'],
                'model': 'gpt-6.1-sol', 'effort': 'high', 'servedModel': None,
                'stages': {'acquisitionMs': 5, 'nativeSessionMs': 63900},
                'termination': {'exitCode': 0, 'signal': None, 'trigger': None}}}}

    def test_projection_timings_and_cancelled_missing_receipt(self):
        metric = self.metric()
        metric['usage']['providerUsage']['actionCounts'] = {'toolCalls': 5, 'reads': 4}
        result = usage.receipt(json.dumps(metric).encode(), 'native-metrics')
        self.assertEqual(result['stages_ms']['nativeSessionMs'], 63900)
        self.assertEqual(result['elapsed_ms'], 64000)
        self.assertIsNone(result['stage_tokens'])
        self.assertEqual(result['counts']['native_reads'], 4)
        self.assertEqual(result['counts']['native_tool_calls'], 5)
        self.assertIsNone(result['counts']['documents'])
        metric['status'] = 'cancelled'; metric['usage']['providerUsage']['provider'] = None
        metric['usage']['providerUsage']['termination'] = {'exitCode': None, 'signal': 'SIGKILL', 'trigger': 'request_aborted'}
        result = usage.receipt(json.dumps(metric).encode(), 'native-metrics')
        self.assertEqual(result['usage_state'], 'missing')
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(result['termination']['trigger'], 'request_aborted')

    def test_projection_versions_and_conflicting_timers_fail(self):
        metric = self.metric()
        for version in (2, True, None):
            invalid = copy.deepcopy(metric); invalid['schema_version'] = version
            self.assertRaises(usage.Invalid, usage.receipt, json.dumps(invalid).encode(), 'native-metrics')
        metric['usage']['stages'] = {'nativeSessionMs': 12}
        self.assertRaises(usage.Invalid, usage.receipt, json.dumps(metric).encode(), 'native-metrics')

    def test_empty_arrays_do_not_masquerade_as_missing_metrics(self):
        for key in ('usage', 'providerUsage', 'stages'):
            metric = self.metric()
            if key == 'usage': metric['usage'] = []
            else: metric['usage'][key] = []
            with self.subTest(key=key), self.assertRaises(usage.Invalid):
                usage.receipt(json.dumps(metric).encode(), 'native-metrics')

    def test_cli_read_only_symlink_refusal_and_metrics_output(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td); source = p / 'events.jsonl'; raw = stream(completed()); source.write_bytes(raw)
            command = [sys.executable, str(ROOT / 'scripts/context_usage.py'), str(source), '--format', 'codex-exec']
            result = subprocess.run(command, capture_output=True, check=True)
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(list(p.iterdir()), [source])
            self.assertEqual(json.loads(result.stdout)['tokens']['input_tokens'], 100)
            link = p / 'alias'; link.symlink_to(source); command[2] = str(link)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)

    def test_opt_in_delivery_empty_default_and_edited_helper_preservation(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td).resolve(); (project / 'AGENTS.md').write_text('User rules\n')
            lock, files = c.resolve([], project, 'both')
            self.assertNotIn('scripts/context_usage.py', files)
            lock, files = c.resolve([], project, 'both', extras=['context-usage'])
            self.assertIn('scripts/context_usage.py', files)
            self.assertNotIn('scripts/context_output.py', files)
            c.apply(project, lock, files); before = (project / '.context-ai/lock.json').read_bytes()
            c.apply(project, lock, files)
            self.assertEqual((project / '.context-ai/lock.json').read_bytes(), before)
            helper = project / '.context-ai/resources/scripts/context_usage.py'
            events = project / 'supplied.jsonl'; events.write_bytes(stream(completed()))
            result = subprocess.run([sys.executable, str(helper), str(events), '--format', 'codex-exec'],
                                    capture_output=True, check=True)
            self.assertEqual(json.loads(result.stdout)['tokens']['input_tokens'], 100)
            self.assertEqual(c.verify(project)['project_checks'], 'not_run')
            helper.write_bytes(helper.read_bytes() + b'\n# user annotation\n'); edited = helper.read_bytes()
            self.assertFalse(c.undo(project)['undone'])
            self.assertEqual(helper.read_bytes(), edited)
            self.assertEqual((project / 'AGENTS.md').read_text(), 'User rules\n')


if __name__ == '__main__':
    unittest.main()
