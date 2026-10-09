const catalog = window.CONTEXT_CATALOG;
const library = catalog.library;
const options = new Map(library.options.map(item => [item.id, item]));
const profiles = library.profiles;
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (className) node.className = className;
  return node;
};
const joined = value => Array.isArray(value) ? value.join('; ') : value ?? 'Not recorded';
function factsList(entries) {
  const list = el('dl', undefined, 'facts');
  for (const [label, value] of entries) list.append(el('dt', label), el('dd', joined(value)));
  return list;
}
function disclosure(label, children) {
  const details = el('details'); details.append(el('summary', label), ...children); return details;
}
function sourceLink(label, source) {
  const link = el('a', label);
  try { const url = new URL(source); if (url.protocol === 'https:') link.href = url.href; }
  catch {}
  return link;
}
function badges(values) {
  const row = el('div', undefined, 'badges'); values.filter(Boolean).forEach(value => row.append(el('span', value))); return row;
}
const selectedBy = id => profiles.filter(profile => profile.selections.some(choice => choice.option === id));
function evidenceLabel(item) {
  const trials = (catalog.trials || []).filter(trial => trial.option === item.id);
  return trials.length ? `Scoped trials: ${[...new Set(trials.map(trial=>trial.status))].join(', ')}; benefit unmeasured` : 'Source inspected · benefit unmeasured';
}
function hosts(item) {
  return item.hosts?.length ? item.hosts.map(host => host === 'claude' ? 'Claude Code' : host === 'codex' ? 'Codex' : host).join(', ') : 'Host compatibility needs checking';
}
function assessmentDetails(item) {
  return item.assessments.map(assessment => {
    const block = el('div', undefined, 'assessment');
    block.append(el('p', assessment.scope), factsList([
      ['Strengths', assessment.strengths], ['Weaknesses', assessment.weaknesses],
      ['Evidence', assessment.evidence], ['Checked revision', assessment.checked_ref],
      ['Fit grade', assessment.grade === null ? 'Not rated' : `${assessment.grade} / 4 in this scope`]
    ])); return block;
  });
}
function renderEquipment() {
  const query = document.querySelector('#equipment-search').value.trim().toLowerCase();
  const domain = document.querySelector('#domain-filter').value;
  const selection = document.querySelector('#selection-filter').value;
  const chosen = library.options.filter(item => {
    const selected = selectedBy(item.id).length > 0;
    return (domain === 'all' || item.domains.includes(domain)) &&
      (selection === 'all' || (selection === 'selected' ? selected : !selected)) &&
      [item.id, item.name, item.purpose, item.concern, ...item.domains].join(' ').toLowerCase().includes(query);
  });
  document.querySelector('#equipment-results').replaceChildren(...chosen.map(item => {
    const card = el('article', undefined, 'equipment-card'); card.id = `equipment-${item.id}`;
    card.append(badges([item.delivery.kind === 'native' ? 'Native sufficient' : item.delivery.kind, ...item.domains]), el('h3', item.name), el('p', item.purpose));
    card.append(factsList([['Prerequisites', item.requirements], ['Hosts', hosts(item)], ['Evidence', evidenceLabel(item)]]), sourceLink('Upstream source', item.upstream.url));
    const selected = selectedBy(item.id);
    const alternatives = library.options.filter(other => other.id !== item.id && other.concern === item.concern);
    card.append(disclosure('Fit, alternatives and source', [
      el('p', selected.length ? `Selected for ${selected.map(p => p.id).join(', ')}. Selection does not establish local installation.` : 'Available alternative; not selected in these profiles.'),
      factsList([['Alternatives', alternatives.length ? alternatives.map(other => other.name) : item.delivery.kind === 'native' ? 'Add a focused option only when a specific gap appears.' : 'Project instructions and native tools for ordinary covered work.'], ['Host compatibility', item.host_compatibility], ['Permissions', item.permissions], ['Limits', item.limits]]),
      factsList([['Source/version', item.upstream.revision], ['License', `${item.upstream.license} · ${item.upstream.license_source}`], ['References', item.references]]),
      ...assessmentDetails(item)
    ])); return card;
  }));
  document.querySelector('#equipment-count').textContent = `${chosen.length} available option${chosen.length === 1 ? '' : 's'}`;
  document.querySelector('#equipment-empty').hidden = chosen.length !== 0;
}
function renderProfiles() {
  const profile = profiles.find(item => item.id === document.querySelector('#profile-filter').value);
  if (!profile) return;
  const card = el('article', undefined, 'profile-card'); card.id = `profile-${profile.id}`;
  card.append(badges(['Proposed AI setup', profile.id]), el('h3', profile.id), el('p', profile.purpose));
  const choices = el('ul', undefined, 'choices');
  for (const choice of profile.selections) {
    const item = options.get(choice.option); if (!item) continue;
    const li = el('li'); li.append(el('strong', item.name), el('p', choice.reason));
    li.append(factsList([['Adds', item.delivery.kind === 'native' ? 'No added Context files or tools for ordinary work.' : item.purpose], ['Prerequisites', item.requirements], ['Permissions', item.permissions]]));
    const link = el('a', 'Inspect this equipment'); link.href = `#equipment-${item.id}`;
    link.addEventListener('click', () => { resetEquipment(); activateTab('equipment'); requestAnimationFrame(() => document.getElementById(`equipment-${item.id}`).scrollIntoView({block:'start'})); });
    li.append(link); choices.append(li);
  }
  card.append(choices, disclosure('Environment, policy and evidence', [
    profile.project ? sourceLink('Public project', profile.project) : el('p', 'Exploratory interest; no repository declared.'),
    factsList([['Environment', Object.entries(profile.environment).map(([key, value]) => `${key}: ${joined(value)}`)], ['Snapshot revision', profile.snapshot.revision || 'No repository snapshot'], ['Priorities', profile.priorities], ['Allowed trials', profile.policy.trials], ['Allowed updates', profile.policy.updates], ['Schedule', profile.policy.schedule ? 'Configured' : 'Not configured'], ['Evidence boundary', 'Public source fit assessment; private local status is excluded.']])
  ])); document.querySelector('#profile-results').replaceChildren(card);
  document.querySelector('#request-profile').textContent = `Plan request for ${profile.id}. Local target binding and permission checks belong to the trusted caller.`;
  document.querySelector('#request-status').textContent = '';
}
function renderLoadouts() {
  const query = document.querySelector('#search').value.trim().toLowerCase();
  const concern = document.querySelector('[name=concern]:checked').value;
  const chosen = catalog.loadouts.filter(item => (concern === 'all' || item.kind === concern) && `${item.id} ${item.description}`.toLowerCase().includes(query));
  document.querySelector('#results').replaceChildren(...chosen.map(item => {
    const row = el('article', undefined, 'loadout'); const body = el('div');
    body.append(el('p', item.description), factsList([['Selected guidance', `${item.guidance} files${item.composes.length ? `; with ${item.composes.join(', ')}` : ''}`], ['Required tools', item.tools.length ? item.tools : 'No required tools'], ['Optional tools', item.optional_tools], ['Evidence', item.evidence.record ? `${item.evidence.benefit}: ${item.evidence.summary} (${item.evidence.record})` : item.evidence.benefit]]));
    row.append(el('h3', item.id), body); return row;
  }));
  document.querySelector('#count').textContent = `${chosen.length} loadout${chosen.length === 1 ? '' : 's'}`;
  document.querySelector('#empty').hidden = chosen.length !== 0;
}
function renderTrials() {
  const trials = catalog.trials || [];
  document.querySelector('#trial-results').replaceChildren(...trials.map(trial => {
    const card = el('article', undefined, 'trial-card'); card.id = `trial-${trial.id}`;
    card.append(badges([trial.status, trial.option]), el('h3', trial.title), el('p', trial.outcome, 'trial-outcome'));
    card.append(el('p', trial.purpose));
    card.append(disclosure('Host, measurements and retained evidence', [factsList([
      ['Host', trial.host], ['Model/settings', trial.model], ['Version', trial.version],
      ['Measurements', trial.metrics ? JSON.stringify(trial.metrics) : 'No comparative task measurement recorded'],
      ['Policy', trial.policy ? Object.entries(trial.policy).map(([key,value])=>`${key}: ${value}`) : 'Not recorded'],
      ['Limitations', trial.limits], ['Evidence reference', trial.evidence], ['Source revision', trial.context_revision || 'Historical uncommitted snapshot; exact commit unknown'], ['Source snapshot hash', trial.source_snapshot_sha256 || 'Not recorded'], ['Receipt hash', trial.receipt_sha256]
    ])])); return card;
  }));
  if (!trials.length) document.querySelector('#trial-results').append(el('p', 'No public trial record is available in this snapshot.'));
}
function renderPreview() {
  const preview = catalog.delivery_preview;
  const area = document.querySelector('#preview-results');
  if (!preview) { area.append(el('p', 'No public example. Preview your target locally.')); return; }
  area.append(el('p', preview.purpose));
  const groups = el('div', undefined, 'preview-groups');
  for (const key of ['additions','replacements','conflicts','unchanged']) {
    const group = el('div', undefined, `preview-group ${key}`); const list = el('ul');
    group.append(el('h3', `${key[0].toUpperCase()+key.slice(1)}`));
    const items = key === 'conflicts' ? preview.conflict_plan?.conflicts || preview[key] : preview.addition_plan?.[key] || preview[key];
    if (!items) list.append(el('li', 'Not enumerated by the engine'));
    else if (!items.length) list.append(el('li', 'None in this example'));
    for (const item of items || []) list.append(el('li', typeof item === 'string' ? item : `${item.path || item.resource || item.id || ''}${item.reason ? ` · ${item.reason}` : ''}`));
    group.append(list); groups.append(group);
  }
  area.append(el('p', 'Additions and replacements show the initial plan; conflicts show the later deliberate edit. Both are proposed engine outputs, not a live target status.', 'note'), groups, disclosure('Example provenance and limits', [factsList([['Source revision', preview.source_commit], ['Evidence reference', preview.raw_refs], ['Status', preview.evidence_class], ['Preservation outcome', preview.outcome ? `Unmanaged bytes preserved: ${preview.outcome.unmanaged_bytes_preserved}; edited helper preserved: ${preview.outcome.edited_helper_preserved}; undo completed: ${preview.outcome.undo?.undone}` : 'Not recorded'], ['Permissions', preview.permissions], ['Limits', preview.limits]])]));
}
function renderOwnership() {
  const area = document.querySelector('#migration-note'); const migration = catalog.opportunity_migration;
  if (migration?.status === 'moved' || migration?.status === 'imported' || migration?.status === 'acknowledged' || !(catalog.suggestions || []).length) {
    area.append(el('p', 'General project opportunities belong to Signals. Context keeps the equipment choices and setup evidence shown here. Ordinary setup works without Signals.'), factsList([['Ownership', catalog.ownership?.project_opportunities || 'Signals project opportunities'], ['Transfer evidence', migration?.receipt_reference || migration?.receipt || 'See the local ownership handoff.']]));
  } else {
    area.append(el('p', 'The retained opportunity records remain available until Signals acknowledges their transfer. They are separate from AI setup selections.'));
    for (const item of catalog.suggestions) document.querySelector('#opportunity-results').append(disclosure(`${item.profile}: ${item.area}`, [el('p', item.opportunity), factsList([['Next action', item.next_action], ['Evidence', item.evidence], ['Limits', item.limitations]])]));
  }
}
function activateTab(id, focus = false) {
  for (const tab of document.querySelectorAll('[role=tab]')) {
    const selected = tab.getAttribute('aria-controls') === id; tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1;
    document.getElementById(tab.getAttribute('aria-controls')).hidden = !selected;
    if (selected && focus) tab.focus();
  }
}
const tabs = [...document.querySelectorAll('[role=tab]')];
for (const tab of tabs) {
  tab.addEventListener('click', () => activateTab(tab.getAttribute('aria-controls')));
  tab.addEventListener('keydown', event => {
    const index = tabs.indexOf(tab); let next;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = tabs.length - 1;
    if (next !== undefined) { event.preventDefault(); activateTab(tabs[next].getAttribute('aria-controls'), true); }
  });
}
function resetEquipment() {
  document.querySelector('#equipment-search').value = ''; document.querySelector('#domain-filter').value = 'all'; document.querySelector('#selection-filter').value = 'all'; renderEquipment();
}
for (const domain of [...new Set(library.options.flatMap(item => item.domains))].sort()) {
  const option = el('option', domain); option.value = domain; document.querySelector('#domain-filter').append(option);
}
for (const profile of profiles) { const option = el('option', profile.id); option.value = profile.id; document.querySelector('#profile-filter').append(option); }
for (const item of library.options.filter(item => ['loadout','capability'].includes(item.delivery.kind))) {
  const option = el('option', item.name); option.value = item.id; document.querySelector('#request-option').append(option);
}
function updateCommand() {
  const item = options.get(document.querySelector('#request-option').value); if (!item) return;
  const selection = `${item.delivery.kind === 'loadout' ? '' : '--with '}${item.delivery.id || item.id}`;
  const host = document.querySelector('#request-host').value;
  document.querySelector('#local-command').textContent = `.venv/bin/python scripts/context_ai.py plan ${selection} --project /absolute/project --provider ${host}\n.venv/bin/python scripts/context_ai.py apply ${selection} --project /absolute/project --provider ${host}\n.venv/bin/python scripts/context_ai.py verify --project /absolute/project\n.venv/bin/python scripts/context_ai.py refresh --project /absolute/project\n.venv/bin/python scripts/context_ai.py undo --project /absolute/project`;
  document.querySelector('#request-status').textContent = '';
}
document.querySelector('#request-form').addEventListener('submit', event => {
  event.preventDefault(); const profile = profiles.find(item => item.id === document.querySelector('#profile-filter').value); if (!profile) return;
  const request = {schema_version:1,request_id:crypto.randomUUID(),method:'plan',profile_id:profile.id,project_ref:{id:profile.id,source_ref:profile.project || `interest:${profile.id}`},constraints:[],findings:[]};
  const url = URL.createObjectURL(new Blob([JSON.stringify(request,null,2)+'\n'],{type:'application/json'}));
  const download = el('a'); download.href = url; download.download = 'context-profile-plan-request.json'; download.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  document.querySelector('#request-status').textContent = 'Profile plan request exported. A trusted local caller must resolve the target and preview; nothing was installed.';
});
for (const id of ['request-option','request-host']) document.querySelector(`#${id}`).addEventListener('change', updateCommand);
document.querySelector('#equipment-search').addEventListener('input', renderEquipment);
for (const id of ['domain-filter','selection-filter']) document.querySelector(`#${id}`).addEventListener('change', renderEquipment);
document.querySelector('#equipment-reset').addEventListener('click', () => { resetEquipment(); document.querySelector('#equipment-search').focus(); });
document.querySelector('#profile-filter').addEventListener('change', renderProfiles);
document.querySelector('#search').addEventListener('input', renderLoadouts);
document.querySelectorAll('[name=concern]').forEach(input => input.addEventListener('change', renderLoadouts));
document.querySelector('#reset').addEventListener('click', () => { document.querySelector('#search').value = ''; document.querySelector('[name=concern][value=all]').checked = true; renderLoadouts(); document.querySelector('#search').focus(); });
document.querySelector('#mode').addEventListener('click', event => { const active = event.currentTarget.getAttribute('aria-pressed') !== 'true'; event.currentTarget.setAttribute('aria-pressed',String(active)); document.body.dataset.mode = active ? 'expressive' : 'quiet'; });
renderEquipment(); renderProfiles(); renderLoadouts(); renderTrials(); renderPreview(); renderOwnership(); updateCommand();
