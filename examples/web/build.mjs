import {mkdir, copyFile, stat, readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const dir = fileURLToPath(new URL('.', import.meta.url));
const out = fileURLToPath(new URL('../../.examples-output/web-dist/', import.meta.url));
await mkdir(out, {recursive:true});
let bytes = 0;
const assets = [];
for (const name of ['index.html', 'style.css', 'catalog.js', 'app.js']) {
  await copyFile(`${dir}${name}`, `${out}${name}`);
  const size = (await stat(`${out}${name}`)).size;
  bytes += size;
  assets.push({name,bytes:size,sha256:createHash('sha256').update(await readFile(`${out}${name}`)).digest('hex')});
}
if (bytes > 90000) throw new Error(`Static catalog exceeds its 90 KB budget: ${bytes}`);
await writeFile(`${out}build-evidence.json`, JSON.stringify({bytes,budget:90000,assets},null,2)+'\n');
console.log(JSON.stringify({output:out,bytes,budget:90000}));
