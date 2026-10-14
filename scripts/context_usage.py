#!/usr/bin/env python3
"""Read supplied native token counters; never collect sessions or run inference."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

MAX_BYTES = 4_000_000
FIELDS = ('input_tokens', 'cached_input_tokens', 'output_tokens',
          'reasoning_output_tokens', 'cache_write_input_tokens', 'total_tokens')
CAMEL = dict(zip(FIELDS, ('inputTokens', 'cachedInputTokens', 'outputTokens',
                        'reasoningOutputTokens', 'cacheWriteInputTokens', 'totalTokens')))
STAGES = ('readinessMs', 'researchMs', 'answerReadyMs', 'inspectionMs',
          'firstValidatedMs', 'acquisitionMs', 'nativeSessionMs', 'validationMs')


class Invalid(ValueError):
    pass


def object_value(value):
    if not isinstance(value, dict):
        raise Invalid('expected an object')
    return value


def optional_object(value):
    return {} if value is None else object_value(value)


def number(value):
    if value is not None and (type(value) is not int or not 0 <= value <= 2**63 - 1):
        raise Invalid('counter must be a nonnegative integer or null')
    return value


def text(value):
    if value is not None and (not isinstance(value, str) or not 1 <= len(value) <= 256):
        raise Invalid('metadata must be bounded text or null')
    return value


def counters(value, camel=False):
    if value is None:
        return dict.fromkeys(FIELDS)
    value = object_value(value)
    return {key: number(value.get(CAMEL[key] if camel else key)) for key in FIELDS}


def missing(tokens):
    return all(value is None for value in tokens.values())


def decreasing(previous, current):
    return any(previous[key] is not None and current[key] is not None
               and current[key] < previous[key] for key in FIELDS)


def decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise Invalid('duplicate JSON field')
            value[key] = item
        return value
    def invalid_constant(value):
        raise Invalid('non-JSON numeric constant')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


def receipt(raw, format, requested_model=None, requested_effort=None):
    if len(raw) > MAX_BYTES:
        raise Invalid('input exceeds 4 MB boundary')
    result = {'schema_version': 1,
        'evidence': {'format': format, 'sha256': hashlib.sha256(raw).hexdigest()},
        'status': 'interrupted', 'requested_model': text(requested_model),
        'requested_effort': text(requested_effort), 'served_model': None,
        'run_id': None, 'thread_id': None, 'elapsed_ms': None, 'stages_ms': {},
        'termination': None, 'cost': None, 'stage_tokens': None,
        'tokens': dict.fromkeys(FIELDS), 'usage_state': 'missing',
        'semantics': None, 'observations': [], 'duplicates': 0,
        'counter_discontinuity': False, 'between_snapshots': None, 'counts': {},
        'limits': ['Reported counters only; missing is not zero.',
                   'Cached/reasoning breakdowns are not added again.',
                   'No quota, cost, context-size or stage-token conversion.']}
    try:
        if format == 'native-metrics':
            data = object_value(decode(raw))
            if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
                raise Invalid('unsupported metrics projection schema version')
            result['run_id'] = text(data.get('runId'))
            status = data.get('status')
            if status not in ('completed', 'partial', 'cancelled', 'failed', 'not_configured'):
                raise Invalid('unsupported result status')
            result['status'] = status
            usage = optional_object(data.get('usage'))
            provider = optional_object(usage.get('providerUsage'))
            result['tokens'] = counters(provider.get('provider'))
            result['requested_model'] = text(provider.get('model'))
            result['requested_effort'] = text(provider.get('effort'))
            result['served_model'] = text(provider.get('servedModel'))
            result['elapsed_ms'] = number(usage.get('elapsedMs'))
            for target, value in {'searches': usage.get('searches'),
                    'documents': usage.get('documents'), 'model_calls': usage.get('modelCalls'),
                    'native_sessions': provider.get('nativeSessions'),
                    'native_tool_calls': optional_object(provider.get('actionCounts')).get('toolCalls'),
                    'native_reads': optional_object(provider.get('actionCounts')).get('reads'),
                    'unclassified_native_tool_calls': optional_object(provider.get('actionCounts')).get('unclassifiedToolCalls')}.items():
                result['counts'][target] = number(value)
            for name in STAGES:
                source = optional_object(usage.get('stages'))
                native = optional_object(provider.get('stages'))
                # Ambiguous duplicate stage definitions are never silently chosen.
                if name in source and name in native and source[name] != native[name]:
                    raise Invalid('conflicting stage timing')
                value = source.get(name, native.get(name))
                if value is not None:
                    result['stages_ms'][name] = number(value)
            termination = provider.get('termination')
            if termination is not None:
                termination = object_value(termination)
                exit_code = termination.get('exitCode')
                if exit_code is not None and (type(exit_code) is not int or not -255 <= exit_code <= 255):
                    raise Invalid('invalid process exit code')
                result['termination'] = {'exit_code': exit_code,
                    'signal': text(termination.get('signal')), 'trigger': text(termination.get('trigger'))}
            result['semantics'] = 'native-session-reported; not individual provider calls'
        elif format in ('codex-exec', 'app-server'):
            previous, first, previous_identity, turn = None, None, None, 0
            last_known = dict.fromkeys(FIELDS)

            def bind(thread, conflict):
                if result['thread_id'] is not None and thread != result['thread_id']:
                    raise Invalid(conflict)
                result['thread_id'] = thread

            def observe(identity, current, observation):
                nonlocal previous, first, previous_identity
                if identity == previous_identity:
                    result['duplicates'] += 1
                    return
                previous_identity = identity
                if decreasing(last_known, current):
                    result['counter_discontinuity'] = True
                last_known.update({key: value for key, value in current.items() if value is not None})
                if first is None:
                    first = current
                result['observations'].append(observation)
                result['tokens'] = previous = current

            for line in raw.splitlines():
                if not line.strip():
                    continue
                event = object_value(decode(line))
                if 'schema_version' in event and (type(event['schema_version']) is not int or event['schema_version'] != 1):
                    raise Invalid('unsupported event envelope version')
                if format == 'codex-exec':
                    kind = event.get('type')
                    if kind == 'thread.started':
                        bind(text(event.get('thread_id')), 'one receipt cannot combine threads')
                    elif kind == 'turn.started':
                        turn += 1
                        result['status'] = 'interrupted'
                        # A later interrupted turn must not inherit prior usage as its own.
                        result['tokens'] = dict.fromkeys(FIELDS)
                    elif kind in ('turn.completed', 'turn.failed'):
                        result['status'] = 'completed' if kind == 'turn.completed' else 'failed'
                        current = counters(event.get('usage'))
                        observe((turn, kind, json.dumps(current, sort_keys=True)), current,
                                {'turn_ordinal': turn, 'tokens': current})
                    # Item text, tool arguments and error messages are never retained.
                else:
                    method = event.get('method')
                    if method == 'thread/tokenUsage/updated':
                        params = object_value(event.get('params'))
                        thread = text(params.get('threadId'))
                        if thread is None:
                            raise Invalid('usage notification needs thread identity')
                        bind(thread, 'one receipt cannot combine threads')
                        usage = object_value(params.get('tokenUsage'))
                        current = counters(usage.get('total'), camel=True)
                        last = counters(usage.get('last'), camel=True)
                        turn_id = text(params.get('turnId'))
                        observe((thread, turn_id, json.dumps([current, last], sort_keys=True)), current,
                                {'turn_id': turn_id, 'total': current, 'last': last})
                    elif method in ('turn/started', 'turn/completed'):
                        params = object_value(event.get('params'))
                        bind(text(params.get('threadId')), 'completion belongs to another thread')
                        if result['thread_id'] is None:
                            raise Invalid('turn notification needs thread identity')
                        state = object_value(params.get('turn')).get('status')
                        if method == 'turn/started':
                            result['status'] = 'interrupted'
                            continue
                        if state not in ('completed', 'interrupted', 'failed'):
                            raise Invalid('unsupported turn completion state')
                        result['status'] = state
            if format == 'app-server':
                result['semantics'] = 'thread cumulative; last snapshot is not an additive event'
                if first is not None and len(result['observations']) > 1 and not result['counter_discontinuity']:
                    result['between_snapshots'] = {key: previous[key] - first[key]
                        if previous[key] is not None and first[key] is not None else None for key in FIELDS}
            else:
                result['semantics'] = 'terminal reported counter; per-call/resume baseline unknown'
        else:
            raise Invalid('unsupported input format')
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, AttributeError):
        raise Invalid('invalid native metrics input') from None
    result['usage_state'] = 'missing' if missing(result['tokens']) else 'reported'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--format', required=True, choices=['codex-exec', 'app-server', 'native-metrics'])
    parser.add_argument('--requested-model')
    parser.add_argument('--requested-effort')
    args = parser.parse_args()
    try:
        if args.input.is_symlink() or not args.input.is_file():
            raise Invalid('input must be a supplied regular file')
        with args.input.open('rb') as source:
            raw = source.read(MAX_BYTES + 1)
        print(json.dumps(receipt(raw, args.format, args.requested_model, args.requested_effort),
                         indent=2, sort_keys=True))
    except (ValueError, OSError):
        print('Usage input refused; check format, counters, version and regular-file/size boundary.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
