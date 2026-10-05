import {mkdir, copyFile, stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const dir = fileURLToPath(new URL('.', import.meta.url));
const out = fileURLToPath(new URL('../../.examples-output/web-dist/', import.meta.url));
await mkdir(out, {recursive:true});
let bytes = 0;
for (const name of ['index.html', 'style.css', 'app.js']) {
  await copyFile(`${dir}${name}`, `${out}${name}`);
  bytes += (await stat(`${out}${name}`)).size;
}
if (bytes > 24000) throw new Error(`Static fixture exceeds its 24 KB budget: ${bytes}`);
console.log(JSON.stringify({output:out,bytes,budget:24000}));
