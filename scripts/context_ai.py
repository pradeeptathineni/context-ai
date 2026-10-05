#!/usr/bin/env python3
"""Pinned, project-local context composition. Manifests never execute commands."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

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
    if not isinstance(name,str) or re.search(r'[\x00-\x1f\x7f\\]',name):
        raise Invalid('unsafe relative path: '+str(name))
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
    registry = Registry().with_resource('https://context-ai.local/schemas/lock.schema.json', Resource.from_contents(json.loads((ROOT/'schemas/lock.schema.json').read_text())))
    Draft202012Validator(schema, registry=registry, format_checker=FormatChecker()).validate(value)

def catalogue():
    return {p.stem: read_yaml(p) for p in (ROOT/'loadouts').glob('*.yaml')}

def current_decisions():
    decisions = {}
    for p in sorted((ROOT/'decisions').glob('*.yaml')):
        document=read_yaml(p)
        defaults=document.get('defaults',{})
        if set(defaults)-{'applicability','unknowns','validation','rollback'}:
            raise Invalid('unsupported decision default')
        for record in document['decisions']:
            d={**defaults,**record}
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

def resource_path(root, name):
    path = inside(root, name)
    if path.name.casefold() in ('agents.md', 'agents.override.md', 'claude.md', 'gemini.md') or any(part.casefold() in ('.agents', '.codex') for part in path.parts):
        raise Invalid('untrusted instruction activation: '+name)
    return path

def resources(names):
    registry = read_yaml(ROOT/'resources.yaml') if (ROOT/'resources.yaml').exists() else {'dependencies': {}}
    dependencies = registry['dependencies']
    output, active = {}, set()
    def visit(name):
        if name in active:
            raise Invalid('resource dependency cycle: '+name)
        if name in output:
            return
        p = resource_path(ROOT, name)
        if not p.is_file():
            raise Invalid('missing resource: '+name)
        active.add(name)
        for dep in dependencies.get(name, []):
            visit(dep)
        active.remove(name)
        output[name] = p.read_bytes()
    for name in names:
        visit(name)
    return output

def source_notices(files):
    if not (ROOT/'sources.lock.json').exists():
        return {}
    result = {}
    covered = set()
    for source in json.loads((ROOT/'sources.lock.json').read_text())['sources']:
        selected = set(files) & set(source['files'])
        if not selected:
            continue
        covered.update(selected)
        notices = {p for p in source['files'] if Path(p).name in ('LICENSE','LICENSE.txt','NOTICE.md')}
        # Preserve the attributed upstream README when a snapshot has no separate notice.
        if not notices:
            notices = {p for p in source['files'] if p.endswith('upstream-README.md')}
        for path in selected | notices:
            data = inside(ROOT,path).read_bytes()
            if digest(data) != source['files'][path]:
                raise Invalid('pinned upstream drift: '+path)
            if path in notices:
                result[path] = data
    if any(p.startswith('sourced/') and p not in covered for p in files):
        raise Invalid('unregistered sourced resource')
    return result

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

def selection(ids, options=None):
    """Compose the same declarations for explanation and materialization."""
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
        if key not in resolved_options:
            raise Invalid('option does not apply to this selection: '+key)
        if key=='brand' and (not isinstance(value,str) or not value.strip() or len(value)>2000):
            raise Invalid('brand intent must be 1-2000 characters')
        if key=='design_procedure' and value not in ('guided','lightweight'):
            raise Invalid('unsupported design procedure')
        if key not in ('brand','design_procedure'):
            raise Invalid('unsupported option '+key)
        resolved_options[key] = value
    return {'loadouts':ordered,'stages':stages,'skills':skills,'capabilities':capabilities,
            'checks':checks,'decisions':decisions,'options':resolved_options}

def selected_decisions(ids):
    current = current_decisions()
    for id in ids:
        if id not in current:
            raise Invalid('unknown decision '+id)
    return {id:current[id] for id in ids}

def capability_definitions(options):
    registry = read_yaml(ROOT/'capabilities.yaml')['capabilities']
    if options.get('design_procedure')=='lightweight':
        registry['context-web-design']={**registry['context-web-design'],
            'path':'procedures/web-design-lightweight.md',
            'description':'Use concise frontend design guidance for bounded web changes.',
            'files':['sourced/anthropic/design/instruction.md','sourced/anthropic/design/LICENSE.txt']}
    return registry

def explain(ids, options=None):
    selected=selection(ids,options)
    registry=capability_definitions(selected['options'])
    loads=catalogue()
    for id in selected['capabilities']:
        if id not in registry:
            raise Invalid('unknown capability: '+id)
    return {'loadouts':{id:loads[id] for id in selected['loadouts']},
            'composition':selected['loadouts'],'stages':selected['stages'],
            'options':selected['options'],'checks':selected['checks'],
            'decisions':selected_decisions(selected['decisions']),
            'capabilities':{id:registry[id] for id in selected['capabilities']},
            'capability_requirements':selected['capabilities']}

def source_revision():
    # An exported tree nested in a consumer repository must not inherit its commit.
    try:
        top=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','--show-toplevel'],
                                    stderr=subprocess.DEVNULL,text=True).strip()
        if Path(top).resolve()==ROOT.resolve():
            return subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],
                                           stderr=subprocess.DEVNULL,text=True).strip()
    except subprocess.CalledProcessError:
        pass
    marker=ROOT/'REVISION'
    revision=marker.read_text().strip() if marker.is_file() else ''
    return revision if re.fullmatch(r'[0-9a-f]{40}',revision) else 'exported-tree'

def resolve(ids, project, provider, options=None):
    if provider != 'codex':
        raise Invalid('supported adapter is codex')
    selected=selection(ids,options)
    decisions=selected_decisions(selected['decisions'])
    registry=capability_definitions(selected['options'])
    states = capability_states(selected['capabilities'],registry)
    files = resources([p for paths in selected['stages'].values() for p in paths]+['skills/context-loadout/SKILL.md','providers/openai/codex.md','LICENSE'])
    for c in selected['capabilities']:
        if registry[c]['kind']=='resource':
            files.update(resources([registry[c]['path']]))
            for extra in registry[c].get('files',[]):
                files.update(resources([extra]))
    files.update(source_notices(files))
    for id in selected['loadouts']:
        files['loadouts/'+id+'.yaml'] = (ROOT/'loadouts'/ (id+'.yaml')).read_bytes()
    file_hashes = {name:digest(data) for name,data in sorted(files.items())}
    tree_hash = digest(encoded(file_hashes))
    lock = {**selected,'schema_version':2,'provider':provider,'project':'.','library_revision':source_revision(),
            'source_tree_sha256':tree_hash,'capabilities':states,
            'decisions':decisions,'resources':file_hashes}
    validate_schema('lock',lock)
    return lock,files

def router(lock):
    lines = [BEGIN,'## Context AI project loadout',
             'Project instructions and explicit task authority take precedence. Use the pinned `.context-ai/lock.json`.',
             'Read `.context-ai/resources/skills/context-loadout/SKILL.md` when changing the selection; report actual reads and checks in the task result.',
             'Load only the modules for the current stage:']
    for stage, paths in lock['stages'].items():
        lines.append('- '+stage+': '+', '.join('`.context-ai/resources/'+p+'`' for p in paths))
    lines.extend(['A selected recipe is not execution or deployment permission.',END])
    return '\n'.join(lines)+'\n'

def materialized(lock, files):
    output = {'.context-ai/resources/'+p:data for p,data in files.items()}
    if len({name.casefold() for name in output}) != len(output):
        raise Invalid('case-colliding resource paths')
    for skill in lock['skills']:
        if not skill.startswith('context-'):
            raise Invalid('unapproved skill router: '+skill)
        if not re.fullmatch('[a-z][a-z0-9-]{0,63}',skill):
            raise Invalid('unsafe skill id')
        path = 'skills/context-loadout/SKILL.md' if skill=='context-loadout' else lock['capabilities'][skill]['definition']['path']
        if path not in files:
            raise Invalid('missing selected skill instructions: '+path)
        description = 'Use pinned Context AI project loadouts.' if skill=='context-loadout' else lock['capabilities'][skill]['definition']['description']
        metadata = yaml.safe_dump({'name':skill,'description':description},sort_keys=False)
        body = '---\n'+metadata+'---\n\nRead [pinned instructions](../../../.context-ai/resources/'+path+') when this procedure is relevant. Follow project instructions and user brand direction first. No tool or hook is activated by this file.\n'
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

def transaction_path(project, name):
    if name not in ('AGENTS.md','.context-ai/lock.json') and not (name.startswith('.context-ai/resources/') or re.fullmatch(r'\.agents/skills/context-[a-z0-9-]+/SKILL\.md',name)):
        raise Invalid('unapproved recovery path: '+name)
    return inside(project,name)

def recover(project):
    journal=inside(project,'.context-ai/pending.json')
    if not journal.exists():return {'recovered':True,'preserved_conflicts':[]}
    state=json.loads(journal.read_text())
    if state.get('schema_version')!=1 or state.get('bound_project')!=str(project) or set(state.get('before',{}))!=set(state.get('after',{})):
        raise Invalid('invalid or differently bound recovery record')
    operations=[]
    for name, before in state['before'].items():
        p=transaction_path(project,name)
        old=base64.b64decode(before,validate=True) if before is not None else None
        expected=state['after'][name]
        if expected is not None and not re.fullmatch('[0-9a-f]{64}',expected):raise Invalid('invalid recovery digest')
        operations.append((name,p,old,expected))
    conflicts=[]
    for name,p,old,expected in operations:
        if p.exists() and not p.is_file():
            conflicts.append(name);continue
        current=p.read_bytes() if p.exists() else None
        if current==old:continue
        current_sha=digest(current) if current is not None else None
        if current_sha!=expected:
            conflicts.append(name);continue
        if old is None:
            p.unlink()
        else:
            atomic(p,old)
    if not conflicts:journal.unlink()
    return {'recovered':not conflicts,'preserved_conflicts':conflicts}


def installed(project, allow_rebind=False):
    if inside(project,'.context-ai/pending.json').exists():
        raise Invalid('incomplete application; run recover before ownership operations')
    p=inside(project,'.context-ai/lock.json')
    if not p.exists():
        return None
    lock = json.loads(p.read_text())
    validate_schema('installation',lock)
    resolution=lock['resolution']
    if digest(encoded(resolution['resources'])) != resolution['source_tree_sha256']:
        raise Invalid('source tree digest does not match resource pins')
    for name,sha in resolution['resources'].items():
        if not lock.get('undo_pending',False) and lock['owned'].get('.context-ai/resources/'+name) != sha:
            raise Invalid('ownership does not match resource pins')
    bound = lock.get('bound_project',lock['resolution']['project'])
    if bound != str(project) and not allow_rebind:
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
    validate_schema('lock',lock)
    if {name:digest(data) for name,data in files.items()} != lock['resources'] or digest(encoded(lock['resources'])) != lock['source_tree_sha256']:
        raise Invalid('application bytes do not match the pin')
    for name in files:
        resource_path(ROOT,name)
    if any(path not in files for paths in lock['stages'].values() for path in paths):
        raise Invalid('missing selected stage instructions')
    if lock['schema_version']==1 and lock['project']!=str(project):
        raise Invalid('legacy pin belongs to another project')
    previous=installed(project)
    targets=materialized(lock,files)
    if previous and previous.get('undo_pending'):
        raise Invalid('resolve preserved undo conflicts before applying')
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
    state={'schema_version':2,'bound_project':str(project),'resolution':lock,'owned':{p:digest(d) for p,d in targets.items()},
           'routing_block':router(lock),'agents_created':previous['agents_created'] if previous else not agents.exists(),
           'agents_added_newline':previous.get('agents_added_newline',False) if previous else bool(text and not text.endswith('\n'))}
    validate_schema('installation',state)
    data=encoded(state)
    desired={**targets,'AGENTS.md':updated.encode(),'.context-ai/lock.json':data}
    desired.update({name:None for name in set(old_owned)-set(targets)})
    before={}
    for name in desired:
        p=transaction_path(project,name)
        before[name]=base64.b64encode(p.read_bytes()).decode() if p.exists() else None
    journal=inside(project,'.context-ai/pending.json')
    atomic(journal,encoded({'schema_version':1,'bound_project':str(project),'before':before,
                            'after':{name:digest(value) if value is not None else None for name,value in desired.items()}}))
    try:
        for name,value in desired.items():
            p=transaction_path(project,name)
            if value is None:
                if p.exists():p.unlink()
            elif not p.exists() or p.read_bytes()!=value:
                atomic(p,value)
    except Exception:
        try:
            recover(project)
        except Exception as recovery_error:
            raise Invalid('application interrupted; recovery bytes retained in .context-ai/pending.json') from recovery_error
        raise
    journal.unlink()
    return {'applied':lock['loadouts'],'resource_count':len(files),'lock_sha256':digest(data)}

def verify(project, allow_rebind=False):
    state=installed(project, allow_rebind=allow_rebind)
    if not state:
        raise Invalid('no installation')
    if state.get('undo_pending'):
        raise Invalid('incomplete undo; preserved conflicts remain')
    for name,sha in state['owned'].items():
        p=inside(project,name)
        if not p.is_file() or digest(p.read_bytes())!=sha:
            raise Invalid('managed file drift: '+name)
    if instruction_block(inside(project,'AGENTS.md').read_text()) != state['routing_block']:
        raise Invalid('routing block drift')
    resolution=state['resolution']
    probes, optional_unavailable = [], []
    for key,entry in resolution['capabilities'].items():
        definition=entry['definition']
        if definition['kind']=='command':
            available=shutil.which(definition['command']) is not None
            if entry['requirement']=='required' and available:
                probe_command(definition['command'])
                probes.append(definition['command']+' --version')
        else:
            path=inside(project,'.context-ai/resources/'+definition['path'])
            available=path.is_file() and digest(path.read_bytes())==resolution['resources'].get(definition['path'])
        if entry['requirement']=='required' and not available:
            raise Invalid('installed required capability unavailable: '+key)
        if entry['requirement']=='optional' and not available:
            optional_unavailable.append({'id':key,'boundary':definition['boundary']})
    return {'verified':resolution['loadouts'],'owned_files':len(state['owned']),
            'scope':'installation integrity and required runtime probes',
            'required_command_probes':probes,'optional_unavailable':optional_unavailable,
            'project_checks':'not_run','suggested_checks':resolution['checks']}

def probe_command(command):
    probes={'python3':['python3','--version'],'git':['git','--version'],'node':['node','--version']}
    if command not in probes:
        raise Invalid('no reviewed required command probe: '+command)
    try:
        run=subprocess.run(probes[command],capture_output=True,text=True,timeout=5,check=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise Invalid('required command invocation failed: '+command) from error
    output=(run.stdout+run.stderr).strip()
    if command=='python3':
        match=re.search(r'Python (\d+)\.(\d+)',output)
        if not match or tuple(map(int,match.groups()))<(3,10):raise Invalid('Python 3.10+ is required')
    elif command=='node':
        match=re.match(r'v(\d+)',output)
        if not match or int(match[1])<20:raise Invalid('Node 20+ is required')
    elif not output.startswith('git version '):
        raise Invalid('unexpected Git version response')
    return output

def rebind(project):
    # Verify the copied installation before changing only its local ownership binding.
    verify(project,allow_rebind=True)
    state=installed(project,allow_rebind=True)
    state['schema_version']=2
    state['bound_project']=str(project)
    state['resolution']['schema_version']=2
    state['resolution']['project']='.'
    validate_schema('installation',state)
    atomic(inside(project,'.context-ai/lock.json'),encoded(state))
    return {'rebound':True,'verified':verify(project),'portable_resolution':state['resolution']}

def pinned_files(lock):
    validate_schema('lock',lock)
    if lock['schema_version']!=2:raise Invalid('export/rebind a legacy lock before portable apply')
    if digest(encoded(lock['resources']))!=lock['source_tree_sha256']:
        raise Invalid('source tree digest does not match resource pins')
    files={}
    for name,sha in lock['resources'].items():
        path=resource_path(ROOT,name)
        if not path.is_file():raise Invalid('missing pinned resource: '+name)
        data=path.read_bytes()
        if digest(data)!=sha:raise Invalid('pinned resource drift: '+name)
        files[name]=data
    expected,_=resolve(lock['loadouts'],Path.cwd(),lock['provider'],lock['options'])
    for field in ['loadouts','stages','skills','options','checks','decisions','resources']:
        if lock[field]!=expected[field]:raise Invalid('imported pin differs from reviewed source '+field)
    definitions=lambda value:{key:{'requirement':entry['requirement'],'definition':entry['definition']} for key,entry in value.items()}
    if definitions(lock['capabilities'])!=definitions(expected['capabilities']):
        raise Invalid('imported capability definitions differ from reviewed source')
    return files


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
    if state.get('routing_removed'):
        pass
    elif block==state['routing_block']:
        removable=('\n'+block) if state.get('agents_added_newline') and ('\n'+block) in text else block
        result=text.replace(removable,'',1)
        if state['agents_created'] and not result:
            agents.unlink()
        else:
            atomic(agents,result.encode())
        state['routing_removed']=True
    else:
        conflicts.append('AGENTS.md')
    if conflicts:
        state['owned']=retained
        state['undo_pending']=True
        atomic(inside(project,'.context-ai/lock.json'),encoded(state))
    else:
        inside(project,'.context-ai/lock.json').unlink()
    return {'undone':not conflicts,'preserved_conflicts':conflicts}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['list','explain','decisions','plan','apply','verify','undo','refresh','export','rebind','recover'])
    parser.add_argument('loadouts',nargs='*')
    parser.add_argument('--project')
    parser.add_argument('--lock',type=Path,help='Apply an exact portable lock against this source checkout')
    parser.add_argument('--provider',default='codex')
    parser.add_argument('--brand',help='Project visual intent, 1-2000 characters')
    parser.add_argument('--design-procedure',choices=['guided','lightweight'])
    args=parser.parse_args()
    if args.command in ('list','explain','decisions'):
        loads=catalogue()
        if args.command=='list':
            result={id:{'description':d['description'],'characteristics':d['characteristics']} for id,d in sorted(loads.items())}
        elif args.command=='decisions':
            if args.brand is not None or args.design_procedure is not None or args.lock:
                raise Invalid('decisions accepts only optional loadout selections')
            result=selected_decisions(selection(args.loadouts)['decisions']) if args.loadouts else current_decisions()
        else:
            if args.provider!='codex':raise Invalid('supported adapter is codex')
            options={}
            if args.brand is not None:options['brand']=args.brand
            if args.design_procedure is not None:options['design_procedure']=args.design_procedure
            result=explain(args.loadouts,options)
    else:
        if not args.project or not Path(args.project).is_absolute() or not Path(args.project).is_dir() or Path(args.project).is_symlink():
            raise Invalid('an existing absolute project directory is required')
        project=Path(args.project).resolve()
        if args.lock and (args.command!='apply' or args.loadouts or args.brand or args.design_procedure):
            raise Invalid('--lock is only for apply without new selections/options')
        if args.command=='recover':
            result=recover(project)
        elif args.command=='export':
            state=installed(project)
            if not state:raise Invalid('no installation to export')
            result=state['resolution'].copy();result['schema_version']=2;result['project']='.'
            validate_schema('lock',result)
        elif args.command=='rebind':
            result=rebind(project)
        elif args.command=='verify':
            result=verify(project)
        elif args.command=='undo':
            result=undo(project)
        else:
            ids=args.loadouts
            state=installed(project)
            if args.command=='refresh' and not ids:
                state=installed(project)
                if not state:
                    raise Invalid('no installation to refresh')
                ids=state['resolution']['loadouts']
            options={}
            if args.command=='refresh' and state:
                applicable=resolve(ids,project,args.provider)[0]['options']
                options={key:value for key,value in state['resolution']['options'].items() if key in applicable}
            if args.brand is not None:options['brand']=args.brand
            if args.design_procedure is not None:options['design_procedure']=args.design_procedure
            if args.lock:
                lock=json.loads(args.lock.read_text());files=pinned_files(lock)
            else:
                lock,files=resolve(ids,project,args.provider,options)
            if args.command=='apply':
                result=apply(project,lock,files)
            else:
                state=installed(project)
                old=state['resolution']['resources'] if state else {}
                targets=materialized(lock,files)
                result={'resolution':lock,'writes':list(targets)+['AGENTS.md','.context-ai/lock.json'],
                        'removals':sorted(set(state['owned'])-set(targets)) if state else [],
                        'changes':sorted(p for p in set(old)|set(lock['resources']) if old.get(p)!=lock['resources'].get(p)),
                        'activation':'proposed'}
    print(encoded(result).decode(),end='')

if __name__=='__main__':
    try:
        main()
    except Exception as e:
        print('context-ai: '+str(e),file=sys.stderr)
        sys.exit(1)
