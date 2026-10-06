"""Frozen checkpoint transport; excluded from task selection and source-age policy."""
import hashlib
import json
import re
from context_ai import ROOT, Invalid, inside

def consume_checkpoint(status_path,expected_repository,load_bundle):
    owner_root=status_path.parent.resolve()
    status=json.loads(status_path.read_text())
    campaign = status.get('campaign') == 'pact-hrr-2026-10-05'
    owner = status.get('producer') if campaign else status.get('owner')
    if campaign and (status.get('state') != 'ready' or status.get('repository') != expected_repository or not isinstance(status.get('revision'),int) or status['revision'] < 1):
        raise Invalid('incomplete or unexpected campaign checkpoint')
    if owner!='signals' or not re.fullmatch('[0-9a-f]{40}',status['commit']):
        raise Invalid('unexpected checkpoint owner/commit')
    if not campaign and status['contract_sha256']!=hashlib.sha256((ROOT/'schemas/evidence-bundle-v1.schema.json').read_bytes()).hexdigest():
        raise Invalid('unsupported peer contract')
    bundles=[]
    for artifact in status['artifacts']:
        p=inside(owner_root,artifact['path'])
        data=p.read_bytes()
        if hashlib.sha256(data).hexdigest()!=artifact['sha256']:
            raise Invalid('checkpoint artifact digest mismatch')
        if p.suffix=='.json':
            value=json.loads(data)
            if isinstance(value,dict) and 'bundle_id' in value and 'mode' in value:
                bundles.append((p,artifact['sha256']))
    if not bundles:raise Invalid('no completed real evidence bundle')
    return [load_bundle(p,sha,expected_repository,status['commit']) for p,sha in bundles]
