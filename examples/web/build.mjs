import {mkdir, copyFile, stat, readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {dirname} from 'node:path';
import {createHash} from 'node:crypto';
const dir = fileURLToPath(new URL('.', import.meta.url));
const out = fileURLToPath(new URL('../../.examples-output/web-dist/', import.meta.url));
const source = JSON.parse(await readFile(new URL('../../docs/portal-appearance-source.json', import.meta.url)));
for (const [name, expected] of Object.entries({...source.vendored_files, ...source.adapted_files})) {
  const actual = createHash('sha256').update(await readFile(new URL(`../../${name}`, import.meta.url))).digest('hex');
  if (actual !== expected) throw new Error(`Appearance source checksum differs: ${name}`);
}
await mkdir(out, {recursive:true});
let bytes = 0;
const assets = [];
for (const name of ['index.html', 'style.css', 'catalog.js', 'app.js', 'appearance.js', 'theme/index.js', 'theme/LICENSE']) {
  await mkdir(dirname(`${out}${name}`), {recursive:true});
  await copyFile(`${dir}${name}`, `${out}${name}`);
  const size = (await stat(`${out}${name}`)).size;
  bytes += size;
  assets.push({name,bytes:size,sha256:createHash('sha256').update(await readFile(`${out}${name}`)).digest('hex')});
}
if (bytes > 120000) throw new Error(`Static catalog exceeds its 120 KB budget: ${bytes}`);
await writeFile(`${out}build-evidence.json`, JSON.stringify({bytes,budget:120000,assets},null,2)+'\n');
console.log(JSON.stringify({output:out,bytes,budget:120000}));
