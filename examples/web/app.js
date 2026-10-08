const catalog = window.CONTEXT_CATALOG;
const loadouts = catalog.loadouts;
const plural = (n, word) => `${n} ${n === 1 ? word : word.endsWith('y') ? word.slice(0, -1) + 'ies' : word + 's'}`;
function facts(item) {
  const owners = Object.entries(item.owners).map(([kind, n]) => `${n} ${kind}`).join(', ');
  const upstream = item.upstream.length ? ` · pinned upstream: ${item.upstream.join(', ')}` : '';
  const tools = item.tools.length ? `needs ${item.tools.join(', ')}` : 'no required tools';
  const optional = item.optional_tools.length ? `; optional ${item.optional_tools.join(', ')}` : '';
  return [
    ['Selected guidance', `${plural(item.guidance, 'file')}${item.composes.length ? ` (with ${item.composes.join(', ')})` : ''} · owners: ${owners}${upstream}`],
    ['Operational tools', `${tools}${optional}; checked by verify, not by this page`],
    ['Measured benefit', item.evidence.record ? `${item.evidence.benefit}: ${item.evidence.summary} (${item.evidence.record})` : item.evidence.benefit]
  ];
}
const search = document.querySelector('#search');
function render() {
  const concern = document.querySelector('[name=concern]:checked').value;
  const query = search.value.toLowerCase().trim();
  const chosen = loadouts.filter(item => (concern === 'all' || concern === item.kind) && (item.id + item.description).toLowerCase().includes(query));
  document.querySelector('#results').replaceChildren(...chosen.map(item => {
    const row = document.createElement('article'); row.className = 'loadout';
    const heading = document.createElement('h3'); heading.textContent = item.id;
    const body = document.createElement('div');
    const detail = document.createElement('p'); detail.textContent = item.description;
    const list = document.createElement('dl'); list.className = 'facts';
    for (const [term, value] of facts(item)) {
      const dt = document.createElement('dt'); dt.textContent = term;
      const dd = document.createElement('dd'); dd.textContent = value;
      list.append(dt, dd);
    }
    body.append(detail, list);
    row.append(heading, body); return row;
  }));
  document.querySelector('#count').textContent = `${chosen.length} loadout${chosen.length === 1 ? '' : 's'}`;
  document.querySelector('#empty').hidden = chosen.length !== 0;
}
search.addEventListener('input', render);
document.querySelectorAll('[name=concern]').forEach(input => input.addEventListener('change', render));
document.querySelector('#reset').addEventListener('click', () => { search.value = ''; document.querySelector('[name=concern][value=all]').checked = true; render(); search.focus(); });
document.querySelector('#mode').addEventListener('click', event => {
  const expressive = event.currentTarget.getAttribute('aria-pressed') !== 'true';
  event.currentTarget.setAttribute('aria-pressed', String(expressive));
  document.body.dataset.mode = expressive ? 'expressive' : 'quiet';
});
const note = document.querySelector('#note');
const noteStatus = document.querySelector('#note-status');
note.addEventListener('input', () => {
  noteStatus.textContent = '';
  note.removeAttribute('aria-invalid');
});
document.querySelector('#notes').addEventListener('submit', event => {
  event.preventDefault();
  const valid = note.value.trim().length >= 4;
  note.setAttribute('aria-invalid', String(!valid));
  noteStatus.textContent = valid ? 'Preview note saved on this page. No server request was sent.' : 'Write at least four characters, then save your preview note.';
  if (!valid) note.focus();
});
document.querySelector('#concept-count').textContent = String(catalog.concepts);
render();

const library = catalog.library;
const options = new Map(library.options.map(item => [item.id, item]));
const profiles = library.profiles;
const selectedBy = id => profiles.filter(profile => profile.selections.some(choice => choice.option === id));
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (className) node.className = className;
  return node;
};
function factsList(entries) {
  const list = el('dl', undefined, 'facts');
  for (const [label, value] of entries) list.append(el('dt', label), el('dd', Array.isArray(value) ? value.join('; ') : value));
  return list;
}
function disclosure(label, children) {
  const details = el('details');
  details.append(el('summary', label), ...children);
  return details;
}
function sourceLink(label, source) {
  const link = el('a', label);
  try {
    const url = new URL(source);
    if (url.protocol === 'https:') link.href = url.href;
  } catch { /* Invalid source URLs remain readable text. */ }
  return link;
}
function badges(values) {
  const row = el('div', undefined, 'badges');
  for (const value of values) row.append(el('span', value));
  return row;
}
function assessmentDetails(item) {
  return item.assessments.map(assessment => {
    const block = el('div', undefined, 'assessment');
    block.append(el('p', assessment.scope), factsList([
      ['Fit grade', assessment.grade === null ? 'Not rated' : `${assessment.grade} / 4, limited to this scope`],
      ['Strengths', assessment.strengths], ['Weaknesses', assessment.weaknesses],
      ['Evidence', assessment.evidence], ['Checked revision', assessment.checked_ref]
    ]));
    return block;
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
    const card = el('article', undefined, 'equipment-card');
    card.id = `equipment-${item.id}`;
    card.append(badges([item.state, item.status, ...item.domains]), el('h3', item.name), el('p', item.purpose));
    const selected = selectedBy(item.id);
    card.append(el('p', selected.length ? `Selected for ${selected.map(p => p.id).join(', ')}` : 'Available alternative; not selected in these profiles', 'selection-note'));
    card.append(el('p', `Route: ${item.delivery.kind}${item.delivery.id ? ` · ${item.delivery.id}` : ''}`, 'note'));
    const alternatives = library.options.filter(other => other.id !== item.id && other.concern === item.concern);
    if (alternatives.length) card.append(el('p', `Other routes for this concern: ${alternatives.map(other => other.name).join('; ')}`, 'note'));
    card.append(disclosure('Fit, limits and source evidence', [
      sourceLink('Upstream source', item.upstream.url),
      factsList([['Pin', item.upstream.revision], ['License', item.upstream.license],
        ['License source', item.upstream.license_source], ['Requirements', item.requirements],
        ['Permissions', item.permissions], ['Limits', item.limits], ['References', item.references]]),
      ...assessmentDetails(item)
    ]));
    return card;
  }));
  document.querySelector('#equipment-count').textContent = plural(chosen.length, 'option');
  document.querySelector('#equipment-empty').hidden = chosen.length !== 0;
}
function renderProfiles() {
  const project = document.querySelector('#project-filter').value;
  const chosen = profiles.filter(profile => project === 'all' || project === profile.id);
  document.querySelector('#profile-results').replaceChildren(...chosen.map(profile => {
    const card = el('article', undefined, 'profile-card');
    card.id = `profile-${profile.id}`;
    card.append(el('h3', profile.id), el('p', profile.purpose));
    if (profile.project) card.append(sourceLink('Public project', profile.project));
    else card.append(el('p', 'Exploratory interest · no repository declared', 'note'));
    const choices = el('ul', undefined, 'choices');
    for (const choice of profile.selections) {
      const li = el('li');
      li.append(el('strong', options.get(choice.option).name), el('p', choice.reason));
      choices.append(li);
    }
    card.append(choices, disclosure('Environment, policy and snapshot', [factsList([
      ['Environment', Object.entries(profile.environment).filter(([key]) => key !== 'snapshot_scope').map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)],
      ['Snapshot scope', profile.environment.snapshot_scope], ['Revision', profile.snapshot.revision || 'No repository snapshot'],
      ['Priorities', profile.priorities], ['Allowed trials', profile.policy.trials.length ? profile.policy.trials : 'None'],
      ['Allowed updates', profile.policy.updates.length ? profile.policy.updates : 'None'],
      ['Schedule', profile.policy.schedule ? 'Configured' : 'Not configured'],
      ['Inspected files', profile.snapshot.files.map(file => `${file.path} · ${file.sha256}`)]
    ])]));
    return card;
  }));
}
function renderOpportunities() {
  const project = document.querySelector('#project-filter').value;
  const chosen = catalog.suggestions.filter(item => project === 'all' || item.profile === project);
  document.querySelector('#opportunity-results').replaceChildren(...chosen.map(item => {
    const card = el('article', undefined, 'opportunity-card');
    card.append(badges([item.profile, item.status]), el('h3', item.area), el('p', item.opportunity));
    const action = el('div', undefined, 'next-action');
    action.append(el('strong', 'Next action'), el('p', item.next_action));
    card.append(action, el('p', `Suggested route: ${options.get(item.option).name}`, 'note'));
    card.append(disclosure('Why this fits and what remains unknown', [el('p', item.why), factsList([
      ['Evidence', item.evidence.length ? item.evidence : 'Declared exploratory interest'],
      ['Limits', item.limitations], ['Checked', `${item.date} · ${item.checked_ref}`]
    ])]));
    return card;
  }));
  document.querySelector('#opportunity-count').textContent = plural(chosen.length, 'opportunity');
}
for (const profile of profiles) {
  const option = el('option', profile.id); option.value = profile.id;
  document.querySelector('#project-filter').append(option);
}
for (const domain of [...new Set(library.options.flatMap(item => item.domains))].sort()) {
  const option = el('option', domain); option.value = domain;
  document.querySelector('#domain-filter').append(option);
}
document.querySelector('#equipment-search').addEventListener('input', renderEquipment);
for (const id of ['domain-filter', 'selection-filter']) document.querySelector(`#${id}`).addEventListener('change', renderEquipment);
document.querySelector('#equipment-reset').addEventListener('click', () => {
  document.querySelector('#equipment-search').value = '';
  document.querySelector('#domain-filter').value = 'all';
  document.querySelector('#selection-filter').value = 'all';
  renderEquipment(); document.querySelector('#equipment-search').focus();
});
document.querySelector('#project-filter').addEventListener('change', () => { renderProfiles(); renderOpportunities(); });
document.querySelector('#library-stats').replaceChildren(...[
  [library.options.length, 'available options'], [profiles.length, 'project profiles'], [catalog.suggestions.length, 'concrete opportunities']
].map(([count, label]) => { const stat = el('div'); stat.append(el('strong', count), el('span', label)); return stat; }));
renderEquipment(); renderProfiles(); renderOpportunities();
