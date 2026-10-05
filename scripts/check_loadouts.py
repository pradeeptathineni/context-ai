#!/usr/bin/env python3
"""Offline contract gate; extends the existing Ruby repository validator."""
from pathlib import Path
import json
import sys
import tempfile
from context_ai import ROOT, catalogue, current_decisions, read_yaml, resolve, validate_schema, inside
from jsonschema import Draft202012Validator

def check():
    for p in (ROOT/'schemas').glob('*.schema.json'):
        Draft202012Validator.check_schema(json.loads(p.read_text()))
    decisions=current_decisions()
    concepts=read_yaml(ROOT/'concepts.yaml')
    ids=set(concepts['concepts'])
    for id,detail in concepts['details'].items():
        if id not in ids:raise ValueError('unknown detailed concept')
        for path in detail['modules']+detail['evidence']:
            if not inside(ROOT,path).is_file():raise ValueError('broken concept resource')
        for d in detail['decisions']:
            if d not in decisions:raise ValueError('unresolved concept decision')
    seed_aliases={
        'agent-instruction-entrypoint':'context.instructions','progressive-procedure-packaging':'context.skills',
        'canonical-behavior-format':'context.instructions','loadout-definition':'context.loadouts',
        'evidence-decision-separation':'research.confidence','context-runtime-boundary':'context.loadouts',
        'web-design-workflow':'web.design','frontend-design-reference':'web.design','react-web-guidance':'web.design',
        'browser-accessibility-validation':'quality.accessibility','signals-foundation':'context.loadouts',
        'source-selection-policy':'research.confidence','version-control-guidance':'delivery.git','code-commenting-guidance':'quality.comments'}
    for d in decisions.values():
        if seed_aliases.get(d['concept'],d['concept']) not in ids:raise ValueError('unresolved decision concept')
        for field in ('rationale','applicability','rollback','revisit_when'):
            if not isinstance(d[field],str) or not d[field].strip():raise ValueError('incomplete decision '+d['id'])
        for field in ('evidence','alternatives','unknowns','validation'):
            if not isinstance(d[field],list) or not d[field]:raise ValueError('incomplete decision '+d['id'])
    with tempfile.TemporaryDirectory() as td:
        for id,d in catalogue().items():
            validate_schema('loadout',d)
            resolve([id],Path(td).resolve(),'codex')
    print('Loadout validation passed: 8 manifests, source pins, decisions, concepts and schemas.')

if __name__=='__main__':
    try:check()
    except Exception as e:print('Loadout validation: '+str(e),file=sys.stderr);sys.exit(1)
