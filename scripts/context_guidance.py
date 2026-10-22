"""Select declared guidance from known task paths without reading task contents.

Applicability is adapted from Continue at 5522c6f; see sourced/continue/rules/NOTICE.md.
"""

from fnmatch import fnmatchcase
from functools import lru_cache
from pathlib import Path

from context_ai import Invalid, digest, inside, parse_yaml, validate_schema

MAX_RULES = 64
MAX_MANIFEST_BYTES = 65536


class GuidanceConflict(Invalid):
    def __init__(self, topic, path, rules):
        super().__init__('conflicting guidance at equal precedence')
        self.details = {'topic': topic, 'task_file': path,
                        'rules': [{k: rule[k] for k in ('scope', 'id', 'path')} for rule in rules]}


def task_paths(project, files):
    """Accept new or existing files, but reject escapes and symlink ancestors."""
    if not isinstance(files, (list, tuple)) or len(files) > MAX_RULES:
        raise Invalid('too many task files')
    names = []
    for name in files:
        if not isinstance(name, str):
            raise Invalid('task file must be a path')
        if Path(name).is_absolute():
            try:
                name = str(Path(name).relative_to(project))
            except ValueError:
                raise Invalid('task file outside project') from None
        inside(project, name)
        if name not in names:
            names.append(name)
    return sorted(names)


def matches(path, pattern):
    """Match path segments; ** spans zero or more directories."""
    @lru_cache(None)
    def visit(parts, patterns):
        if not patterns:
            return not parts
        if patterns[0] == '**':
            return visit(parts, patterns[1:]) or bool(parts) and visit(parts[1:], patterns)
        return bool(parts) and fnmatchcase(parts[0], patterns[0]) and visit(parts[1:], patterns[1:])

    return visit(tuple(path.split('/')), tuple(pattern.split('/')))


def _globs(path, patterns):
    positive = [p for p in patterns if not p.startswith('!')]
    negative = [p[1:] for p in patterns if p.startswith('!')]
    return (not positive or any(matches(path, p) for p in positive)) and not any(
        matches(path, p) for p in negative)


def _read(path, limit):
    if not path.is_file() or path.stat().st_size > limit:
        raise Invalid('selected guidance missing or oversized')
    return path.read_text(encoding='utf-8')


def _load(root, name, scope, sources):
    path = inside(root, name)
    if not path.exists():
        return []
    raw = _read(path, MAX_MANIFEST_BYTES)
    doc = parse_yaml(raw)
    try:
        validate_schema('task-guidance', doc)
    except Exception:
        raise Invalid('invalid task guidance manifest') from None
    sources.append({'scope': scope, 'name': name, 'sha256': digest(raw.encode())})
    ids = set()
    rules = []
    for spec in doc['rules']:
        if spec['id'] in ids:
            raise Invalid('duplicate guidance id')
        ids.add(spec['id'])
        inside(root, spec['path'])
        directory = spec.get('directory', '')
        if directory:
            # Private directories describe the target project, never the Custom tree
            if Path(directory).is_absolute() or any(x in ('', '.', '..') for x in directory.split('/')) or '\\' in directory:
                raise Invalid('unsafe guidance directory')
        patterns = spec.get('globs', [])
        patterns = [patterns] if isinstance(patterns, str) else patterns
        for pattern in patterns:
            value = pattern.removeprefix('!')
            if (not value or value.startswith('/') or '\\' in value or
                    any(x in ('', '.', '..') for x in value.split('/')) or
                    any(c in value for c in '{}()') or
                    any('**' in x and x != '**' for x in value.split('/'))):
                raise Invalid('unsupported guidance glob')
        rules.append({**spec, 'scope': scope, 'directory': directory,
                      'globs': patterns, 'root': root})
    return rules


def _applicable(rule, files):
    # Continue's off/global/known-files/colocation/glob decision order, with reasons
    if rule.get('policy') == 'off':
        return [], 'disabled'
    if rule.get('always_apply') is True:
        return files or [''], 'always apply'
    directory = rule['directory']
    if not directory and not rule['globs'] and rule.get('always_apply') is not False:
        return files or [''], 'root default'
    if not files:
        return [], 'no known task files'
    if not directory and not rule['globs'] and rule.get('always_apply') is False:
        return [], 'explicit selection required'
    selected = []
    for path in files:
        if directory and not path.startswith(directory + '/'):
            continue
        relative = path[len(directory) + 1:] if directory else path
        if _globs(relative, rule['globs']):
            selected.append(path)
    return selected, 'matched task files' if selected else 'no matching task file'


def select(project, private_root, files, limit):
    """Resolve declared topic conflicts per file; equal-authority contradictions stop delivery."""
    files = task_paths(project, files)
    sources = []
    rules = _load(project, '.context-ai/guidance.yaml', 'project', sources)
    if private_root is not None:
        rules += _load(Path(private_root).resolve(), 'guidance.yaml', 'private', sources)
    decisions = []
    applicable = []
    for rule in rules:
        paths, reason = _applicable(rule, files)
        decision = {k: rule[k] for k in ('scope', 'id', 'path')}
        decision.update(status='selected' if paths else 'omitted', reason=reason, matches=paths)
        decisions.append(decision)
        if paths:
            rule['body'] = _read(inside(rule['root'], rule['path']), limit)
            sources.append({'scope': rule['scope'], 'name': rule['path'],
                            'sha256': digest(rule['body'].encode())})
            rule['decision'] = decision
            rule['rank'] = (2 if rule['scope'] == 'project' else 1,
                            len(rule['directory'].split('/')) if rule['directory'] and not rule.get('always_apply') else 0)
            applicable.append(rule)
    topics = {r['topic'] for r in applicable if 'topic' in r}
    for topic in sorted(topics):
        group = [r for r in applicable if r.get('topic') == topic]
        won = {id(r): [] for r in group}
        for path in files or ['']:
            claims = [r for r in group if path in r['decision']['matches']]
            if not claims:
                continue
            rank = max(r['rank'] for r in claims)
            top = [r for r in claims if r['rank'] == rank]
            if len({r['body'] for r in top}) > 1:
                raise GuidanceConflict(topic, path, top)
            winner = min(top, key=lambda r: r['id'])
            won[id(winner)].append(path)
        for rule in group:
            decision = rule['decision']
            decision['applies_to'] = won[id(rule)]
            if not won[id(rule)]:
                decision.update(status='shadowed', reason='same topic: higher precedence or identical guidance')
            elif won[id(rule)] != decision['matches']:
                decision['reason'] = 'same topic: selected for part of task'
    entries = []
    seen = set()
    for rule in applicable:
        decision = rule['decision']
        if decision['status'] != 'selected':
            continue
        paths = decision.get('applies_to', decision['matches'])
        body = ('Applies to: ' + ', '.join(p or 'all tasks' for p in paths) + '\n' + rule['body'])
        if body not in seen:
            entries.append((rule['scope'] + ' task guidance', body))
            seen.add(body)
    return {'entries': entries, 'sources': sources,
            'task_files': files, 'decisions': decisions}
