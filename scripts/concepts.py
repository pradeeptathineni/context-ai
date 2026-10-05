#!/usr/bin/env python3
"""Generate research needs and coverage from the canonical concept catalog."""
import argparse
import subprocess
import copy
from context_ai import ROOT, read_yaml, encoded, inside, Invalid, current_decisions

CONSTRAINTS = [
    'Provider-independent Markdown behavior; exact contracts remain structured data.',
    'Codex is the current distributor; no agent runtime, automatic hooks or installers.',
    'Preserve project instructions, retained edits, source integrity and portable declarations.',
    'Offer multiple applicable practices/options; offering is separate from enabling.',
    'Group source acquisition; bind claims precisely; a generic reference is not coverage.',
    'Existing web resources and user visual intent remain supported; no neon1 implementation.',
]
RESEARCH_GROUPS = [
    ('agent-work', 'When does delegation improve a real development task, and what isolation, handoff and review keep its cost below the benefit?',
     ['agents.decomposition', 'agents.orchestration', 'agents.delegation', 'agents.isolation', 'agents.handoff']),
    ('model-choice', 'How should task difficulty, available models and measured outcomes guide model and reasoning effort without a brittle task classifier?',
     ['models.selection', 'models.reasoning', 'models.routing', 'models.cost_latency', 'models.eval']),
    ('context-use', 'Which retrieval and compression practices improve task outcomes and total cost on current coding agents?',
     ['context.project_knowledge', 'context.retrieval', 'context.compression', 'context.budget', 'context.sync']),
    ('repository-understanding', 'What small procedures help a new agent locate canonical ownership, contracts and relevant prior work in an unfamiliar repository?',
     ['architecture.boundaries', 'architecture.composition', 'implementation.reuse', 'research.prior_art']),
    ('evidence-to-decision', 'How should development research select credible sources, calibrate claim strength and turn evidence into a revisitable choice?',
     ['research.discovery', 'research.credibility', 'research.confidence', 'research.decision']),
    ('implementation-and-debugging', 'Which practices improve architectural choices, fault localization and refactoring on real code without adding ceremony?',
     ['architecture.patterns', 'architecture.interfaces', 'implementation.errors', 'implementation.debugging', 'implementation.refactoring']),
    ('verification-and-review', 'Which test, evaluation and review methods find material defects beyond a capable baseline agent, at acceptable cost?',
     ['quality.strategy', 'quality.integration_tests', 'quality.end_to_end', 'quality.evaluations', 'quality.review']),
    ('delivery-and-maintenance', 'What VCS, CI, documentation and maintenance procedures preserve useful work while keeping small changes proportional?',
     ['delivery.git', 'delivery.ci', 'delivery.documentation', 'product.lifecycle']),
    ('web-experience', 'For a real website, which design, responsive, accessibility and browser checks improve user outcomes beyond a static build?',
     ['web.product', 'web.design', 'web.responsive', 'quality.accessibility', 'quality.visual']),
    ('security-and-operations', 'Which bounded supply-chain, trust and debugging checks should development agents run, and when?',
     ['security.trust', 'security.supply_chain', 'security.vulnerabilities', 'operations.observability']),
    ('skills-and-writing', 'When do on-demand skills or captured procedures change behavior, and which writing checks remove unsupported or generic prose?',
     ['context.skills', 'integration.workflow_capture', 'communication.anti_slop', 'communication.clarity']),
]

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
        if set(coverage) - {'disposition','rationale','source_refs','claim_refs','decisions','uncertainty','next_action'}:
            raise Invalid('unknown coverage fields: '+id)
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


def coverage():
    return [{'id': id, **entry['coverage']} for id, entry in catalog().items()]


def generate():
    entries = catalog()
    decisions_by_concept = {}
    for decision in current_decisions().values():
        decisions_by_concept.setdefault(decision['concept'], []).append(decision['id'])
    seen = set()
    questions = []
    for group, question, ids in RESEARCH_GROUPS:
        concepts = []
        for id in ids:
            if id not in entries or id in seen:
                raise Invalid('unknown or repeated research concept: '+id)
            seen.add(id)
            entry = entries[id]
            concepts.append({'id': id, 'definition': entry['definition'],
                             'disposition': entry['coverage']['disposition'],
                             'uncertainty': entry['coverage']['uncertainty'],
                             'source_refs': entry['coverage']['source_refs'],
                             'claim_refs': entry['coverage']['claim_refs'],
                             'decision_refs': sorted(set(entry['coverage']['decisions'] + decisions_by_concept.get(id, [])))})
        questions.append({'group': group, 'question': question, 'concepts': concepts})
    try:
        revision = subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    except subprocess.CalledProcessError:
        revision = (ROOT/'REVISION').read_text().strip() if (ROOT/'REVISION').exists() else 'exported-tree'
    return {'schema_version': 2, 'kind': 'concept-needs', 'repository': 'pradeeptathineni/context-ai',
            'catalog_revision': revision, 'constraints': CONSTRAINTS,
            'questions': questions}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('view', choices=['needs','coverage','definitions','options'], default='needs', nargs='?')
    args = p.parse_args()
    artifact = generate() if args.view == 'needs' else (
        offered_options() if args.view == 'options' else (
            {id: entry['definition'] for id, entry in catalog().items()}
            if args.view == 'definitions' else coverage()))
    print(encoded(artifact).decode(), end='')
