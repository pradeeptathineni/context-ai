#!/usr/bin/env python3
"""Generate research needs and coverage from the canonical concept catalog."""
import argparse
from collections import defaultdict
import subprocess
from context_ai import ROOT, read_yaml, encoded

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
    return doc['concepts']

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
            'coverage': coverage}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('view', choices=['needs','coverage'], default='needs', nargs='?')
    args = p.parse_args()
    artifact = generate()
    print(encoded(artifact if args.view == 'needs' else artifact['coverage']).decode(), end='')
