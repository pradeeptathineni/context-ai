#!/usr/bin/env python3
"""Read-only exact-byte evidence admission. Never activates a recommendation."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

from context_ai import ROOT, Invalid, read_yaml, validate_schema, encoded

def public_url(value):
    u=urlparse(value)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):
        raise Invalid('evidence URL must be public HTTPS without credentials')
    host=u.hostname.lower().rstrip('.')
    if '.' not in host or host.endswith(('.local','.internal','.localhost','.test','.invalid')) or host=='localhost':
        raise Invalid('private or reserved evidence host')
    try:
        ip=ipaddress.ip_address(host)
        if not ip.is_global:
            raise Invalid('private evidence address')
    except ValueError as e:
        if isinstance(e,Invalid):raise
    # No network is performed. DNS rebinding/redirects must be guarded by a fetching host.
    return value

def unique(items,kind):
    ids=[x['id'] for x in items]
    if len(ids)!=len(set(ids)):
        raise Invalid('duplicate '+kind+' IDs')
    return {x['id']:x for x in items}

def inspect_bundle(path,expected_sha,producer=None,commit=None,allow_fixture=False,now=None):
    data=path.read_bytes()
    if len(data)>2_000_000:
        raise Invalid('bundle exceeds 2 MB limit')
    if not re.fullmatch('[0-9a-f]{64}',expected_sha) or hashlib.sha256(data).hexdigest()!=expected_sha:
        raise Invalid('exact-byte digest mismatch')
    def pairs(entries):
        result={}
        for k,v in entries:
            if k in result:raise Invalid('duplicate JSON key')
            result[k]=v
        return result
    b=json.loads(data.decode('utf-8'),object_pairs_hook=pairs)
    validate_schema('evidence-bundle-v1',b)
    fixture=b['mode']=='fixture'
    if fixture and not allow_fixture:
        raise Invalid('fixture cannot become production evidence')
    if not fixture:
        if not producer or not commit or b['producer']['repository']!=producer or b['producer']['commit']!=commit or not re.fullmatch('[0-9a-f]{40}',commit):
            raise Invalid('pinned producer identity/commit mismatch')
        if b['producer']['protocol']!='signals-evidence-v1':
            raise Invalid('unsupported producer protocol')
    sources=unique(b['sources'],'source');claims=unique(b['claims'],'claim');candidates=unique(b['candidates'],'candidate')
    concepts=read_yaml(ROOT/'concepts.yaml')['concepts']
    aliases={'browser-validation':'quality.visual'}
    ids=b['need'].get('concept_ids',[])
    mapped=[aliases.get(id,id) for id in ids]
    if any(id not in concepts for id in mapped):
        raise Invalid('unresolved concept ID')
    for source in sources.values():
        public_url(source['uri'])
        if not fixture and source['source_class']=='fixture':raise Invalid('fixture source in real evidence')
    for claim in claims.values():
        if any(id not in sources for id in claim['source_ids']):
            raise Invalid('unresolved source citation')
    for candidate in candidates.values():
        public_url(candidate['canonical_uri'])
        if any(id not in claims for id in candidate['claim_ids']):
            raise Invalid('unresolved claim citation')
        if candidate['disposition'] in ('adopt','trial'):
            if not candidate['claim_ids'] or not any(claims[id]['status'] in ('observed','supported') for id in candidate['claim_ids']):
                raise Invalid('adoption/trial lacks supported claims')
    if (not sources or not claims or not candidates) and not b['limitations']:
        raise Invalid('empty evidence requires an honest limitation')
    ext=b.get('extensions',{})
    # Extensions are opaque non-authoritative data. Unknown policy IDs cannot grant authority.
    for key,value in ext.items():
        if key in ('privacy','privacy_scope') or key.endswith(('.privacy','.privacy_scope')):
            if value not in ('public','public-only','public_sources_only'):
                raise Invalid('inadmissible privacy scope')
        if key in ('policy_id','policy_ids') or key.endswith(('.policy_id','.policy_ids')):
            raise Invalid('unknown extension policy cannot acquire authority')
    now=now or datetime.now(timezone.utc)
    created=datetime.fromisoformat(b['created_at'].replace('Z','+00:00'))
    if created>now:raise Invalid('future evidence creation date')
    ages={};unknown=[]
    for source in sources.values():
        date=source.get('observed_at')
        if date is None:unknown.append(source['id']);continue
        observed=datetime.fromisoformat(date.replace('Z','+00:00'))
        if observed>now:raise Invalid('future source observation')
        ages[source['id']]=(now-observed).days
    return {'input_schema_version':b['schema_version'],'bundle_id':b['bundle_id'],'bundle_sha256':expected_sha,
            'producer':b['producer'],'mode':b['mode'],'concept_ids':mapped,
            'admitted_as':'fixture-test' if fixture else 'pinned-peer-evidence',
            'source_age_days':ages,'unknown_freshness_ids':unknown,
            'age_interpretation':'Observation age is information, not claim currency or an adoption cutoff.',
            'sources':list(sources.values()),'claims':list(claims.values()),
            'recommendations':list(candidates.values()),'constraints':b['need'].get('constraints',[]),
            'activation':False,'extensions_authority':'none',
            'limitations':b['limitations']+['Hashes verify bytes and local pinned origin, not truth. Claim/source ID resolution does not prove claim support. Recommendations and constraints require a Context adoption decision.']}

def load_bundle(path,expected_sha,producer=None,commit=None,allow_fixture=False,now=None):
    """Frozen v1 summary: retain its historical age label for old callers only."""
    result=inspect_bundle(path,expected_sha,producer,commit,allow_fixture,now)
    ages=result.pop('source_age_days')
    result.pop('age_interpretation')
    result['schema_version']=result.pop('input_schema_version')
    result['stale_source_ids']=[id for id,days in ages.items() if days>30]
    return result

def consume_checkpoint(status_path,expected_repository):
    """Compatibility entry point for frozen checkpoint callers."""
    from legacy_evidence import consume_checkpoint as legacy
    return legacy(status_path,expected_repository,load_bundle)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundle',type=Path,nargs='?')
    p.add_argument('--sha256');p.add_argument('--producer');p.add_argument('--commit')
    p.add_argument('--checkpoint',type=Path)
    p.add_argument('--legacy-summary',action='store_true',help='Retain frozen v1 age labels; not a current freshness policy')
    args=p.parse_args()
    if args.checkpoint:
        result=consume_checkpoint(args.checkpoint,args.producer)
    else:
        if not args.bundle or not args.sha256:raise Invalid('bundle and --sha256 required')
        reader=load_bundle if args.legacy_summary else inspect_bundle
        result=reader(args.bundle,args.sha256,args.producer,args.commit)
    print(encoded(result).decode(),end='')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('context-ai evidence: '+str(e),file=sys.stderr);sys.exit(1)
