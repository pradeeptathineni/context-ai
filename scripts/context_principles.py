"""Explicit, source-bound native Principles v2 guidance; no network or activation."""
import base64
from datetime import date
import json
from pathlib import Path
import re
import unicodedata

import context_ai as engine

PROFILES = ('minimal', 'standard', 'learning', 'verification')
SOURCE_STATES = ('active', 'moved', 'superseded', 'withdrawn', 'unavailable')


def require(condition, message):
    if not condition:
        raise engine.Invalid('Principles: ' + message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)


def source_record(value):
    require(isinstance(value, dict) and set(value) == {'schema_version', 'id', 'title', 'publisher', 'evidence_kind',
            'canonical_url', 'url_aliases', 'published_or_version', 'first_retrieved', 'last_reviewed', 'status', 'superseded_by'}, 'incomplete native source record')
    require(value['schema_version'] == 4 and re.fullmatch(r'SRC-\d{6}', value['id']), 'unsupported native source identity/schema')
    require(all(text(value[key]) for key in ('title', 'publisher', 'evidence_kind', 'canonical_url')), 'missing native source qualification')
    require(re.match(r'https?://[^/\s]+', value['canonical_url']) and isinstance(value['url_aliases'], list), 'invalid native source URLs')
    require(all(isinstance(url, str) and re.match(r'https?://[^/\s]+', url) for url in value['url_aliases']), 'invalid native source alias')
    for key in ('first_retrieved', 'last_reviewed'):
        require(isinstance(value[key], str), 'native source date missing')
        date.fromisoformat(value[key])
    require(value['status'] in SOURCE_STATES, 'unsupported native source lifecycle')
    if value['status'] != 'superseded':
        require(value['superseded_by'] is None, 'unexpected supersession target')


def parse(raw):
    require(len(raw) <= 4_000_000, 'export exceeds bounded input size')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def native_yaml(raw):
    value = engine.parse_yaml(raw.decode('utf-8'))
    return json.loads(json.dumps(value, default=lambda item: item.isoformat()))


def native_plain(raw):
    """Exact supported native inline projection; unsupported syntax fails closed."""
    # The pinned producer renders plain text and inline code, normalizes NFC,
    # and collapses ECMAScript whitespace. Do not guess other Markdown nodes.
    pieces = raw.split('`')
    require(len(pieces) % 2 == 1, 'unsupported native inline code; use supported export derivation')
    for index, piece in enumerate(pieces):
        if index % 2:
            require(piece and '\n' not in piece and not re.search(r'[^ ]\s| {2,}', piece), 'unsupported native inline code')
        else:
            require(not re.search(r'[\[\]*_\\<>]|&(?:#\w+|[A-Za-z]+);', piece),
                    'unsupported native inline Markdown; exact derivation unavailable')
    value = unicodedata.normalize('NFC', ''.join(pieces))
    return re.sub(r'[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+', ' ', value).strip(' ')


def native_entry(raw, entry_id, file_id):
    """Derive complete ordered claim views from the bound canonical entry."""
    text = raw.decode('utf-8')
    require('\r' not in text and text.count('\n## References\n') == 1, 'unsupported native document layout')
    references_text = text.split('\n## References\n', 1)[1]
    refs = []
    definitions = []
    for line in references_text.splitlines():
        if not line:
            continue
        reference = re.fullmatch(r'(\d+)\. \[([^\[\]]+)\]\[(\d+)\] — `(SRC-\d{6})`', line)
        definition = re.fullmatch(r'\[(\d+)\]: (https?://\S+)', line)
        if reference:
            ordinal, title, label, source_id = reference.groups()
            require(not definitions and ordinal == label == str(len(refs) + 1), 'unsupported native bibliography order')
            refs.append({'label': file_id + ':' + label, 'source_id': source_id, 'title': native_plain(title)})
        elif definition:
            require(definition[1] == str(len(definitions) + 1), 'unsupported native reference definition order')
            definitions.append(definition[2])
        else:
            require(False, 'unsupported native bibliography; exact derivation unavailable')
    require(refs and len(refs) == len(definitions), 'incomplete native bibliography')
    source_by_label = {ref['label']: ref['source_id'] for ref in refs}
    matches = [(match[2], match[3]) for match in re.finditer(r'^### (PRN-\d{6}) — ([^\n]+)\n([\s\S]*?)(?=^### |^## References|\Z)', text, re.M) if match[1] == entry_id]
    require(len(matches) == 1, 'native entry identity missing or duplicated')
    title, body = matches[0]
    sections = re.split(r'^#### ([^\n]+)\n', body, flags=re.M)
    blocks = {'statement': sections[0]}
    order = ['Why', 'Practices', 'Applicability', 'Goals', 'Tags']
    seen = []
    for name, content in zip(sections[1::2], sections[2::2]):
        require(name in order and name not in seen and (not seen or order.index(name) > order.index(seen[-1])), 'unsupported native section order')
        seen.append(name)
        blocks[name.lower()] = content
    require('Why' in seen and 'Practices' in seen, 'native entry lacks required sections')

    def paragraphs(content):
        result = [part.strip() for part in re.split(r'\n[ \t]*\n', content.strip()) if part.strip()]
        require(all(not re.search(r'^(?:\s{4}|\s*[#>|]|\s*[-+*] |\s*\d+[.)] )', part, re.M) for part in result), 'unsupported native paragraph block')
        return result

    def items(content):
        result = []
        blank = False
        for line in content.strip().splitlines():
            if not line.strip():
                blank = True
                continue
            match = re.fullmatch(r'[-+*] (.+)', line)
            if match:
                result.append(match[1]);blank = False
            else:
                require(result and not blank and re.match(r'^ {2,3}\S', line), 'unsupported native list item shape')
                result[-1] += '\n' + line.lstrip()
        return result

    def claim(content, role):
        cited = re.search(r'\s+(\[[1-9]\d*\](?:, \[[1-9]\d*\])*)$', content)
        require(cited is not None or role.startswith('goal-'), 'native required claim lacks citations')
        labels = re.findall(r'\[(\d+)\]', cited[1]) if cited else []
        namespaced = [file_id + ':' + label for label in labels]
        require(all(label in source_by_label for label in namespaced), 'native citation missing bibliography identity')
        plain = native_plain(content[:cited.start()] if cited else content)
        require(bool(plain), 'empty native claim')
        suffix = ' ' + ', '.join('[' + label + ']' for label in namespaced) if labels else ''
        return {'role': role, 'text': plain + suffix, 'claim_sha256': engine.digest(plain.encode()) if labels else None,
                'source_ids': list(dict.fromkeys(source_by_label[label] for label in namespaced))}

    statement = paragraphs(blocks['statement'])
    require(len(statement) == 1, 'native entry must have one statement')
    result = {'title': title, 'statement': claim(statement[0], 'statement')}
    for section, role in (('why', 'why'), ('practices', 'practice'), ('applicability', 'applicability'), ('goals', 'goal')):
        values = (items if section in ('practices', 'goals') else paragraphs)(blocks[section]) if section in blocks else []
        result[section] = [claim(value, role + '-' + str(index)) for index, value in enumerate(values, 1)]
    result['tags'] = items(blocks['tags']) if 'tags' in blocks else []
    require(all(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', tag) for tag in result['tags']), 'unsupported native tags')
    claims = [result['statement']] + result['why'] + result['practices'] + result['applicability'] + result['goals']
    result['source_ids'] = list(dict.fromkeys(source for item in claims for source in item['source_ids']))
    result['references'] = [ref for ref in refs if ref['source_id'] in result['source_ids']]
    return result


def verify_derivation(entry, records, profile):
    expected = native_entry(records[entry['file_path']], entry['id'], entry['file_id'])
    fields = ['title', 'statement', 'source_ids', 'references']
    if profile != 'minimal':
        fields += ['why', 'practices', 'applicability']
    if profile in ('learning', 'verification'):
        fields += ['goals', 'tags']
    for field in fields:
        require(entry[field] == expected[field], 'native derivation mismatch: ' + entry['id'] + ':' + field)
    if profile == 'verification':
        evidence = [native_yaml(raw) for path, raw in records.items() if path.startswith('evidence/')]
        evidence = [value for value in evidence if isinstance(value, dict) and value.get('entry_id') == entry['id']]
        require(len(evidence) <= 1 and entry['evidence'] == (evidence[0] if evidence else None), 'native derivation mismatch: verification evidence')
        if evidence:
            configuration = evidence[0].get('reviewer', {}).get('configuration')
            if configuration and configuration.get('configuration_ref'):
                path = configuration['configuration_ref']
                require(path in records and engine.digest(records[path]) == configuration.get('configuration_sha256'), 'native evidence configuration binding mismatch')


def validate(bundle, revision, artifact_sha256):
    require(set(bundle) == {'artifact', 'inputs'}, 'invalid retained bundle')
    raw = base64.b64decode(bundle['artifact'], validate=True)
    require(sha(artifact_sha256) and engine.digest(raw) == artifact_sha256, 'export digest mismatch; re-preview')
    artifact = parse(raw)
    require(type(artifact.get('schema_version')) is int and artifact['schema_version'] == 2,
            'unsupported derived version; regenerate v1, never relabel it (Signals v1 is unrelated)')
    require(artifact.get('source_revision') == revision and text(revision), 'source revision mismatch')
    profile = artifact.get('profile')
    require(profile in PROFILES, 'unsupported profile')
    require(artifact.get('usage') == ('reference-only' if profile == 'minimal' else 'qualified-guidance'), 'invalid profile usage')
    omitted = (['why', 'practices', 'applicability'] if profile == 'minimal' else [])
    omitted += ['goals', 'tags'] if profile in ('minimal', 'standard') else []
    omitted += ['sources', 'evidence'] if profile != 'verification' else []
    require(artifact.get('omitted_sections') == omitted, 'profile omissions do not match native v2')
    inputs = artifact.get('inputs')
    entries = artifact.get('entries')
    require(isinstance(inputs, list) and inputs and isinstance(entries, list) and entries, 'missing inputs or selection')
    records = {}
    for item in inputs:
        require(isinstance(item, dict) and set(item) == {'path', 'sha256'} and sha(item['sha256']), 'invalid input pin')
        path = item['path']
        require(isinstance(path, str) and re.fullmatch(r'(domains|sources|evidence|evals)/[A-Za-z0-9_./-]+\.(md|yaml)', path), 'unsupported input path')
        engine.inside(Path('/principles-bound-inputs'), path)
        require(path not in records and path in bundle['inputs'], 'missing or duplicate native input')
        data = base64.b64decode(bundle['inputs'][path], validate=True)
        require(engine.digest(data) == item['sha256'], 'source input digest changed: ' + path + '; re-preview')
        records[path] = data
    require(set(bundle['inputs']) == set(records), 'unbound retained inputs')
    ids = []
    for entry in entries:
        required = {'id', 'title', 'file_id', 'file_path', 'status', 'last_reviewed', 'reviewed_content_sha256',
                    'input_sha256', 'statement', 'source_ids', 'source_inputs', 'references'}
        if profile != 'minimal':
            required |= {'why', 'practices', 'applicability'}
        if profile in ('learning', 'verification'):
            required |= {'goals', 'tags'}
        if profile == 'verification':
            required |= {'sources', 'evidence'}
        require(isinstance(entry, dict) and set(entry) == required, 'incomplete selected blocks, applicability, or qualification')
        require(re.fullmatch(r'PRN-\d{6}', entry['id']) and text(entry['title']), 'invalid principle identity')
        ids.append(entry['id'])
        require(entry['status'] in ('draft', 'active'), 'unsupported corpus lifecycle')
        require(entry['file_path'] in records and engine.digest(records[entry['file_path']]) == entry['input_sha256'], 'corpus input identity mismatch')
        parts = records[entry['file_path']].decode('utf-8').split('---', 2)
        require(len(parts) == 3 and not parts[0], 'native frontmatter missing')
        frontmatter = native_yaml(parts[1].encode())
        for native, exported in (('id', 'file_id'), ('status', 'status'), ('last_reviewed', 'last_reviewed'), ('reviewed_content_sha256', 'reviewed_content_sha256')):
            require(frontmatter.get(native) == entry[exported], 'corpus qualification differs from native bytes')
        require(frontmatter.get('schema_version') == 5, 'unsupported native corpus schema')
        if entry['status'] == 'active':
            require(text(entry['last_reviewed']) and sha(entry['reviewed_content_sha256']), 'active qualification missing')
        source_map = {}
        require(isinstance(entry['source_inputs'], list), 'source lifecycle missing')
        for source in entry['source_inputs']:
            require(set(source) == {'id', 'status', 'path', 'input_sha256'} and source['status'] in SOURCE_STATES, 'invalid native source lifecycle')
            require(source['path'] in records and engine.digest(records[source['path']]) == source['input_sha256'], 'source identity mismatch')
            value = native_yaml(records[source['path']])
            source_record(value)
            require(value.get('schema_version') == 4 and value.get('id') == source['id'] and value.get('status') == source['status'], 'native source record mismatch')
            require(source['id'] not in source_map, 'duplicate source identity')
            if source['status'] == 'moved':
                require(value.get('url_aliases') and value.get('superseded_by') is None, 'moved source needs aliases')
            if source['status'] == 'superseded':
                require(re.fullmatch(r'SRC-\d{6}', value.get('superseded_by', '')), 'superseded source needs target')
            source_map[source['id']] = value
        require(entry['source_ids'] == list(source_map), 'source IDs differ from lifecycle records')
        require(isinstance(entry['references'], list) and all(set(ref) == {'label', 'source_id', 'title'} and text(ref['title']) for ref in entry['references']), 'invalid namespaced references')
        references = {ref['label']: ref['source_id'] for ref in entry['references']}
        require(len(references) == len(entry['references']) and set(references.values()) == set(source_map), 'unresolved namespaced references')
        claims = [entry['statement']]
        for section in ('why', 'practices', 'applicability', 'goals'):
            if section in entry:
                require(isinstance(entry[section], list), 'incomplete ' + section)
                if section in ('why', 'practices'):
                    require(bool(entry[section]), 'empty required ' + section)
                claims += entry[section]
        for claim in claims:
            require(isinstance(claim, dict) and set(claim) == {'role', 'text', 'claim_sha256', 'source_ids'} and text(claim['text']), 'invalid claim')
            labels = re.findall(r'\[(' + re.escape(entry['file_id']) + r':\d+)\]', claim['text'])
            if not claim['role'].startswith('goal-'):
                require(labels and sha(claim['claim_sha256']), 'uncited required claim')
            require(all(label in references for label in labels), 'unresolved claim citation')
            require(claim['source_ids'] == list(dict.fromkeys(references[label] for label in labels)), 'claim source identity mismatch')
            unnamespaced = re.sub(r'\s+\[' + re.escape(entry['file_id']) + r':\d+\](?:, \[' + re.escape(entry['file_id']) + r':\d+\])*$', '', claim['text'])
            require((not labels and claim['claim_sha256'] is None) or engine.digest(unnamespaced.encode()) == claim['claim_sha256'], 'claim digest mismatch')
        if profile == 'verification':
            require(entry['sources'] == list(source_map.values()), 'full source records differ from native bytes')
        verify_derivation(entry, records, profile)
    require(ids == sorted(set(ids)), 'duplicate or unordered principle selection')
    binding = {'source_revision': revision, 'inputs': inputs,
               'selection': [{'id': entry['id'], 'file_id': entry['file_id']} for entry in entries]}
    calculated = engine.digest(json.dumps(binding, ensure_ascii=False, separators=(',', ':')).encode())
    require(artifact.get('input_sha256') == calculated, 'native input binding mismatch')
    return artifact


def read(spec):
    raw = Path(spec['export']).read_bytes()
    reference_raw = None
    require(engine.digest(raw) == spec['sha256'], 'export digest changed; re-preview')
    value = parse(raw)
    # Version check precedes even a reference-only fetch.
    require(value.get('schema_version') == 2, 'unsupported derived version; regenerate v1 (Signals v1 is unrelated)')
    if value.get('profile') == 'minimal':
        reference_raw = raw
        require(spec.get('full_export') and sha(spec.get('full_sha256')), 'reference-only minimal needs matching full export')
        full_raw = Path(spec['full_export']).read_bytes()
        full = parse(full_raw)
        require(engine.digest(full_raw) == spec['full_sha256'] and full.get('input_sha256') == value.get('input_sha256'), 'stale full fetch; re-preview')
        raw = full_raw
        artifact_sha = spec['full_sha256']
    else:
        artifact_sha = spec['sha256']
    value = parse(raw)
    root = Path(spec['source_root'])
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(), 'explicit native input directory required')
    bundle = {'artifact': base64.b64encode(raw).decode(), 'inputs': {}}
    for item in value.get('inputs', []):
        path = engine.inside(root, item['path'])
        require(path.is_file() and path.stat().st_size <= 2_000_000, 'missing or oversized native input')
        bundle['inputs'][item['path']] = base64.b64encode(path.read_bytes()).decode()
    artifact = validate(bundle, spec['revision'], artifact_sha)
    if reference_raw is not None:
        reference = validate({'artifact': base64.b64encode(reference_raw).decode(), 'inputs': bundle['inputs']}, spec['revision'], spec['sha256'])
        require(reference['input_sha256'] == artifact['input_sha256'], 'stale full fetch; re-preview')
    require(artifact['profile'] != 'minimal', 'reference-only full fetch is still lossy')
    intent = spec.get('intent', 'operational')
    require(intent in ('operational', 'inspect'), 'unsupported selection intent')
    selected = [entry['id'] for entry in artifact['entries'] if intent == 'inspect' or
                (entry['status'] == 'active' and all(source['status'] in ('active', 'moved') for source in entry['source_inputs']))]
    return {'artifact_sha256': artifact_sha, 'source_revision': spec['revision'], 'input_sha256': artifact['input_sha256'],
            'intent': intent, 'selected_ids': selected, 'bundle': bundle}


def resources(selection):
    require(set(selection) == {'artifact_sha256', 'source_revision', 'input_sha256', 'intent', 'selected_ids', 'bundle'}, 'invalid retained selection')
    artifact = validate(selection['bundle'], selection['source_revision'], selection['artifact_sha256'])
    require(artifact['input_sha256'] == selection['input_sha256'] and artifact['profile'] != 'minimal', 'incomplete or changed retained selection')
    require(selection['intent'] in ('operational', 'inspect'), 'unsupported selection intent')
    selected = [entry for entry in artifact['entries'] if selection['intent'] == 'inspect' or
                (entry['status'] == 'active' and all(source['status'] in ('active', 'moved') for source in entry['source_inputs']))]
    require(selection['selected_ids'] == [entry['id'] for entry in selected], 'selection would change lifecycle authority')
    lines = ['# Selected Principles', 'Intent: ' + selection['intent'],
             'Inspection is nonauthoritative. Drafts and source lifecycle never become active approval.',
             'Export profile: ' + artifact['profile'], 'Declared omissions: ' + json.dumps(artifact['omitted_sections']),
             'Source revision: ' + selection['source_revision'], 'Input SHA-256: ' + selection['input_sha256']]
    for entry in selected:
        lines += ['', '## ' + entry['id'] + ' — ' + entry['title'], 'Corpus lifecycle: ' + entry['status'],
                  'Qualification: last_reviewed=' + str(entry['last_reviewed']) + '; reviewed_content_sha256=' + str(entry['reviewed_content_sha256']),
                  'Native input: ' + entry['file_path'] + ' SHA-256=' + entry['input_sha256'], entry['statement']['text']]
        for section in ('why', 'practices', 'applicability', 'goals'):
            if section in entry:
                lines += ['', '### ' + section.capitalize()] + [claim['text'] for claim in entry[section]]
        lines += ['', '### Source lifecycle and references', json.dumps(entry['source_inputs'], ensure_ascii=False),
                  json.dumps(entry['references'], ensure_ascii=False), '### Complete selected export entry', json.dumps(entry, ensure_ascii=False)]
    return {'principles/selected.md': ('\n'.join(lines) + '\n').encode(), 'principles/bundle.json': engine.encoded(selection)}
