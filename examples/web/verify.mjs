import {chromium, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {createServer} from 'node:http';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const dist = fileURLToPath(new URL('../../.examples-output/web-dist/', import.meta.url));
const out = fileURLToPath(new URL('../../.examples-output/web-evidence/', import.meta.url));
await mkdir(out, {recursive:true});
const server=createServer(async (req,res)=>{
  const name=req.url==='/'?'index.html':req.url.slice(1);
  if (!['index.html','style.css','app.js'].includes(name)) {res.writeHead(404);res.end();return;}
  try {res.setHeader('Content-Type',name.endsWith('.css')?'text/css':name.endsWith('.js')?'text/javascript':'text/html');res.end(await readFile(dist+name));}
  catch {res.writeHead(500);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({headless:true});
const errors=[],results=[];
try {
  for (const width of [320,390,768,1440]) {
    const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
    const page=await context.newPage();
    page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
    page.on('requestfailed',r=>errors.push(r.url()));
    await page.goto(base);await page.locator('.loadout').last().waitFor();
    assert.equal(await page.locator('.loadout').count(),8);
    const overflow=await page.evaluate(()=>({present:document.documentElement.scrollWidth>innerWidth,offenders:[...document.querySelectorAll('body *')].filter(el=>el.getBoundingClientRect().right>innerWidth+.5).map(el=>({tag:el.tagName,id:el.id,class:el.className,width:el.getBoundingClientRect().width}))}));
    assert(!overflow.present,'horizontal overflow at '+width+': '+JSON.stringify(overflow.offenders));
    await page.screenshot({path:out+`quiet-${width}.png`,fullPage:true});
    const quiet=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
    assert.deepEqual(quiet.violations,[],JSON.stringify(quiet.violations));
    await page.getByRole('button',{name:'Expressive palette'}).click();
    await page.screenshot({path:out+`expressive-${width}.png`,fullPage:true});
    const expressive=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
    assert.deepEqual(expressive.violations,[],JSON.stringify(expressive.violations));
    await page.getByLabel('Find a loadout').fill('no-such-loadout');
    assert(await page.getByRole('heading',{name:'No matching loadouts'}).isVisible());
    await page.getByRole('button',{name:'Clear filters'}).click();
    assert.equal(await page.locator('.loadout').count(),8);
    await page.getByLabel('Web',{exact:true}).check();
    assert.equal(await page.locator('.loadout').count(),2);
    await page.locator('summary').click();
    assert(await page.getByText('Inspect the built page at desktop and 320px.').isVisible());
    const note=page.getByLabel('Preview a review note');
    const noteStatus=page.locator('#note-status');
    const save=page.getByRole('button',{name:'Save preview note'});
    const noteRequests=[];
    const recordNoteRequest=request=>noteRequests.push({url:request.url(),method:request.method()});
    page.on('request',recordNoteRequest);
    for (const palette of ['expressive','quiet']) {
      if (palette==='quiet') await page.getByRole('button',{name:'Expressive palette'}).click();
      await note.fill('');
      await save.click();
      await expect(noteStatus).toHaveText('Write at least four characters, then save your preview note.');
      await expect(note).toHaveAttribute('aria-invalid','true');
      await expect(note).toBeFocused();
      // Editing clears the old result even while the new draft is still too short.
      await note.press('a');
      await expect(noteStatus).toBeEmpty();
      await expect(note).not.toHaveAttribute('aria-invalid');
      await expect(note).toHaveValue('a');
      await save.click();
      await expect(noteStatus).toHaveText('Write at least four characters, then save your preview note.');
      await expect(note).toHaveAttribute('aria-invalid','true');
      await note.fill('Check reading order');
      await expect(noteStatus).toBeEmpty();
      await expect(note).not.toHaveAttribute('aria-invalid');
      await save.click();
      await expect(noteStatus).toHaveText('Preview note saved on this page. No server request was sent.');
      await expect(note).toHaveAttribute('aria-invalid','false');
      await expect(note).toHaveValue('Check reading order');
      if ([320,1440].includes(width)) await page.screenshot({path:out+`note-saved-${palette}-${width}.png`,fullPage:true});
      await note.press('ControlOrMeta+a');
      await note.press('ArrowRight');
      await note.press('!');
      await expect(noteStatus).toBeEmpty();
      await expect(note).not.toHaveAttribute('aria-invalid');
      await expect(note).toHaveValue('Check reading order!');
      await page.getByLabel('Find a loadout').fill('no-such-loadout');
      await page.getByRole('button',{name:'Clear filters'}).click();
      await expect(page.locator('.loadout')).toHaveCount(8);
      await expect(note).toHaveValue('Check reading order!');
      if ([320,1440].includes(width)) await page.screenshot({path:out+`note-edited-${palette}-${width}.png`,fullPage:true});
      await save.click();
      await expect(noteStatus).toHaveText('Preview note saved on this page. No server request was sent.');
      await note.fill(' abc ');
      await expect(noteStatus).toBeEmpty();
      await expect(note).not.toHaveAttribute('aria-invalid');
      await save.click();
      await expect(noteStatus).toHaveText('Write at least four characters, then save your preview note.');
      await expect(note).toHaveAttribute('aria-invalid','true');
      await expect(note).toHaveValue(' abc ');
    }
    assert.deepEqual(noteRequests,[],'note edits and submissions must not send requests');
    page.off('request',recordNoteRequest);
    await page.goto(base);await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Skip to loadouts');
    await page.keyboard.press('Enter');
    await expect(page.locator('#main')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link',{name:'Explore the loadouts'})).toBeFocused();
    assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');
    results.push({width,axe_quiet:0,axe_expressive:0,overflow:false,states:'filter/empty/reset/details/error/edit/retry/success in both palettes',note_requests:noteRequests.length,keyboard:'skip destination focus, next Tab target and rejected-note focus',reduced_motion:true});
    await context.close();
  }
  assert.deepEqual(errors,[]);
  await writeFile(out+'results.json',JSON.stringify({evidence_class:'fixture + browser builder proxy',results,errors,limits:['No assistive-technology user test. No deployed field Web Vitals. Axe does not certify WCAG conformance.']},null,2)+'\n');
  console.log(`Web verification passed: ${results.length} widths, both palettes, interactions and axe; screenshots ${out}`);
} finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
