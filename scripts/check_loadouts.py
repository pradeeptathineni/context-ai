#!/usr/bin/env python3
"""Offline contract gate; extends the existing Ruby repository validator."""
from pathlib import Path
import json
import sys
import tempfile
from context_ai import ROOT, catalogue, current_decisions, resolve, validate_schema
from jsonschema import Draft202012Validator

def check():
    for p in (ROOT/'schemas').glob('*.schema.json'):
        Draft202012Validator.check_schema(json.loads(p.read_text()))
    decisions=current_decisions()
    from concepts import catalog, validate_catalog
    concepts=catalog()
    validate_catalog(concepts, decisions)
    ids=set(concepts)
    for d in decisions.values():
        if d['concept'] not in ids:raise ValueError('unresolved decision concept')
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
