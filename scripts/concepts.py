#!/usr/bin/env python3
"""Generate research needs and coverage from the canonical concept catalog."""
import argparse
from collections import defaultdict
import subprocess
import copy
from context_ai import ROOT, read_yaml, encoded, inside, Invalid

CONSTRAINTS = [
    'Provider-independent Markdown behavior; exact contracts remain structured data.',
    'Codex is the current distributor; no agent runtime, automatic hooks or installers.',
    'Preserve project instructions, retained edits, source integrity and portable declarations.',
    'Offer multiple applicable practices/options; offering is separate from enabling.',
    'Group source acquisition; bind claims precisely; a generic reference is not coverage.',
    'Existing web resources and user visual intent remain supported; no neon1 implementation.',
]
PRIORITY = {'context.instructions', 'context.loadouts', 'context.skills', 'context.injection',
            'context.budget', 'context.compression', 'architecture.portability',
            'research.prior_art', 'research.confidence', 'research.provenance',
            'quality.review', 'quality.strategy', 'delivery.git', 'communication.clarity'}

def catalog():
    doc = read_yaml(ROOT/'concepts.yaml')
    if doc['schema_version'] == 1:
        return {id: {'definition': definition, **doc['details'][id]}
                for id, definition in doc['concepts'].items()}
    result = {}
    for id, entry in doc['concepts'].items():
        result[id] = {**copy.deepcopy(doc['defaults']), **entry}
        result[id]['coverage'] = {**copy.deepcopy(doc['defaults']['coverage']), **entry.get('coverage', {})}
    return result

def validate_catalog(entries, decisions):
    sources=read_yaml(ROOT/'sources.yaml')['sources']
    bundles=read_yaml(ROOT/'concepts.yaml').get('evidence_bundles',{})
    aliases=set(entries)
    dispositions={'source-backed','context-options','practice-retained','not-applicable','unresolved'}
    for id, entry in entries.items():
        if set(entry) - {'definition','modules','scope','aliases','boundary','coverage'}:
            raise Invalid('unknown concept fields: '+id)
        if not isinstance(entry['definition'],str) or not entry['definition'].strip() or '\n' in entry['definition']:
            raise Invalid('invalid concept definition: '+id)
        for alias in entry['aliases']:
            if alias in aliases:raise Invalid('ambiguous concept alias: '+alias)
            aliases.add(alias)
        for path in entry['modules']:
            if not inside(ROOT,path).is_file():raise Invalid('broken concept module: '+path)
        coverage=entry['coverage']
        if coverage['disposition'] not in dispositions or not coverage['rationale'] or not coverage['uncertainty'] or not coverage['next_action']:
            raise Invalid('incomplete concept coverage: '+id)
        if any(ref not in sources for ref in coverage['source_refs']):raise Invalid('unresolved concept source: '+id)
        if any(ref not in decisions for ref in coverage['decisions']):raise Invalid('unresolved concept decision: '+id)
        for ref in coverage['claim_refs']:
            bundle,claim=ref.split(':',1)
            if bundle not in bundles or claim not in bundles[bundle]['claims']:
                raise Invalid('unresolved concept claim: '+id)
            if not set(bundles[bundle]['claims'][claim]['source_refs']).issubset(coverage['source_refs']):
                raise Invalid('claim support is not bound to its precise sources: '+id)
        if coverage['disposition']=='source-backed' and not coverage['source_refs']:
            raise Invalid('source-backed coverage requires a source: '+id)


def offered_options():
    options = {}
    for path in ['signals/common.yaml','providers/openai/signals.yaml']:
        for id, candidates in read_yaml(ROOT/path)['signals'].items():
            options.setdefault(id,[])
            options[id].extend({'offered': True, 'enabled': False, 'registry': path, **candidate} for candidate in candidates)
    return options


def generate():
    entries = catalog()
    groups = defaultdict(list)
    coverage = []
    for id, entry in entries.items():
        family = id.split('.')[0]
        groups[family].append({'id': id, 'definition': entry['definition'],
                               'scope': entry['scope'], 'modules': entry['modules'],
                               'priority': 'high' if id in PRIORITY else 'normal'})
        coverage.append({'id': id, **entry.get('coverage', {
            'disposition': 'unresolved',
            'rationale': 'Module routing is available; broad decision pointers do not establish concept-specific support.',
            'source_refs': [],
            'next_action': 'Assess the precise claim against primary evidence and applicable consumer constraints.',
        })})
    try:
        revision = subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    except subprocess.CalledProcessError:
        revision = (ROOT/'REVISION').read_text().strip() if (ROOT/'REVISION').exists() else 'exported-tree'
    return {'schema_version': 1, 'kind': 'concept-needs', 'repository': 'pradeeptathineni/context-ai',
            'catalog_revision': revision, 'constraints': CONSTRAINTS,
            'questions': [{'family': family,
                           'question': 'Which practices or mechanisms address these distinct decisions, under which conditions, and what remains unsupported?',
                           'concepts': concepts} for family, concepts in groups.items()],
            'coverage': coverage, 'options': offered_options()}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('view', choices=['needs','coverage','definitions','options'], default='needs', nargs='?')
    args = p.parse_args()
    artifact = generate()
    print(encoded(artifact if args.view == 'needs' else (offered_options() if args.view == 'options' else ({id:entry['definition'] for id,entry in catalog().items()} if args.view == 'definitions' else artifact['coverage']))).decode(), end='')
