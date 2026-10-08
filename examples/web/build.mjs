import {mkdir, copyFile, stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const dir = fileURLToPath(new URL('.', import.meta.url));
const out = fileURLToPath(new URL('../../.examples-output/web-dist/', import.meta.url));
await mkdir(out, {recursive:true});
let bytes = 0;
for (const name of ['index.html', 'style.css', 'catalog.js', 'app.js']) {
  await copyFile(`${dir}${name}`, `${out}${name}`);
  bytes += (await stat(`${out}${name}`)).size;
}
if (bytes > 90000) throw new Error(`Static catalog exceeds its 90 KB budget: ${bytes}`);
console.log(JSON.stringify({output:out,bytes,budget:90000}));
