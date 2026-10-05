#!/usr/bin/env python3
"""Pinned, project-local context composition. Manifests never execute commands."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse, unquote

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
BEGIN = '<!-- context-ai:begin -->'
END = '<!-- context-ai:end -->'

class Invalid(ValueError):
    pass

class UniqueLoader(yaml.SafeLoader):
    pass

def mapping(loader, node, deep=False):
    result = {}
    for key, value in node.value:
        k = loader.construct_object(key, deep=deep)
        if not isinstance(k, str) or k in result:
            raise Invalid('duplicate or non-string YAML key')
        result[k] = loader.construct_object(value, deep=deep)
    return result

UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)

def read_yaml(path):
    data = path.read_text(encoding='utf-8')
    if len(data) > 2_000_000:
        raise Invalid('YAML exceeds bounded input size')
    if any(isinstance(e, yaml.AliasEvent) for e in yaml.parse(data)):
        raise Invalid('YAML aliases are not supported')
    return yaml.load(data, Loader=UniqueLoader)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def encoded(data):
    return (json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)+'\n').encode()

def inside(root, name):
    p = Path(name)
    if not isinstance(name, str) or p.is_absolute() or not p.parts or any(x in ('.','..') for x in name.split('/')):
        raise Invalid('unsafe relative path: '+str(name))
    target = root / p
    for item in [target, *target.parents]:
        if item == root:
            break
        if item.is_symlink():
            raise Invalid('symlink in approved path: '+name)
    if not target.resolve().is_relative_to(root.resolve()):
        raise Invalid('escaping path: '+name)
    return target

def validate_schema(name, value):
    schema = json.loads(inside(ROOT, 'schemas/'+name+'.schema.json').read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)

def catalogue():
    return {p.stem: read_yaml(p) for p in (ROOT/'loadouts').glob('*.yaml')}

def current_decisions():
    decisions = {}
    for p in sorted((ROOT/'decisions').glob('*.yaml')):
        for d in read_yaml(p)['decisions']:
            key = (d['id'],d['revision'])
            if key in decisions:
                raise Invalid('duplicate decision revision')
            decisions[key] = d
    for d in decisions.values():
        if d.get('supersedes'):
            predecessor = (d['id'],d['supersedes'])
            if predecessor not in decisions or d['revision'] <= d['supersedes']:
                raise Invalid('invalid decision successor')
    return {id: max((v for (k,_),v in decisions.items() if k==id), key=lambda d:d['revision']) for id,_ in decisions}

def resources(names):
    output = {}
    pending = list(names)
    while pending:
        name = pending.pop(0)
        if name in output:
            continue
        p = inside(ROOT, name)
        if not p.is_file():
            raise Invalid('missing resource: '+name)
        data = p.read_bytes()
        output[name] = data
        if p.suffix == '.md':
            for link in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)', data.decode('utf-8')):
                if urlparse(link).scheme or link.startswith('#'):
                    continue
                rel = unquote(link.split('#')[0].split('?')[0].strip('<>'))
                dest = Path(os.path.normpath(str(Path(name).parent/rel)))
                dep = inside(ROOT, dest.as_posix())
                if dep.is_dir():
                    pending.extend(x.relative_to(ROOT).as_posix() for x in sorted(dep.rglob('*')) if x.is_file())
                    continue
                pending.append(dest.as_posix())
    return output

def capability_states(selected, registry):
    states = {}
    for key, required in selected.items():
        if key not in registry:
            raise Invalid('unknown capability: '+key)
        item = registry[key]
        if item['kind'] == 'command':
            available = shutil.which(item['command']) is not None
        elif item['kind'] == 'resource':
            available = inside(ROOT,item['path']).is_file()
        else:
            raise Invalid('unsupported capability kind')
        states[key] = {'requirement':required,'available':available,'definition':item}
        if required == 'required' and not available:
            raise Invalid('missing required capability: '+key)
    return states

def resolve(ids, project, provider, options=None):
    if provider != 'codex':
        raise Invalid('supported adapter is codex')
    all_loads = catalogue()
    ordered, active = [], set()
    def visit(id):
        if id in active:
            raise Invalid('composition cycle: '+id)
        if id in ordered:
            return
        if id not in all_loads:
            raise Invalid('unknown loadout: '+id)
        d = all_loads[id]
        validate_schema('loadout',d)
        active.add(id)
        for parent in d['compose']:
            visit(parent)
        active.remove(id)
        ordered.append(id)
    for id in ids:
        visit(id)
    if not ordered:
        raise Invalid('select at least one loadout')
    stages, skills, capabilities, checks, decisions = {}, [], {}, [], []
    resolved_options = {}
    for id in ordered:
        d = all_loads[id]
        for key, value in d['options'].items():
            if key in resolved_options and resolved_options[key] != value:
                raise Invalid('conflicting loadout option: '+key)
            resolved_options[key] = value
        for stage, modules in d['stages'].items():
            stages.setdefault(stage,[])
            stages[stage] = list(dict.fromkeys(stages[stage]+modules))
        skills = list(dict.fromkeys(skills+d['skills']))
        checks.extend({'loadout':id,'recipe':c} for c in d['checks'])
        decisions = list(dict.fromkeys(decisions+d['decisions']))
        for c, state in d['capabilities'].items():
            capabilities[c] = 'required' if state=='required' or capabilities.get(c)=='required' else 'optional'
    for key, value in (options or {}).items():
        if key != 'brand' or value not in ('quiet','expressive') or 'brand' not in resolved_options:
            raise Invalid('unsupported option '+key)
        resolved_options[key] = value
    current = current_decisions()
    for d in decisions:
        if d not in current:
            raise Invalid('unknown decision '+d)
    registry = read_yaml(ROOT/'capabilities.yaml')['capabilities']
    states = capability_states(capabilities,registry)
    files = resources([p for paths in stages.values() for p in paths]+['skills/context-loadout/SKILL.md','providers/openai/codex.md','LICENSE'])
    for c in capabilities:
        if registry[c]['kind']=='resource':
            files.update(resources([registry[c]['path']]))
            for extra in registry[c].get('files',[]):
                files.update(resources([extra]))
    for p in ['requirements.txt','decisions/bootstrap.yaml','capabilities.yaml']:
        files[p] = inside(ROOT,p).read_bytes()
    for id in ordered:
        files['loadouts/'+id+'.yaml'] = (ROOT/'loadouts'/ (id+'.yaml')).read_bytes()
    file_hashes = {name:digest(data) for name,data in sorted(files.items())}
    tree_hash = digest(encoded(file_hashes))
    try:
        revision = subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],stderr=subprocess.DEVNULL,text=True).strip()
    except subprocess.CalledProcessError:
        revision = 'exported-tree'
    lock = {'schema_version':1,'provider':provider,'project':str(project),'library_revision':revision,
            'source_tree_sha256':tree_hash,'loadouts':ordered,'stages':stages,'skills':skills,
            'capabilities':states,'options':resolved_options,'checks':checks,
            'decisions':{d:current[d] for d in decisions},'resources':file_hashes}
    validate_schema('lock',lock)
    return lock,files

def router(lock):
    lines = [BEGIN,'## Context AI project loadout',
             'Project instructions and explicit task authority take precedence. Use the pinned `.context-ai/lock.json`.',
             'Read `.context-ai/resources/skills/context-loadout/SKILL.md` for selection and use receipts.',
             'Load only the modules for the current stage:']
    for stage, paths in lock['stages'].items():
        lines.append('- '+stage+': '+', '.join('`.context-ai/resources/'+p+'`' for p in paths))
    lines.extend(['A selected recipe is not execution or deployment permission.',END])
    return '\n'.join(lines)+'\n'

def materialized(lock, files):
    output = {'.context-ai/resources/'+p:data for p,data in files.items()}
    for skill in lock['skills']:
        if not re.fullmatch('[a-z][a-z0-9-]{0,63}',skill):
            raise Invalid('unsafe skill id')
        path = 'skills/context-loadout/SKILL.md' if skill=='context-loadout' else lock['capabilities'][skill]['definition']['path']
        body = ('---\nname: '+skill+'\ndescription: '+('Use pinned Context AI project loadouts.' if skill=='context-loadout' else lock['capabilities'][skill]['definition']['description'])+'\n---\n\nRead [pinned instructions](../../../.context-ai/resources/'+path+') when this procedure is relevant. Follow project instructions and user brand direction first. No tool or hook is activated by this file.\n')
        output['.agents/skills/'+skill+'/SKILL.md'] = body.encode()
    return output

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp = tempfile.mkstemp(prefix='.context-ai-write-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def installed(project):
    p=inside(project,'.context-ai/lock.json')
    if not p.exists():
        return None
    lock = json.loads(p.read_text())
    validate_schema('installation',lock)
    if lock['resolution']['project'] != str(project):
        raise Invalid('installation belongs to another project')
    for name in lock['owned']:
        if not (name.startswith('.context-ai/resources/') or re.fullmatch(r'\.agents/skills/[a-z][a-z0-9-]{0,63}/SKILL\.md',name)):
            raise Invalid('unapproved owned path')
        inside(project,name)
    return lock

def instruction_block(text):
    if text.count(BEGIN)!=1 or text.count(END)!=1:
        raise Invalid('missing, duplicate or edited routing markers')
    start=text.index(BEGIN); finish=text.index(END)+len(END)
    if finish < start:
        raise Invalid('reversed routing markers')
    if text[finish:finish+1]=='\n':
        finish+=1
    return text[start:finish]

def apply(project,lock,files):
    previous=installed(project)
    targets=materialized(lock,files)
    old_owned=previous['owned'] if previous else {}
    # Preflight every path before any mutation; user modifications always conflict.
    for name in set(targets)|set(old_owned):
        p=inside(project,name)
        if p.exists():
            if not p.is_file() or name not in old_owned or digest(p.read_bytes())!=old_owned[name]:
                raise Invalid('user file conflict: '+name)
        elif name in old_owned:
            raise Invalid('missing owned file: '+name)
    agents=inside(project,'AGENTS.md')
    text=agents.read_text() if agents.exists() else ''
    old_block=previous['routing_block'] if previous else None
    if old_block:
        if instruction_block(text)!=old_block:
            raise Invalid('edited managed AGENTS block')
        updated=text.replace(old_block,router(lock),1)
    else:
        if BEGIN in text or END in text:
            raise Invalid('unowned routing block')
        updated=text+('' if not text or text.endswith('\n') else '\n')+router(lock)
    state={'schema_version':1,'resolution':lock,'owned':{p:digest(d) for p,d in targets.items()},
           'routing_block':router(lock),'agents_created':previous['agents_created'] if previous else not agents.exists()}
    validate_schema('installation',state)
    for name,data in targets.items():
        p=inside(project,name)
        if not p.exists() or p.read_bytes()!=data:
            atomic(p,data)
    for name in set(old_owned)-set(targets):
        inside(project,name).unlink()
    if updated!=text:
        atomic(agents,updated.encode())
    statepath=inside(project,'.context-ai/lock.json')
    data=encoded(state)
    if not statepath.exists() or statepath.read_bytes()!=data:
        atomic(statepath,data)
    return {'applied':lock['loadouts'],'resource_count':len(files),'lock_sha256':digest(data)}

def verify(project):
    state=installed(project)
    if not state:
        raise Invalid('no installation')
    for name,sha in state['owned'].items():
        p=inside(project,name)
        if not p.is_file() or digest(p.read_bytes())!=sha:
            raise Invalid('managed file drift: '+name)
    if instruction_block(inside(project,'AGENTS.md').read_text()) != state['routing_block']:
        raise Invalid('routing block drift')
    resolution=state['resolution']
    capability_states({c:s['requirement'] for c,s in resolution['capabilities'].items()},
                      {c:s['definition'] for c,s in resolution['capabilities'].items() if s['definition']['kind']=='command'}) if all(s['definition']['kind']=='command' for s in resolution['capabilities'].values()) else None
    return {'verified':resolution['loadouts'],'owned_files':len(state['owned'])}

def undo(project):
    state=installed(project)
    if not state:
        raise Invalid('no installation')
    conflicts=[]; retained={}
    for name,sha in state['owned'].items():
        p=inside(project,name)
        if p.is_file() and digest(p.read_bytes())==sha:
            p.unlink()
        elif p.exists():
            conflicts.append(name); retained[name]=sha
    agents=inside(project,'AGENTS.md')
    text=agents.read_text() if agents.exists() else ''
    try:
        block=instruction_block(text)
    except Invalid:
        block=None
    if block==state['routing_block']:
        result=text.replace(block,'',1)
        if state['agents_created'] and not result:
            agents.unlink()
        else:
            atomic(agents,result.encode())
    else:
        conflicts.append('AGENTS.md')
    if conflicts:
        state['owned']=retained
        atomic(inside(project,'.context-ai/lock.json'),encoded(state))
    else:
        inside(project,'.context-ai/lock.json').unlink()
    return {'undone':not conflicts,'preserved_conflicts':conflicts}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['list','explain','plan','apply','verify','undo','refresh'])
    parser.add_argument('loadouts',nargs='*')
    parser.add_argument('--project')
    parser.add_argument('--provider',default='codex')
    parser.add_argument('--brand',choices=['quiet','expressive'])
    args=parser.parse_args()
    if args.command in ('list','explain'):
        loads=catalogue()
        result=loads if args.command=='list' else {id:loads[id] for id in args.loadouts}
    else:
        if not args.project or not Path(args.project).is_absolute() or not Path(args.project).is_dir() or Path(args.project).is_symlink():
            raise Invalid('an existing absolute project directory is required')
        project=Path(args.project).resolve()
        if args.command=='verify':
            result=verify(project)
        elif args.command=='undo':
            result=undo(project)
        else:
            ids=args.loadouts
            if args.command=='refresh' and not ids:
                state=installed(project)
                if not state:
                    raise Invalid('no installation to refresh')
                ids=state['resolution']['loadouts']
            lock,files=resolve(ids,project,args.provider,{'brand':args.brand} if args.brand else {})
            if args.command=='apply':
                result=apply(project,lock,files)
            else:
                state=installed(project)
                old=state['resolution']['resources'] if state else {}
                result={'resolution':lock,'writes':list(materialized(lock,files))+['AGENTS.md','.context-ai/lock.json'],
                        'changes':[p for p in set(old)|set(lock['resources']) if old.get(p)!=lock['resources'].get(p)],
                        'activation':'proposed'}
    print(encoded(result).decode(),end='')

if __name__=='__main__':
    try:
        main()
    except Exception as e:
        print('context-ai: '+str(e),file=sys.stderr)
        sys.exit(1)
