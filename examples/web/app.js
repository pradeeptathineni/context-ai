const loadouts = [
  ['standard', 'engineering', 'Inspect, implement, test, review, and deliver with the project’s existing tools.'],
  ['context-authoring', 'engineering', 'Keep instructions concise, coherent, attributable, and sufficient to continue.'],
  ['research-evidence', 'engineering', 'Acquire primary evidence, compare options, and preserve uncertainty.'],
  ['web-experience', 'web', 'Shape the product, build the experience, and critique it in a real browser.'],
  ['react-web', 'web', 'Add React guidance that matches the actual framework and runtime.'],
  ['service-api', 'engineering', 'Test API contracts, trust boundaries, persistence, and failure recovery.'],
  ['aws-infrastructure', 'engineering', 'Inspect and validate existing infrastructure with explicit deployment boundaries.'],
  ['release-review', 'engineering', 'Review compatibility, validation, immutable tags, and the release destination.']
];
const search = document.querySelector('#search');
function render() {
  const concern = document.querySelector('[name=concern]:checked').value;
  const query = search.value.toLowerCase().trim();
  const chosen = loadouts.filter(([name, kind, desc]) => (concern === 'all' || concern === kind) && (name + desc).toLowerCase().includes(query));
  document.querySelector('#results').replaceChildren(...chosen.map(([name, , desc]) => {
    const row = document.createElement('article'); row.className = 'loadout';
    const heading = document.createElement('h3'); heading.textContent = name;
    const detail = document.createElement('p'); detail.textContent = desc;
    row.append(heading, detail); return row;
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
render();
