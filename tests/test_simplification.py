"""Usage receipts keep observation, duplicate and thread-scope behavior exactly."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import context_usage as usage


def stream(*events):
    return ('\n'.join(json.dumps(event) for event in events) + '\n').encode()


def tokens(input=None, cached=None, output=None, reasoning=None, write=None, total=None):
    return dict(zip(usage.FIELDS, (input, cached, output, reasoning, write, total)))


def snapshot(input, turn='turn', thread='thread'):
    values = {'inputTokens': input, 'cachedInputTokens': input // 2,
              'outputTokens': 10, 'reasoningOutputTokens': 4, 'totalTokens': input + 10}
    return {'method': 'thread/tokenUsage/updated', 'params': {
        'threadId': thread, 'turnId': turn,
        'tokenUsage': {'total': values, 'last': dict(values)}}}


def turn(method, status, thread='thread'):
    return {'method': method, 'params': {'threadId': thread, 'turn': {'status': status}}}


def projection(result):
    return {key: result[key] for key in ('thread_id', 'status', 'duplicates', 'counter_discontinuity',
            'observations', 'tokens', 'between_snapshots', 'usage_state')}


class UsageReceiptBehavior(unittest.TestCase):
    def test_codex_exec_observations_duplicates_and_turn_reset(self):
        end = {'type': 'turn.completed', 'usage': {'input_tokens': 100,
               'cached_input_tokens': 60, 'output_tokens': 20, 'reasoning_output_tokens': 5}}
        full = tokens(100, 60, 20, 5)
        result = usage.receipt(stream({'type': 'thread.started', 'thread_id': None},
            {'type': 'thread.started', 'thread_id': 'a'}, {'type': 'turn.started'}, end, end,
            {'type': 'turn.failed'}, {'type': 'turn.started'}, end), 'codex-exec')
        self.assertEqual(projection(result), {
            'thread_id': 'a', 'status': 'completed', 'duplicates': 1, 'counter_discontinuity': False,
            'observations': [{'turn_ordinal': 1, 'tokens': full},
                             {'turn_ordinal': 1, 'tokens': tokens()},
                             {'turn_ordinal': 2, 'tokens': full}],
            'tokens': full, 'between_snapshots': None, 'usage_state': 'reported'})

    def test_app_server_observations_duplicates_and_cumulative_delta(self):
        result = usage.receipt(stream(snapshot(100, 't1'), snapshot(100, 't1'),
            turn('turn/started', 'inProgress'), snapshot(100, 't2'), snapshot(150, 't2'),
            turn('turn/completed', 'interrupted')), 'app-server')
        low, high = tokens(100, 50, 10, 4, None, 110), tokens(150, 75, 10, 4, None, 160)
        self.assertEqual(projection(result), {
            'thread_id': 'thread', 'status': 'interrupted', 'duplicates': 1, 'counter_discontinuity': False,
            'observations': [{'turn_id': 't1', 'total': low, 'last': low},
                             {'turn_id': 't2', 'total': low, 'last': low},
                             {'turn_id': 't2', 'total': high, 'last': high}],
            'tokens': high, 'between_snapshots': tokens(50, 25, 0, 0, None, 50), 'usage_state': 'reported'})

    def test_last_event_wins_after_a_decrease_and_blocks_delta(self):
        result = usage.receipt(stream(snapshot(150), snapshot(100)), 'app-server')
        self.assertEqual(result['tokens']['input_tokens'], 100)
        self.assertTrue(result['counter_discontinuity'])
        self.assertIsNone(result['between_snapshots'])

    def test_thread_scope_refusals_keep_their_precedence(self):
        cases = [
            ('app-server', [snapshot(100, thread=None)], 'usage notification needs thread identity'),
            ('app-server', [snapshot(100), snapshot(100, thread=None)], 'usage notification needs thread identity'),
            ('app-server', [snapshot(100), snapshot(150, thread='other')], 'one receipt cannot combine threads'),
            ('app-server', [turn('turn/completed', 'completed', None)], 'turn notification needs thread identity'),
            ('app-server', [snapshot(100), turn('turn/completed', 'completed', None)], 'completion belongs to another thread'),
            ('app-server', [snapshot(100), turn('turn/started', 'inProgress', 'other')], 'completion belongs to another thread'),
            ('app-server', [turn('turn/completed', 'completed', 'other'), snapshot(100)], 'one receipt cannot combine threads'),
            ('codex-exec', [{'type': 'thread.started', 'thread_id': 'a'},
                            {'type': 'thread.started', 'thread_id': 'b'}], 'one receipt cannot combine threads'),
            ('codex-exec', [{'type': 'thread.started', 'thread_id': 'a'},
                            {'type': 'thread.started', 'thread_id': None}], 'one receipt cannot combine threads'),
        ]
        for format, events, message in cases:
            with self.subTest(events=events), self.assertRaisesRegex(usage.Invalid, '^' + message + '$'):
                usage.receipt(stream(*events), format)

    def test_same_thread_and_unsupported_completion_state(self):
        result = usage.receipt(stream(turn('turn/completed', 'failed'), snapshot(100)), 'app-server')
        self.assertEqual((result['thread_id'], result['status']), ('thread', 'failed'))
        with self.assertRaisesRegex(usage.Invalid, 'unsupported turn completion state'):
            usage.receipt(stream(turn('turn/completed', 'inProgress')), 'app-server')


if __name__ == '__main__':
    unittest.main()
