#!/usr/bin/env python3
"""Generated product scope and opportunities; YAML remains authoritative."""
import sys
from context_ai import ROOT, read_yaml
from context_library import inventory, profiles, render_suggestions, document


def render():
    data = read_yaml(ROOT / 'docs/product.yaml')
    lines = ['# Context AI — product', '', data['mission'], '',
             'Generated from product.yaml. Delivery and scoped value are separate.', '',
             '| Feature | Delivery | Value | Scope and limits |', '| --- | --- | --- | --- |']
    for row in data['features']:
        a = row.get('assessment') or {}
        value = 'unknown' if a.get('value') is None else str(a['value'])
        details = a.get('scope', '') + ' ' + '; '.join(a.get('limitations', []))
        lines.append('| ' + ' | '.join([row['name'], a.get('delivery', 'unassessed'), value, details.replace('|', '\\|').replace('\n', ' ')]) + ' |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    options, ps = inventory(), profiles()
    known = read_yaml(ROOT / 'concepts.yaml')['concepts']
    for interest in document('interests')['interests']:
        if set(interest['profiles']) - set(ps) or set(interest['concepts']) - set(known):
            raise ValueError('unresolved interest profiles or concepts: ' + interest['id'])
    outputs = {'docs/PRODUCT.md': render(), 'docs/project-suggestions.md': render_suggestions()}
    for name, value in outputs.items():
        target = ROOT / name
        if sys.argv[1:] == ['--check']:
            if not target.exists() or target.read_text() != value:
                raise ValueError(name + ' is stale; run scripts/build_product.py')
        else:
            target.write_text(value)
