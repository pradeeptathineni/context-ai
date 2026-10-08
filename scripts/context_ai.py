#!/usr/bin/env python3
"""Pinned, project-local context composition. Manifests never execute commands."""
import argparse
import base64
import fnmatch
from functools import lru_cache
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

def capability_registry():
    document=read_yaml(ROOT/'capabilities.yaml')
    validate_schema('capabilities',document)
    for key,spec in document['options'].items():
        if spec.get('type')=='text':continue
        if spec['default'] not in spec['alternatives']:
            raise Invalid('unsupported default option: '+key)
        for alternative in spec['alternatives'].values():
            for alias,target in alternative['aliases'].items():
                if alias not in document['capabilities'] or target not in document['capabilities']:
                    raise Invalid('unresolved option capability: '+alias+' -> '+target)
            for conflict in alternative.get('incompatible',[]):
                other=document['options'].get(conflict['option'],{})
                if conflict['value'] not in other.get('alternatives',{}):
                    raise Invalid('unresolved option incompatibility')
    return document

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

def active_files():
    """Every guidance file a loadout, capability or packet route can load."""
    files=set(['overlays/orchestration.md','overlays/model-deliberation.md','core/prior-art.md'])
    for d in catalogue().values():
        for paths in d['stages'].values():files.update(paths)
    for item in capability_registry()['capabilities'].values():
        if item['kind']=='resource':files.add(item['path'])
    return files

def ownership():
    """One active owner per concern; archived files stay off every active route."""
    document=read_yaml(ROOT/'ownership.yaml')
    validate_schema('ownership',document)
    pinned={s['id'] for s in json.loads((ROOT/'sources.lock.json').read_text())['sources']}
    commands={k for k,v in capability_registry()['capabilities'].items() if v['kind']=='command'}
    owner_of={}
    for concern,spec in document['concerns'].items():
        for path in spec.get('files',[]):
            if path in owner_of:
                raise Invalid('file has two concern owners: '+path+' ('+owner_of[path]+', '+concern+')')
            if not inside(ROOT,path).is_file():
                raise Invalid('missing concern file: '+path)
            owner_of[path]=concern
        if 'upstream' in spec and spec['upstream'] not in pinned:
            raise Invalid('concern upstream is not pinned in sources.lock.json: '+spec['upstream'])
        for tool in spec.get('tools',[]):
            if tool not in commands:
                raise Invalid('unknown concern tool capability: '+tool)
        for path in spec.get('archived',[]):
            if not inside(ROOT,path).is_file():
                raise Invalid('missing archived file: '+path)
    active=active_files()
    uncovered=sorted(active-set(owner_of))
    if uncovered:
        raise Invalid('active files without a concern owner: '+', '.join(uncovered))
    archived=[p for p in active if p.startswith('archive/')]
    deps=read_yaml(ROOT/'resources.yaml')['dependencies']
    archived+=[d for key,values in deps.items() for d in [key,*values] if d.startswith('archive/')]
    if archived:
        raise Invalid('archived file on an active route: '+', '.join(sorted(set(archived))))
    return document['concerns'],owner_of

def selected_concerns(files):
    concerns,owner_of=ownership()
    result={}
    for path in dict.fromkeys(files):
        concern=owner_of.get(path)
        if concern:
            spec=concerns[concern]
            entry=result.setdefault(concern,{'owner_kind':spec['owner_kind'],'owner':spec['files'][0],'selected':[]})
            entry['selected'].append(path)
            for key in ('upstream','adapted_from','native_names','tools'):
                if key in spec:entry[key]=spec[key]
    return result

def resource_path(root, name):
    path = inside(root, name)
    # Only the selected name is checked: a source checkout may itself live under .codex/worktrees.
    if path.name.casefold() in ('agents.md', 'agents.override.md', 'claude.md', 'gemini.md') or any(part.casefold() in ('.agents', '.codex', '.claude') for part in Path(name).parts):
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

def project_data(project, path):
    """Bounded manifest read; workspace/package symlinks must stay in their owner."""
    target=project/path
    if not target.resolve().is_relative_to(project.resolve()):
        raise Invalid('tool discovery path escapes project/workspace: '+str(target))
    if not target.is_file():
        return None
    if target.stat().st_size>2_000_000:
        raise Invalid('tool manifest exceeds bounded input size: '+str(target))
    return json.loads(target.read_text(encoding='utf-8'))

def workspace_match(member, pattern):
    """Supported workspace globs match segments; '*' never grants another level."""
    if not pattern or len(pattern)>500 or any(x in pattern for x in ('{','}','(',')','\\')):
        raise Invalid('unsupported workspace glob; use segment *, ?, [], ** or inspect explicitly')
    parts=pattern.split('/')
    if any(part in ('','.','..') for part in parts):
        raise Invalid('unsupported workspace glob; use relative path segments')
    path=member.split('/')
    @lru_cache(maxsize=None)
    def match(i,j):
        if i==len(parts):return j==len(path)
        if parts[i]=='**':
            return match(i+1,j) or (j<len(path) and not path[j].startswith('.') and match(i,j+1))
        return (j<len(path) and (not path[j].startswith('.') or parts[i].startswith('.'))
                and fnmatch.fnmatchcase(path[j],parts[i]) and match(i+1,j+1))
    return match(0,0)

def node_project(project):
    manifest=project_data(project,Path('package.json')) or {}
    owner=project
    # Only an ancestor explicitly declaring this member can supply hoisted packages.
    for parent in project.parents:
        if not (parent/'package.json').is_file() and not (parent/'pnpm-workspace.yaml').is_file():
            continue
        candidate=project_data(parent,Path('package.json')) or {}
        patterns=candidate.get('workspaces',[])
        if isinstance(patterns,dict):patterns=patterns.get('packages',[])
        if (parent/'pnpm-workspace.yaml').is_file():
            path=inside(parent,'pnpm-workspace.yaml')
            patterns=(read_yaml(path) or {}).get('packages',[])
        member=project.relative_to(parent).as_posix()
        if not isinstance(patterns,list) or any(not isinstance(x,str) for x in patterns):
            raise Invalid('unsupported workspace declaration')
        matches=[(p.startswith('!'),workspace_match(member,p[1:] if p.startswith('!') else p)) for p in patterns]
        positive=any(found for excluded,found in matches if not excluded)
        excluded=any(found for excluded,found in matches if excluded)
        if positive and not excluded:
            owner=parent
            break
        # The nearest workspace/package owner is a boundary, not arbitrary ancestor search.
        break
    manager=manifest.get('packageManager')
    if owner!=project:
        manager=manager or (project_data(owner,Path('package.json')) or {}).get('packageManager')
    locks={'pnpm-lock.yaml':'pnpm','yarn.lock':'yarn','package-lock.json':'npm','bun.lock':'bun','bun.lockb':'bun'}
    detected=set(value for path,value in locks.items() if (owner/path).is_file())
    if manager is not None:
        if not isinstance(manager,str) or not re.fullmatch(r'(npm|pnpm|yarn|bun)@[^\s/]+',manager):
            raise Invalid('unsupported packageManager declaration; inspect it explicitly')
        command=manager.split('@')[0]
    else:
        command=next(iter(detected)) if len(detected)==1 else None
    return manifest,owner,manager,command,sorted(detected)

def discover_command(definition, project):
    """Static locations are candidates, never proof of readiness or execution."""
    command=definition['command']; resolver=definition.get('resolver')
    result={'source':'PATH','location':shutil.which(command),'exercised':False,
            'uncertainty':'Version, authentication, service readiness and project checks not tested.'}
    if resolver=='python':
        declared=[name for name in ('pyproject.toml','requirements.txt','Pipfile') if (project/name).is_file()]
        env=project/'.venv'
        result['declared']=declared
        if env.exists() or env.is_symlink():
            if env.is_symlink():
                raise Invalid('project .venv symlink outside managed boundary; use an in-project environment')
            cfg=inside(project,'.venv/pyvenv.cfg')
            if (env/'bin').is_symlink():
                raise Invalid('project .venv/bin symlink outside managed boundary; only interpreter links are supported')
            executable=env/'bin/python'
            # Standard venv interpreters may link to a system-managed runtime.
            # Read no home paths/configuration beyond this explicit venv marker.
            result.update(source='project .venv',location=str(executable) if cfg.is_file() and executable.is_file() else None,
                          uncertainty='Managed interpreter link allowed; interpreter/version and dependencies not exercised.')
        elif declared:
            result.update(location=None,source='project Python declaration',
                          uncertainty='No .venv found. Select the documented project environment explicitly; PATH/Context interpreter is not substituted.')
    elif resolver in ('node','package-manager','playwright'):
        manifest,owner,manager,manager_command,locks=node_project(project)
        result.update(manifest=str(project/'package.json'),workspace=str(owner),package_manager=manager,
                      lockfile_managers=locks,scripts=manifest.get('scripts',{}),
                      scripts_authority='Candidates only; not evaluated or executed.')
        if resolver=='package-manager':
            result.update(source='packageManager or lockfile',location=shutil.which(manager_command) if manager_command else None,
                          command=manager_command,
                          uncertainty='Manager may be a network-resolving shim; do not probe via package resolution. Conflicting/absent lockfiles need explicit project choice.')
        elif resolver=='playwright':
            deps={**manifest.get('dependencies',{}),**manifest.get('devDependencies',{})}
            result.update(declared={key:deps[key] for key in ('@playwright/test','playwright','playwright-core') if key in deps},
                          installed=[],uncertainty='Browser binaries, launch and behavior not tested. No npx or configuration imports performed.')
            for base in dict.fromkeys([project,owner]):
                for package in ('@playwright/test','playwright','playwright-core'):
                    path=Path('node_modules')/package/'package.json'
                    info=project_data(owner,(base/path).relative_to(owner))
                    if not info:continue
                    if info.get('name')!=package:
                        raise Invalid('local package identity mismatch: '+str(base/path))
                    bins=info.get('bin',{})
                    cli=bins.get('playwright') if isinstance(bins,dict) else bins if isinstance(bins,str) else None
                    location=None
                    if cli:
                        # A package declares data, not arbitrary executable authority.
                        if not isinstance(cli,str) or Path(cli).is_absolute() or '..' in Path(cli).parts:
                            raise Invalid('unsafe local Playwright bin declaration')
                        target=base/'node_modules'/package/cli
                        if not target.resolve().is_relative_to(owner):
                            raise Invalid('Playwright CLI escapes project/workspace')
                        if target.is_file():location=str(target)
                    result['installed'].append({'package':package,'version':info.get('version'),'manifest':str(base/path),'cli':location})
            local=next((item['cli'] for item in result['installed'] if item['cli']),None)
            if local:result.update(source='installed project package',location=local)
    elif resolver is not None:
        raise Invalid('unsupported tool resolver: '+resolver)
    return result

def capability_states(selected, registry, project, strict=True):
    states = {}
    for key, required in selected.items():
        if key not in registry:
            raise Invalid('unknown capability: '+key)
        item = registry[key]
        if item['kind'] == 'command':
            discovery=discover_command(item,project)
            available = discovery['location'] is not None
        elif item['kind'] == 'resource':
            available = inside(ROOT,item['path']).is_file()
        else:
            raise Invalid('unsupported capability kind')
        states[key] = {'requirement':required,'available':available,'definition':item}
        if item['kind']=='command':states[key]['discovery']=discovery
        if strict and required == 'required' and not available:
            raise Invalid('missing required capability: '+key+'; '+discovery.get('uncertainty','') if item['kind']=='command' else 'missing required capability: '+key)
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
    stages, skills, capabilities, checks, decisions = {}, [], {}, [], []
    resolved_options = {}
    declarations = capability_registry()['options']
    for id in ordered:
        d = all_loads[id]
        for key, value in d['options'].items():
            if value is None:
                value=declarations.get(key,{}).get('default')
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
        resolved_options[key] = value
    for key, value in resolved_options.items():
        if key not in declarations:
            raise Invalid('unsupported option: '+key)
        spec = declarations[key]
        if spec.get('type') == 'text':
            if not isinstance(value,str) or not value.strip() or len(value)>spec['max_length']:
                raise Invalid(key+' intent must be 1-'+str(spec['max_length'])+' characters')
        else:
            if not isinstance(value,str) or value not in spec['alternatives']:
                raise Invalid('unsupported option '+key+': '+str(value))
            for conflict in spec['alternatives'][value].get('incompatible', []):
                if resolved_options.get(conflict['option']) == conflict['value']:
                    raise Invalid('incompatible options: '+key+' and '+conflict['option'])
    return {'loadouts':ordered,'stages':stages,'skills':skills,'capabilities':capabilities,
            'checks':checks,'decisions':decisions,'options':resolved_options}

def selected_decisions(ids):
    current = current_decisions()
    for id in ids:
        if id not in current:
            raise Invalid('unknown decision '+id)
    return {id:current[id] for id in ids}

def capability_definitions(options):
    document = capability_registry()
    registry = document['capabilities'].copy()
    aliases = {}
    for key, value in options.items():
        spec = document['options'][key]
        if spec.get('type') == 'text':
            continue
        for alias, target in spec['alternatives'][value].get('aliases', {}).items():
            if alias not in registry or target not in registry:
                raise Invalid('unresolved option capability: '+alias+' -> '+target)
            if alias in aliases and aliases[alias] != target:
                raise Invalid('conflicting capability alternatives: '+alias)
            aliases[alias] = target
    # Targets come from the base registry, never another option's replacement.
    for alias, target in aliases.items():
        registry[alias] = document['capabilities'][target]
    return registry

def explain(ids, options=None):
    selected=selection(ids,options)
    registry=capability_definitions(selected['options'])
    loads=catalogue()
    for id in selected['capabilities']:
        if id not in registry:
            raise Invalid('unknown capability: '+id)
    routed=[p for paths in selected['stages'].values() for p in paths]
    routed+=[registry[c]['path'] for c in selected['capabilities'] if registry[c]['kind']=='resource']
    return {'loadouts':{id:loads[id] for id in selected['loadouts']},
            'composition':selected['loadouts'],'stages':selected['stages'],
            'concerns':selected_concerns(routed),
            'options':selected['options'],'checks':selected['checks'],
            'option_choices':{key:capability_registry()['options'][key] for key in selected['options']},
            'decisions':selected_decisions(selected['decisions']),
            'capabilities':{id:registry[id] for id in selected['capabilities']},
            'capability_requirements':selected['capabilities']}

def model_recommendation(attributes):
    """Literal first-match policy; task interpretation and host settings stay external."""
    policy=read_yaml(ROOT/'models/routing.yaml')
    keys={key for route in policy['routes'] for key in route['match']}
    if set(attributes)-keys:
        raise Invalid('unknown model route attributes: '+', '.join(sorted(set(attributes)-keys)))
    if '*' in attributes.values():
        raise Invalid('model wildcard belongs to policy, not task attributes')
    route=next((r for r in policy['routes'] if all(value=='*' or attributes.get(key)==value
                for key,value in r['match'].items())),None)
    if route is None:
        route=next(r for r in policy['routes'] if r['id']==policy['matching']['fallback_route'])
    def binding(choice):
        model=policy['models'][choice['model_profile']]
        return {**choice,'provider':model['provider'],'model':model['model'],
                'availability':model['availability']}
    return {'route':route['id'],'attributes':attributes,'recommendation':binding(route['select']),
            'fallback':binding(route['fallback']) if 'fallback' in route else None,
            'policy':'models/routing.yaml','reviewed':policy['reviewed'],'applied':False}

def task_packet(profile, project):
    """Resolve advice without materialization, command probes or semantic classification."""
    validate_schema('task-profile',profile)
    context=profile.get('context',{'mode':'direct'})
    stages,options,loadouts,checks,decision_ids={},{},[],[],[]
    selected=profile.get('capabilities',{}).copy()
    roots=context.get('resources',[]).copy()
    if context['mode']=='loadout':
        composition=selection(context['loadouts'],context.get('options'))
        loadouts=composition['loadouts'];options=composition['options']
        for stage in context['stages']:
            if stage not in composition['stages']:
                raise Invalid('stage does not apply to selection: '+stage)
            stages[stage]=composition['stages'][stage]
            roots.extend(stages[stage])
        checks=composition['checks'];decision_ids=composition['decisions']
        # Resource capabilities belong only to a requested stage. Command requirements
        # remain composition requirements, but their discovery is never execution.
        registry=capability_definitions(options)
        for key,requirement in composition['capabilities'].items():
            definition=registry[key]
            if definition['kind']=='command' or set(definition.get('stages',context['stages'])) & set(context['stages']):
                selected[key]='required' if 'required' in (selected.get(key),requirement) else 'optional'
    orchestration=profile.get('orchestration','single_agent')
    pact=profile.get('pact',{'required':False,'reason':'No unresolved capability decision was requested.'})
    if pact['required']:
        roots.append('core/prior-art.md')
    if 'model' in profile:
        roots.append('overlays/model-deliberation.md')
    if orchestration!='single_agent':
        roots.append('overlays/orchestration.md')
    if orchestration=='fresh_review':
        roots.append('procedures/review-fresh.md')
    registry=capability_definitions(options)
    for key in selected:
        if key not in registry:
            raise Invalid('unknown capability: '+key)
        definition=registry[key]
        if definition['kind']=='resource':
            roots.extend([definition['path'],*definition.get('files',[])])
    roots=list(dict.fromkeys(roots))
    if any(Path(p).suffix.lower()!='.md' or p.split('/')[0] not in
           ('core','overlays','domains','procedures','skills','providers','sourced')
           for p in context.get('resources',[])):
        raise Invalid('direct resources must be Context guidance Markdown paths')
    files=resources(roots)
    files.update(source_notices(files))
    # Alternatives that are prerequisites of another (direct review for fresh
    # review) compose; competing primary procedures do not.
    for spec in capability_registry()['options'].values():
        paths={registry[target]['path'] for alt in spec.get('alternatives',{}).values()
               for target in alt.get('aliases',{}).values() if registry[target]['kind']=='resource'}
        chosen=paths & set(files)
        primary={path for path in chosen if not any(path in resources([other]) for other in chosen if other!=path)}
        if len(primary)>1:
            raise Invalid('conflicting primary procedures: '+', '.join(sorted(primary)))
    fresh='procedures/review-fresh.md' in files
    if fresh and orchestration!='fresh_review':
        raise Invalid('fresh review guidance requires explicit orchestration=fresh_review')
    if 'review' in stages and 'review_mode' in options:
        expected='fresh' if orchestration=='fresh_review' else 'direct'
        if options['review_mode']!=expected:
            raise Invalid('review_mode and orchestration must agree for the review stage')
    states=capability_states(selected,registry,project,strict=False)
    unresolved=profile.get('unresolved',[]).copy()
    for key,state in states.items():
        if not state['available']:
            unresolved.append(key+': '+state['requirement']+' candidate unavailable; '+state['definition']['boundary'])
        if state['definition']['kind']=='command':
            unresolved.append(key+': '+state['discovery']['uncertainty'])
    model=model_recommendation(profile['model']) if 'model' in profile else {'applied':False,'recommendation':None}
    if 'model' in profile:
        unresolved.append('Model/reasoning binding and access need active-host verification; explicit session choices win.')
    if orchestration!='single_agent':
        unresolved.append('Delegation authority, bounded ownership and native host support need agent verification; no agents spawned.')
    return {'schema_version':1,'task':profile['task'],
            'authority':'Advice only. User and project instructions always win.',
            'context':{'mode':context['mode'],'loadouts':loadouts,'options':options,'stages':stages,
                       'reads':list(files),'resource_sha256':{p:digest(data) for p,data in files.items()},
                       'procedures':[p for p in files if p.startswith('procedures/')]},
            'capabilities':states,'native_host_tools':'Host-reported separately; local discovery cannot establish native readiness.',
            'model':model,'orchestration':{'recommendation':orchestration,'applied':False},
            'selection_outcome':'focused' if files or selected or 'model' in profile or orchestration!='single_agent' else 'native-sufficient',
            'pact':pact,'verification':{'expectations':profile['verification'],
                'suggested_checks':checks,'project_checks':'not_run'},
            'unresolved':list(dict.fromkeys(unresolved)),
            'decisions':{key:{'revision':record['revision'],'concept':record['concept']}
                         for key,record in selected_decisions(decision_ids).items()},
            'execution':'not_run','writes':[]}

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

PROVIDERS = {'codex':('codex',),'claude':('claude',),'both':('codex','claude')}
SKILL_DIRS = {'codex':'.agents/skills','claude':'.claude/skills'}
ADAPTER_DOCS = {'codex':'providers/openai/codex.md','claude':'providers/anthropic/claude-code.md'}
CLAUDE_FILES = ('CLAUDE.md','.claude/CLAUDE.md','CLAUDE.local.md')

def hosts(provider):
    if provider not in PROVIDERS:
        raise Invalid('supported adapters are codex, claude and both')
    return PROVIDERS[provider]

def with_capabilities(selected, extras):
    """Explicit project-chosen resource procedures beyond the loadouts; never added from evidence."""
    registry=capability_registry()['capabilities']
    for key in extras:
        if key not in registry or registry[key]['kind']!='resource' or not key.startswith('context-'):
            raise Invalid('--with accepts only registered context-* resource capabilities: '+str(key))
        selected['capabilities'][key]='required'
        if key not in selected['skills']:
            selected['skills'].append(key)
    return selected

def resolve(ids, project, provider, options=None, extras=()):
    hosts(provider)
    selected=selection(ids,options)
    extras=list(dict.fromkeys(extras))
    if extras:
        selected=with_capabilities(selected,extras)
        selected['extra_capabilities']=extras
    decisions=selected_decisions(selected['decisions'])
    registry=capability_definitions(selected['options'])
    states = capability_states(selected['capabilities'],registry,project)
    # Machine observations belong to local reports, never portable resource pins.
    for entry in states.values():
        entry.pop('discovery',None)
    files = resources([p for paths in selected['stages'].values() for p in paths]+(['skills/context-loadout/SKILL.md','LICENSE']+[ADAPTER_DOCS[host] for host in hosts(provider)] if selected['loadouts'] else ['LICENSE']))
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
    lines = [BEGIN,'## Context AI project selection',
             'Project instructions and explicit task authority take precedence. Ordinary covered work uses native tools; activate selected guidance only for a relevant risk or capability gap.']
    if not lock['stages'] and not lock['capabilities']:
        return '\n'.join(lines+['Selection: native-sufficient; no additional task guidance. Context manages setup/refresh/undo separately.',END])+'\n'
    if 'context-output' in lock['capabilities']:
        lines.append('Before reading a large log or running a verbose command, keep raw output outside context. Use `python3 .context-ai/resources/scripts/context_output.py inspect LOG --query error` for bounded line evidence, or `run --log NEW_LOG -- COMMAND ...` to capture once and preserve its exit status. Retrieve another query/range before concluding; omitted lines are not evidence of absence. Native Read/Grep/Glob bypass shell filters: bound those reads too.')
    lines.append('Selected modules below are available by stage; read only what the current task needs:')
    staged=set()
    for stage, paths in lock['stages'].items():
        staged.update(paths)
        lines.append('- '+stage+': '+', '.join('`.context-ai/resources/'+p+'`' for p in paths))
    for key, entry in lock['capabilities'].items():
        # A procedure already routed by a stage is not listed twice.
        if entry['definition']['kind']=='resource' and entry['definition']['path'] not in staged:
            lines.append('- '+key+': read `.context-ai/resources/'+entry['definition']['path']+'` when relevant.')
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
        if skill=='context-loadout':
            metadata=yaml.safe_load(files[path].decode().split('---',2)[1])
            description=metadata['description']
        else:
            description=lock['capabilities'][skill]['definition']['description']
        metadata = yaml.safe_dump({'name':skill,'description':description},sort_keys=False)
        # One canonical instruction copy; each host gets a thin router at the same depth.
        body = '---\n'+metadata+'---\n\nRead [pinned instructions](../../../.context-ai/resources/'+path+') when this procedure is relevant. Follow project instructions and user brand direction first. No tool or hook is activated by this file.\n'
        for host in hosts(lock['provider']):
            output[SKILL_DIRS[host]+'/'+skill+'/SKILL.md'] = body.encode()
    return output

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    # mkstemp creates 0600; keep an existing file's mode, else the umask default.
    if path.exists():
        mode=path.stat().st_mode & 0o7777
    else:
        umask=os.umask(0);os.umask(umask);mode=0o666 & ~umask
    fd,tmp = tempfile.mkstemp(prefix='.context-ai-write-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data)
        os.chmod(tmp,mode)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

SKILL_ROUTER = r'\.(agents|claude)/skills/context-[a-z0-9-]+/SKILL\.md'

def transaction_path(project, name):
    if name not in ('AGENTS.md','.context-ai/lock.json','CLAUDE.md','.claude/CLAUDE.md') and not (name.startswith('.context-ai/resources/') or re.fullmatch(SKILL_ROUTER,name)):
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
        if not (name.startswith('.context-ai/resources/') or re.fullmatch(r'\.(agents|claude)/skills/[a-z][a-z0-9-]{0,63}/SKILL\.md',name)):
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

def imports_agents(project, path):
    """Only filesystem identity proves a shared instruction owner; prose is host-owned."""
    return path.is_symlink() and path.resolve() == (project/'AGENTS.md').resolve()

def claude_route(project, previous=None):
    """Native first: Claude Code reads AGENTS.md unless a CLAUDE.md shadows it."""
    owned=(previous or {}).get('claude_routing')
    shadow=[]
    for base in [project,*project.parents]:
        for name in CLAUDE_FILES:
            candidate=base/name
            if candidate.is_file():shadow.append(candidate)
    local=[p for p in shadow if p.parent in (project,project/'.claude')]
    for p in local:
        name=p.relative_to(project).as_posix()
        if name=='CLAUDE.local.md':continue
        if owned and owned['path']==name:
            return {'mode':'managed-block','path':name}
        if imports_agents(project,p):
            return {'mode':'imports-agents','path':name}
    if owned:
        return {'mode':'managed-block','path':owned['path']}
    if not shadow:
        return {'mode':'native-agents','path':None}
    existing=[p.relative_to(project).as_posix() for p in local if p.name!='CLAUDE.local.md']
    return {'mode':'managed-block','path':existing[0] if existing else 'CLAUDE.md'}

def host_routing(project, lock, previous=None):
    result={}
    for host in hosts(lock['provider']):
        if host=='codex':
            result['codex']={'mode':'agents-block','path':'AGENTS.md','skills':SKILL_DIRS['codex']}
        else:
            result['claude']={**claude_route(project,previous),'skills':SKILL_DIRS['claude']}
    return result

def skill_metadata(path):
    if path.stat().st_size>2_000_000:raise Invalid('skill metadata exceeds bounded input size')
    text=path.read_text()
    if text.startswith('---\n') and '\n---' in text[4:]:
        metadata=yaml.safe_load(text.split('\n---',1)[0][4:])
        if isinstance(metadata,dict):return metadata
    return {}

def native_inventory(project, owned):
    """Project-local host-managed resources; read only, never written by Context."""
    skills=[]
    for host,folder in SKILL_DIRS.items():
        base=inside(project,folder)
        if not base.is_dir():continue
        for path in sorted(base.glob('*/SKILL.md')):
            name=path.relative_to(project).as_posix()
            if name in owned:continue
            path=inside(project,name)
            skills.append({'host':host,'path':name,'name':skill_metadata(path).get('name',path.parent.name),'folder':path.parent.name})
    plugins=[]
    for name in ('.claude/settings.json','.claude/settings.local.json'):
        p=inside(project,name)
        if p.is_file():
            try:enabled=json.loads(p.read_text()).get('enabledPlugins',{})
            except json.JSONDecodeError:enabled={}
            plugins.extend({'host':'claude','source':name,'plugin':key} for key,on in sorted(enabled.items()) if on)
    p=inside(project,'.codex/config.toml')
    if p.is_file():
        plugins.extend({'host':'codex','source':'.codex/config.toml','plugin':m} for m in re.findall(r'^\[plugins\."([^"]+)"\]',p.read_text(),re.M))
    return {'skills':skills,'plugins':plugins}

def preflight(project, lock, files):
    """Everything apply would do, as data; conflicts are reported, never resolved silently."""
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
    conflicts=[]
    if previous and previous.get('undo_pending'):
        conflicts.append('resolve preserved undo conflicts before applying')
    old_owned=previous['owned'] if previous else {}
    inventory=native_inventory(project,old_owned)
    # Hosts match frontmatter names, not folder names; refuse duplicate local names.
    for skill in inventory['skills']:
        if skill['name'] in lock['skills'] or skill['folder'] in lock['skills']:
            conflicts.append('existing skill name conflict: '+skill['name']+' ('+skill['path']+')')
    routed=[p for paths in lock['stages'].values() for p in paths]+[e['definition']['path'] for e in lock['capabilities'].values() if e['definition']['kind']=='resource']
    duplicates=[]
    for concern,entry in selected_concerns(routed).items():
        for skill in inventory['skills']:
            if skill['name'] in entry.get('native_names',[]):
                duplicates.append({'concern':concern,'existing':skill['path'],'name':skill['name'],'context_owner':entry['owner']})
    conflicts.extend('duplicate concern owner: '+d['concern']+' is already routed by '+d['existing']+'; remove it or deselect the Context route' for d in duplicates)
    for name in set(targets)|set(old_owned):
        p=inside(project,name)
        if p.exists():
            if not p.is_file() or name not in old_owned or digest(p.read_bytes())!=old_owned[name]:
                conflicts.append('user file conflict: '+name)
        elif name in old_owned:
            conflicts.append('missing owned file: '+name)
    agents=inside(project,'AGENTS.md')
    text=agents.read_bytes().decode("utf-8") if agents.exists() else ''
    old_block=previous['routing_block'] if previous else None
    updated=None
    if old_block:
        try:current=instruction_block(text)
        except Invalid:current=None
        if current!=old_block:
            conflicts.append('edited managed AGENTS block')
        else:
            updated=text.replace(old_block,router(lock),1)
    elif BEGIN in text or END in text:
        conflicts.append('unowned routing block')
    else:
        updated=text+('' if not text or text.endswith('\n') else '\n')+router(lock)
    routing=host_routing(project,lock,previous)
    claude_desired={}; claude_state=None
    old_claude=previous.get('claude_routing') if previous else None
    want=routing.get('claude',{}).get('mode')=='managed-block'
    if old_claude and (not want or routing['claude']['path']!=old_claude['path']):
        p=inside(project,old_claude['path'])
        ctext=p.read_bytes().decode("utf-8") if p.exists() else ''
        try:current=instruction_block(ctext)
        except Invalid:current=None
        if current!=old_claude['block']:
            conflicts.append('edited managed '+old_claude['path']+' block')
        else:
            removable=('\n'+current) if old_claude.get('added_newline') and ('\n'+current) in ctext else current
            rest=ctext.replace(removable,'',1)
            claude_desired[old_claude['path']]=None if old_claude['created'] and not rest else rest.encode()
        old_claude=None
    if want:
        name=routing['claude']['path']
        p=inside(project,name)
        ctext=p.read_bytes().decode("utf-8") if p.exists() else ''
        if old_claude:
            try:current=instruction_block(ctext)
            except Invalid:current=None
            if current!=old_claude['block']:
                conflicts.append('edited managed '+name+' block')
            else:
                claude_desired[name]=ctext.replace(old_claude['block'],router(lock),1).encode()
            claude_state={**old_claude,'block':router(lock)}
        elif BEGIN in ctext or END in ctext:
            conflicts.append('unowned routing block in '+name)
        else:
            claude_desired[name]=(ctext+('' if not ctext or ctext.endswith('\n') else '\n')+router(lock)).encode()
            claude_state={'path':name,'block':router(lock),'created':not p.exists(),'added_newline':bool(ctext and not ctext.endswith('\n'))}
    state={'schema_version':2,'bound_project':str(project),'resolution':lock,'owned':{p:digest(d) for p,d in targets.items()},
           'routing_block':router(lock),'agents_created':previous['agents_created'] if previous else not agents.exists(),
           'agents_added_newline':previous.get('agents_added_newline',False) if previous else bool(text and not text.endswith('\n'))}
    if claude_state:state['claude_routing']=claude_state
    validate_schema('installation',state)
    desired={**targets,'.context-ai/lock.json':encoded(state)}
    if updated is not None:desired['AGENTS.md']=updated.encode()
    desired.update(claude_desired)
    desired.update({name:None for name in set(old_owned)-set(targets)})
    return {'previous':previous,'targets':targets,'old_owned':old_owned,'state':state,'desired':desired,
            'conflicts':conflicts,'duplicates':duplicates,'inventory':inventory,'host_routing':routing}

def apply(project,lock,files):
    check=preflight(project,lock,files)
    if check['conflicts']:
        raise Invalid('; '.join(check['conflicts']))
    desired=check['desired']
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
    return {'selection_outcome':'focused' if lock['stages'] or lock['capabilities'] else 'native-sufficient',
            'applied':lock['loadouts'],'provider':lock['provider'],'resource_count':len(files),
            'lock_sha256':digest(desired['.context-ai/lock.json']),'host_routing':check['host_routing']}

def upstream_pins(files):
    pins=[]
    for source in json.loads((ROOT/'sources.lock.json').read_text())['sources']:
        selected=sorted(set(files)&set(source['files']))
        if selected:
            pins.append({'id':source['id'],'repository':source['repository'],'revision':source['revision'],
                         'license':source['license'],'files':selected,'update_owner':'context (sources.lock.json)'})
    return pins

def plan(project, lock, files):
    check=preflight(project,lock,files)
    previous=check['previous']
    old=previous['resolution']['resources'] if previous else {}
    old_owned=check['old_owned']; targets=check['targets']
    registry={key:entry for key,entry in lock['capabilities'].items()}
    return {'selection_outcome':'focused' if lock['stages'] or lock['capabilities'] else 'native-sufficient',
            'resolution':lock,
            'writes':sorted(set(targets)|{name for name,value in check['desired'].items() if value is not None}),
            'additions':sorted(set(targets)-set(old_owned)),
            'replacements':sorted(name for name in set(targets)&set(old_owned) if digest(targets[name])!=old_owned[name]),
            'removals':sorted(set(old_owned)-set(targets)),
            'changes':sorted(p for p in set(old)|set(lock['resources']) if old.get(p)!=lock['resources'].get(p)),
            'conflicts':check['conflicts'],'duplicate_concern_owners':check['duplicates'],
            'prerequisites':{key:{'requirement':entry['requirement'],'kind':entry['definition']['kind'],'available':entry['available'],
                                  'boundary':entry['definition']['boundary']} for key,entry in registry.items()},
            'capability_discovery':{key:discover_command(entry['definition'],project) for key,entry in lock['capabilities'].items() if entry['definition']['kind']=='command'},
            'runs_code':{'apply':False,'verify':'bounded version probes for required python3/git/node only'},
            'credentials':'none read or required by Context',
            'host_routing':check['host_routing'],
            'native_managed':check['inventory'],
            'host_management':'Context owns only listed writes; native skills/plugins above stay host-managed and are never modified.',
            'upstream_pins':upstream_pins(files),
            'concerns':selected_concerns(files),
            'activation':'proposed'}

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
    if instruction_block(inside(project,'AGENTS.md').read_bytes().decode('utf-8')) != state['routing_block']:
        raise Invalid('routing block drift')
    claude=state.get('claude_routing')
    if claude:
        p=inside(project,claude['path'])
        if not p.is_file() or instruction_block(p.read_bytes().decode('utf-8'))!=claude['block']:
            raise Invalid('routing block drift: '+claude['path'])
    resolution=state['resolution']
    probes, optional_unavailable, discovery, observed_versions = [], [], {}, {}
    for key,entry in resolution['capabilities'].items():
        definition=entry['definition']
        if definition['kind']=='command':
            observation=discover_command(definition,project)
            discovery[key]=observation
            available=observation['location'] is not None
            if entry['requirement']=='required' and available:
                observed_versions[key]=probe_command(definition['command'],observation['location'])
                observation['exercised']='version only'
                probes.append(definition['command']+' --version')
        else:
            path=inside(project,'.context-ai/resources/'+definition['path'])
            available=path.is_file() and digest(path.read_bytes())==resolution['resources'].get(definition['path'])
        if entry['requirement']=='required' and not available:
            raise Invalid('installed required capability unavailable: '+key)
        if entry['requirement']=='optional' and not available:
            optional_unavailable.append({'id':key,'boundary':definition['boundary']})
    routing=host_routing(project,resolution,state)
    if 'claude' in routing and routing['claude']['mode']=='managed-block' and not claude:
        raise Invalid('Claude Code no longer reads AGENTS.md here (a CLAUDE.md now shadows it); refresh to route Claude')
    return {'verified':resolution['loadouts'],'provider':resolution.get('provider','codex'),'owned_files':len(state['owned']),
            'scope':'installation integrity and required runtime probes',
            'levels':{'files_present':True,'schema_valid':True,
                      'native_discovery':'not_observed; run the host (see providers/) and record what it listed',
                      'runtime_tools':'required version probes passed' if probes else 'no required command probes',
                      'consumer_task':'not_run'},
            'host_routing':routing,
            'required_command_probes':probes,'optional_unavailable':optional_unavailable,
            'capability_discovery':discovery,'observed_versions':observed_versions,
            'project_checks':'not_run','suggested_checks':resolution['checks']}

def probe_command(command, location=None):
    probes={'python3':['python3','--version'],'git':['git','--version'],'node':['node','--version']}
    if command not in probes:
        raise Invalid('no reviewed required command probe: '+command)
    try:
        argv=[location or probes[command][0],*probes[command][1:]]
        run=subprocess.run(argv,capture_output=True,text=True,timeout=5,check=True)
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
    expected,_=resolve(lock['loadouts'],Path.cwd(),lock['provider'],lock['options'],lock.get('extra_capabilities',[]))
    for field in ['loadouts','stages','skills','options','checks','decisions','resources','extra_capabilities']:
        if lock.get(field)!=expected.get(field):raise Invalid('imported pin differs from reviewed source '+field)
    definitions=lambda value:{key:{'requirement':entry['requirement'],'definition':entry['definition']} for key,entry in value.items()}
    if definitions(lock['capabilities'])!=definitions(expected['capabilities']):
        raise Invalid('imported capability definitions differ from reviewed source')
    return files

def remove_block(project, name, block, created, added_newline):
    path=inside(project,name)
    text=path.read_bytes().decode("utf-8") if path.exists() else ''
    try:
        current=instruction_block(text)
    except Invalid:
        current=None
    if current!=block:
        return False
    removable=('\n'+block) if added_newline and ('\n'+block) in text else block
    result=text.replace(removable,'',1)
    if created and not result:
        path.unlink()
    else:
        atomic(path,result.encode())
    return True

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
    if not state.get('routing_removed'):
        if remove_block(project,'AGENTS.md',state['routing_block'],state['agents_created'],state.get('agents_added_newline')):
            state['routing_removed']=True
        else:
            conflicts.append('AGENTS.md')
    claude=state.get('claude_routing')
    if claude and not claude.get('removed'):
        if remove_block(project,claude['path'],claude['block'],claude['created'],claude.get('added_newline')):
            claude['removed']=True
        else:
            conflicts.append(claude['path'])
    if conflicts:
        state['owned']=retained
        state['undo_pending']=True
        atomic(inside(project,'.context-ai/lock.json'),encoded(state))
    else:
        inside(project,'.context-ai/lock.json').unlink()
    return {'undone':not conflicts,'preserved_conflicts':conflicts}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['list','explain','decisions','owners','tools','packet','plan','apply','verify','undo','refresh','export','rebind','recover','catalog','profiles','select','suggestions','trial','evolve','pause','resume','decide','assess'])
    parser.add_argument('loadouts',nargs='*')
    parser.add_argument('--project')
    parser.add_argument('--profile',type=Path,help='Task profile for packet, or catalog project profile for delivery')
    parser.add_argument('--state',type=Path,help='Private local library assessment/evolution state')
    parser.add_argument('--input',type=Path,help='Exact pinned Signals evidence bundle')
    parser.add_argument('--sha256')
    parser.add_argument('--producer')
    parser.add_argument('--commit')
    parser.add_argument('--interest')
    parser.add_argument('--fixture',action='store_true',help='Allow labeled fixture evidence for mechanical checks only')
    parser.add_argument('--wheel-cache',type=Path,help='Inspected exact wheel cache for a trusted executable trial')
    parser.add_argument('--destination',type=Path,help='New disposable trial directory')
    parser.add_argument('--execute',action='store_true',help='Execute trusted eligible trials after isolation probes')
    parser.add_argument('--lock',type=Path,help='Apply an exact portable lock against this source checkout')
    parser.add_argument('--provider',choices=sorted(PROVIDERS),help='Host adapter: codex (default), claude or both; refresh keeps the installed host')
    parser.add_argument('--brand',help='Project visual intent, 1-2000 characters')
    parser.add_argument('--design-procedure',choices=['guided','lightweight'])
    parser.add_argument('--option',action='append',default=[],metavar='KEY=VALUE',help='Explicit supported alternative; repeat for different options')
    parser.add_argument('--with',dest='extras',action='append',default=[],metavar='CAPABILITY',help='Add a registered context-* resource procedure to this project selection')
    args=parser.parse_args()
    if args.command in ('catalog','profiles','select','suggestions','trial','evolve','pause','resume','decide','assess'):
        from context_library import dispatch
        result=dispatch(args)
        print(encoded(result).decode(),end='')
        if args.command=='trial' and result['status'] not in ('planned','passed'):
            sys.exit(2)
        return
    if args.profile is not None and args.command in ('plan','apply','refresh'):
        if args.loadouts or args.lock or args.extras or args.option or args.brand or args.design_procedure:
            raise Invalid('profile selections cannot be mixed with delivery overrides')
        from context_library import delivery
        if not args.project:
            raise Invalid('profile delivery needs --project')
        result=delivery(args.profile.stem,args.project,args.provider or 'both',args.command,args.state)
        print(encoded(result).decode(),end='')
        return
    if args.extras and args.command not in ('plan','apply','refresh'):
        raise Invalid('--with applies only to plan, apply and refresh')
    if (args.command=='packet') != (args.profile is not None):
        raise Invalid('--profile is required only for packet')
    overrides={}
    for value in args.option:
        key,separator,item=value.partition('=')
        if not separator or key in overrides:
            raise Invalid('options must be unique KEY=VALUE declarations')
        overrides[key]=item
    for key,value in [('brand',args.brand),('design_procedure',args.design_procedure)]:
        if value is not None:
            if key in overrides and overrides[key]!=value:
                raise Invalid('conflicting compatibility flag and option: '+key)
            overrides[key]=value
    if args.command in ('list','explain','decisions','owners'):
        loads=catalogue()
        if args.command=='owners':
            if args.loadouts or overrides or args.lock:
                raise Invalid('owners takes no selections')
            result=ownership()[0]
        elif args.command=='list':
            result={id:{'description':d['description'],'characteristics':d['characteristics']} for id,d in sorted(loads.items())}
        elif args.command=='decisions':
            if overrides or args.lock:
                raise Invalid('decisions accepts only optional loadout selections')
            result=selected_decisions(selection(args.loadouts)['decisions']) if args.loadouts else current_decisions()
        else:
            result=explain(args.loadouts,overrides)
    else:
        if not args.project or not Path(args.project).is_absolute() or not Path(args.project).is_dir() or Path(args.project).is_symlink():
            raise Invalid('an existing absolute project directory is required')
        project=Path(args.project).resolve()
        if args.lock and (args.command!='apply' or args.loadouts or overrides or args.provider):
            raise Invalid('--lock is only for apply without new selections/options/provider')
        if args.command=='packet':
            if args.loadouts or overrides or args.lock or args.provider:
                raise Invalid('packet selections belong in --profile')
            result=task_packet(read_yaml(args.profile),project)
        elif args.command=='tools':
            if args.loadouts or overrides or args.lock:
                raise Invalid('tools accepts only --project; use plan for selected requirements')
            registry=read_yaml(ROOT/'capabilities.yaml')['capabilities']
            result={'project':str(project),'execution':'not_run',
                    'tools':{key:discover_command(registry[key],project) for key in ('python-runtime','git','node','package-manager','browser','context7')},
                    'native_managed':native_inventory(project,{}),
                    'native_host_tools':'Host-reported tools must be inspected separately; PATH is not native host discovery.'}
        elif args.command=='recover':
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
                if not state:
                    raise Invalid('no installation to refresh')
                ids=state['resolution']['loadouts']
            options={}
            if args.command=='refresh' and state:
                applicable=selection(ids)['options']
                options={key:value for key,value in state['resolution']['options'].items() if key in applicable}
            options.update(overrides)
            provider=args.provider or (state['resolution'].get('provider','codex') if state else 'codex')
            extras=args.extras or (state['resolution'].get('extra_capabilities',[]) if state and args.command=='refresh' else [])
            if args.lock and args.extras:raise Invalid('--lock already pins its capabilities')
            if args.lock:
                lock=json.loads(args.lock.read_text());files=pinned_files(lock)
            else:
                lock,files=resolve(ids,project,provider,options,extras)
            if args.command=='apply':
                result=apply(project,lock,files)
            else:
                result=plan(project,lock,files)
    print(encoded(result).decode(),end='')

if __name__=='__main__':
    try:
        main()
    except Exception as e:
        print('context-ai: '+str(e),file=sys.stderr)
        sys.exit(1)
