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
  if (!['index.html','style.css','catalog.js','app.js'].includes(name)) {res.writeHead(404);res.end();return;}
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
    assert.equal(await page.locator('.loadout').count(),9);
    const publicCounts=await page.evaluate(()=>({options:window.CONTEXT_CATALOG.library.options.length,
      profiles:window.CONTEXT_CATALOG.library.profiles.length,suggestions:window.CONTEXT_CATALOG.suggestions.length}));
    assert(publicCounts.options>2 && publicCounts.profiles>=2 && publicCounts.suggestions>=2);
    await expect(page.locator('.equipment-card')).toHaveCount(publicCounts.options);
    await expect(page.locator('.profile-card')).toHaveCount(publicCounts.profiles);
    await expect(page.locator('.opportunity-card')).toHaveCount(publicCounts.suggestions);
    await expect(page.locator('.opportunity-card',{hasText:'Close the independent-backup-destination gap'})).toBeVisible();
    await expect(page.locator('.opportunity-card',{hasText:'Turn the unstarted CKAD-002 link'})).toBeVisible();
    await page.getByLabel('Project or interest').selectOption('labs');
    await expect(page.locator('.profile-card')).toHaveCount(1);
    await expect(page.locator('.profile-card h3')).toHaveText('labs');
    await expect(page.locator('.opportunity-card')).toHaveCount(2);
    await page.getByLabel('Project or interest').selectOption('all');
    await page.getByLabel('Find equipment').fill('no-such-equipment');
    await expect(page.getByRole('heading',{name:'No matching equipment'})).toBeVisible();
    await page.getByRole('button',{name:'Reset equipment filters'}).click();
    await expect(page.getByLabel('Find equipment')).toBeFocused();
    await page.getByLabel('Selection',{exact:true}).selectOption('alternative');
    await expect(page.locator('#equipment-matt-pocock-tdd')).toBeVisible();
    await expect(page.locator('#equipment-context-output')).toHaveCount(0);
    await page.getByLabel('Selection',{exact:true}).selectOption('all');
    await page.getByLabel('Domain',{exact:true}).selectOption('learning');
    await expect(page.locator('.equipment-card')).toHaveCount(1);
    await page.getByLabel('Domain',{exact:true}).selectOption('all');
    // Source strings must remain text even when they resemble executable markup.
    const originalName=await page.evaluate(()=>window.CONTEXT_CATALOG.library.options[0].name);
    await page.evaluate(()=>{window.CONTEXT_CATALOG.library.options[0].name='<img src=x onerror="window.untrustedRan=true">';renderEquipment();});
    await expect(page.locator('.equipment-card').first().locator('h3')).toHaveText('<img src=x onerror="window.untrustedRan=true">');
    await expect(page.locator('.equipment-card img')).toHaveCount(0);
    assert.equal(await page.evaluate(()=>window.untrustedRan),undefined);
    await page.evaluate(name=>{window.CONTEXT_CATALOG.library.options[0].name=name;renderEquipment();},originalName);
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
    assert.equal(await page.locator('.loadout').count(),9);
    await expect(page.locator('.loadout').first().locator('h3')).toHaveText('essentials');
    const canonicalLoadouts=await page.evaluate(()=>window.CONTEXT_CATALOG.loadouts);
    for (const item of canonicalLoadouts) {
      const evidence=item.evidence;
      const expected=evidence.record?`${evidence.benefit}: ${evidence.summary} (${evidence.record})`:evidence.benefit;
      await expect(page.locator('.loadout').filter({has:page.locator('h3',{hasText:new RegExp(`^${item.id}$`)})}).getByText(expected,{exact:true})).toBeVisible();
    }
    await expect(page.getByText(/^recorded in /)).toHaveCount(0);
    for (const state of ['Reference knowledge','Selected guidance','Installed resource','Operational tool','Measured benefit'])
      await expect(page.locator('#states dt',{hasText:state})).toBeVisible();
    await expect(page.locator('#concept-count')).toHaveText('140');
    await page.getByLabel('Web',{exact:true}).check();
    assert.equal(await page.locator('.loadout').count(),2);
    await page.getByText('Preview, use, refresh or remove a focused selection',{exact:true}).click();
    await expect(page.locator('#task pre').first()).toBeVisible();
    assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)), 'focused commands overflow at '+width);
    if ([320,1440].includes(width)) await page.screenshot({path:out+`task-expanded-${width}.png`,fullPage:true});
    await page.getByText('Read the web acceptance checklist',{exact:true}).click();
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
      await expect(page.locator('.loadout')).toHaveCount(9);
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
    assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Skip to library');
    await page.keyboard.press('Enter');
    await expect(page.locator('#main')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link',{name:'Explore equipment'})).toBeFocused();
    assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');
    await page.locator('.equipment-card').first().getByText('Fit, limits and source evidence',{exact:true}).click();
    await page.locator('.profile-card').first().getByText('Environment, policy and snapshot',{exact:true}).click();
    await page.locator('.opportunity-card').first().getByText('Why this fits and what remains unknown',{exact:true}).click();
    assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)), 'evidence details overflow at '+width);
    if ([320,1440].includes(width)) await page.screenshot({path:out+`library-expanded-${width}.png`,fullPage:true});
    results.push({width,axe_quiet:0,axe_expressive:0,overflow:false,states:'catalog/profile/opportunity filters, alternatives, evidence disclosures, text-only source rendering; legacy filter/empty/reset/details/error/edit/retry/success in both palettes',note_requests:noteRequests.length,keyboard:'skip destination focus, next Tab target and rejected-note focus',reduced_motion:true});
    await context.close();
  }
  assert.deepEqual(errors,[]);
  await writeFile(out+'results.json',JSON.stringify({evidence_class:'fixture + browser builder proxy',results,errors,limits:['No assistive-technology user test. No deployed field Web Vitals. Axe does not certify WCAG conformance.']},null,2)+'\n');
  console.log(`Web verification passed: ${results.length} widths, both palettes, interactions and axe; screenshots ${out}`);
} finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
