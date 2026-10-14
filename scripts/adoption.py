#!/usr/bin/env python3
"""Project-specific adoption decision over admitted evidence. Advice only; never installs or runs."""
import argparse
from pathlib import Path
import sys

from context_ai import Invalid, encoded, read_yaml
from evidence import inspect_bundle

FIT_KEYS=('capability','runtimes','licenses_allowed','existing_owner','excluded','assessments')
ASSESSMENT_KEYS={'capability','facts','revision','verified'}
FACT_KEYS={'license','runtime'}

def decide(admitted, need):
    """Each candidate gets adopt/trial/study/reject from project fit plus supported claims.

    A producer's score, disposition or recommendation action is recorded as input; it never
    satisfies a project constraint by itself.
    """
    if set(need)-set(FIT_KEYS) or 'capability' not in need:
        raise Invalid('need declares capability plus optional '+', '.join(FIT_KEYS[1:]))
    claims={c['id']:c for c in admitted['claims']}
    advice={item['candidate_id']:item for item in (admitted.get('contextual_recommendations') or {}).get('items',[])}
    assessments=need.get('assessments',{})
    known={c['id'] for c in admitted['recommendations']}
    for key,value in assessments.items():
        if key not in known:raise Invalid('assessment names an unknown candidate: '+key)
        if not isinstance(value,dict) or set(value)-ASSESSMENT_KEYS or not {'capability','revision','verified'}<=set(value) or not value['verified']:
            raise Invalid('a Context assessment needs capability, inspected revision and what was verified')
        facts=value.get('facts',{})
        if not isinstance(facts,dict) or set(facts)-FACT_KEYS or any(not isinstance(v,str) or not v.strip() for v in facts.values()):
            raise Invalid('assessment facts may state only non-empty '+' and '.join(sorted(FACT_KEYS))+'; omit a field that was not inspected')
    decisions=[]
    for candidate in admitted['recommendations']:
        reasons=[];blocked=[]
        supported=[id for id in candidate['claim_ids'] if claims[id]['status'] in ('observed','supported')]
        # Only this candidate's own cited claims count; a Context assessment never revises claim status.
        contradicted=[id for id in candidate['claim_ids'] if claims[id]['status']=='contradicted']
        item=advice.get(candidate['id'])
        unknown=[]
        # Context's own inspection outranks producer-reported facts; both stay visible.
        assessment=assessments.get(candidate['id'])
        # Each fact keeps its own origin: only fields Context inspected are 'context'; a producer
        # value fills a gap but stays 'producer', and an absent field stays unknown.
        assessed=(assessment or {}).get('facts') or {}
        produced=item.get('facts',{}) if item else {}
        facts={**produced,**assessed}
        origin={key:'context' if key in assessed else 'producer' if key in produced else 'unknown' for key in sorted(FACT_KEYS)}
        addresses=assessment['capability'] if assessment else item['capability'] if item else None
        if addresses is not None and addresses!=need['capability']:
            blocked.append('addresses '+addresses+', not '+need['capability'])
        if candidate['id'] in need.get('excluded',[]) or candidate['name'] in need.get('excluded',[]):
            blocked.append('excluded by project')
        for key,allowed,label in (('runtime',need.get('runtimes'),'project runtimes'),('license',need.get('licenses_allowed'),'allowed licenses')):
            if not allowed:continue
            if key not in facts:unknown.append(key)
            elif facts[key] not in allowed:blocked.append(key+' '+facts[key]+' not in '+label+' '+', '.join(allowed))
        if unknown:
            reasons.append('unknown '+' and '.join(unknown)+'; inspect the candidate before any trial')
        if assessment:
            reasons.append('capability verified by Context at '+assessment['revision']+': '+'; '.join(assessment['verified']))
        for key in sorted(FACT_KEYS):
            if origin[key]=='context':
                reasons.append(key+' '+facts[key]+' verified by Context at '+assessment['revision'])
            elif origin[key]=='producer':
                reasons.append(key+' '+facts[key]+' is producer-reported and not verified by Context; check it at the exact version before adoption')
        constrained=[k for k,allowed in (('runtime',need.get('runtimes')),('license',need.get('licenses_allowed'))) if allowed]
        gaps=[k for k in constrained if origin[k]!='context']
        verification=('none' if not assessment else 'complete' if not gaps else 'partial')
        if need.get('existing_owner'):
            reasons.append('project already owns this with '+need['existing_owner']+'; adoption must beat it on a trial')
        if not supported:
            blocked.append('no supported or observed claim')
        if addresses is None:
            unknown.append('capability')
            reasons.append('no recommendation states which capability this addresses; map it before a trial')
        if blocked:
            decision='reject' if any(not b.startswith('no supported') for b in blocked) else 'study'
        elif unknown or contradicted:
            decision='study'
        else:
            # Adoption needs a passing project trial; evidence alone earns a trial, never adoption.
            decision='trial'
        if contradicted:
            # Explain the adverse claims against the final result: a fit/exclusion rejection is not a pending study.
            outcome='; rejected on project fit or exclusion (see blocked_by), not pending reassessment' if decision=='reject' else '; study pending reassessment before any trial'
            reasons.append('cited contradicted claims '+', '.join(contradicted)+outcome)
        # Describes what 'state' covers; it never adds a check or changes the state.
        scope=('no Context assessment recorded; nothing verified by Context' if not assessment else
               'declared constraints '+', '.join(constrained)+' only; capability assessment, not runtime, privacy or legal assurance and not whole-candidate validation' if constrained else
               'capability assessment only; no runtime or license constraint declared, so state covers no such fact; not whole-candidate validation')
        decisions.append({'candidate':candidate['id'],'name':candidate['name'],'decision':decision,
                          'blocked_by':blocked,'notes':reasons,'supporting_claims':supported,
                          'contradicted_claims':contradicted,
                          'context_assessment':assessment,
                          'verification':{'state':verification,'fact_origin':origin,
                                          'unverified_constraints':gaps if assessment else constrained,
                                          'scope':scope},
                          'producer_disposition':candidate['disposition'],
                          'producer_signal':candidate.get('signal'),
                          'producer_action':item['action'] if item else None,
                          'producer_intrinsic_strength':item.get('intrinsic_strength') if item else None})
    return {'capability':need['capability'],'bundle_id':admitted['bundle_id'],'mode':admitted['mode'],
            'decisions':decisions,'adoption_rule':'adopt only after the trial passes in this project',
            'trial_authorization':'not granted here; a trial needs the project owner\'s authority and a separate plan',
            'authority':'Advice only; installation needs a separate plan and user/project authority.',
            'activation':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundle',type=Path);p.add_argument('--sha256',required=True)
    p.add_argument('--producer');p.add_argument('--commit')
    p.add_argument('--need',type=Path,required=True,help='YAML with capability and optional project constraints')
    args=p.parse_args()
    admitted=inspect_bundle(args.bundle,args.sha256,args.producer,args.commit)
    print(encoded(decide(admitted,read_yaml(args.need))).decode(),end='')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('context-ai adoption: '+str(e),file=sys.stderr);sys.exit(1)
