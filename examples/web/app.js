const catalog = window.CONTEXT_CATALOG;
const loadouts = catalog.loadouts;
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
function facts(item) {
  const owners = Object.entries(item.owners).map(([kind, n]) => `${n} ${kind}`).join(', ');
  const upstream = item.upstream.length ? ` · pinned upstream: ${item.upstream.join(', ')}` : '';
  const tools = item.tools.length ? `needs ${item.tools.join(', ')}` : 'no required tools';
  const optional = item.optional_tools.length ? `; optional ${item.optional_tools.join(', ')}` : '';
  return [
    ['Selected guidance', `${plural(item.guidance, 'file')}${item.composes.length ? ` (with ${item.composes.join(', ')})` : ''} · owners: ${owners}${upstream}`],
    ['Operational tools', `${tools}${optional}; checked by verify, not by this page`],
    ['Measured benefit', item.measured ? `recorded in ${item.measured}` : 'unmeasured']
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
document.querySelector('#reset').addEventListener('click', () => { search.value = ''; document.querySelector('[value=all]').checked = true; render(); search.focus(); });
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
