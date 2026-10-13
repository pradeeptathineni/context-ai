import {chromium, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {createServer} from 'node:http';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import path from 'node:path';
const dist = fileURLToPath(new URL('../../.examples-output/web-dist/', import.meta.url));
const out = process.env.WEB_EVIDENCE_DIR ? path.resolve(process.env.WEB_EVIDENCE_DIR)+'/' : fileURLToPath(new URL('../../.examples-output/web-evidence/', import.meta.url));
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
    const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce',acceptDownloads:true});
    const page=await context.newPage();
    page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
    page.on('requestfailed',r=>errors.push(r.url()));
    await page.goto(base);await page.locator('.equipment-card').last().waitFor();
    const data=await page.evaluate(()=>window.CONTEXT_CATALOG);
    assert(data.library.options.length>2 && data.library.profiles.length>=2);
    assert.equal(data.opportunity_migration.status,'moved','retired-state catalog required');
    assert(!Object.hasOwn(data,'suggestions'),'duplicate general-opportunity data must be absent');
    await expect(page.locator('#opportunity-compatibility')).toHaveCount(0);
    assert(data.trials?.some(trial=>trial.status && trial.outcome),'actual public trial evidence required');
    assert(data.delivery_preview,'canonical delivery preview required');
    await expect(page.locator('.equipment-card')).toHaveCount(data.library.options.length);
    await expect(page.locator('#equipment-native')).toContainText('Native sufficient');
    await expect(page.locator('#equipment-native')).toContainText('Prerequisites');
    await expect(page.locator('#equipment-native')).toContainText('Evidence');
    const assertNoOverflow=async(state)=>{
      const overflow=await page.evaluate(()=>({present:document.documentElement.scrollWidth>innerWidth,offenders:[...document.querySelectorAll('body *')].filter(el=>el.getBoundingClientRect().right>innerWidth+.5).map(el=>({tag:el.tagName,id:el.id,class:el.className}))}));
      assert(!overflow.present,`${state} overflow at ${width}: ${JSON.stringify(overflow.offenders)}`);
    };
    await assertNoOverflow('equipment');
    if ([320,1440].includes(width)) await page.screenshot({path:out+`equipment-${width}.png`});
    await page.getByLabel('Find equipment').fill('no-such-equipment');
    await expect(page.getByRole('heading',{name:'No matching equipment'})).toBeVisible();
    await page.getByRole('button',{name:'Reset equipment filters'}).click();
    await expect(page.getByLabel('Find equipment')).toBeFocused();
    await page.getByLabel('Selection',{exact:true}).selectOption('alternative');
    await expect(page.locator('#equipment-matt-pocock-tdd')).toBeVisible();
    await expect(page.locator('#equipment-context-output')).toHaveCount(0);
    await page.getByLabel('Selection',{exact:true}).selectOption('all');
    await page.getByLabel('Need',{exact:true}).selectOption('software');
    await expect(page.locator('.equipment-card')).toHaveCount(data.library.options.filter(item=>item.domains.includes('software')).length);
    await page.getByLabel('Need',{exact:true}).selectOption('all');
    // The public source can contain markup-shaped strings; they remain inert text.
    const originalName=data.library.options[0].name;
    await page.evaluate(()=>{window.CONTEXT_CATALOG.library.options[0].name='<img src=x onerror="window.untrustedRan=true">';renderEquipment();});
    await expect(page.locator('.equipment-card').first().locator('h3')).toHaveText('<img src=x onerror="window.untrustedRan=true">');
    await expect(page.locator('.equipment-card img')).toHaveCount(0);
    assert.equal(await page.evaluate(()=>window.untrustedRan),undefined);
    await page.evaluate(name=>{window.CONTEXT_CATALOG.library.options[0].name=name;renderEquipment();},originalName);
    await page.locator('.equipment-card').first().locator('summary').click();
    await assertNoOverflow('source disclosure');
    for (const palette of ['quiet','expressive']) {
      if (palette==='expressive') await page.getByRole('button',{name:'Expressive palette'}).click();
      for (const tab of ['Equipment','Loadouts','Trials']) {
        await page.getByRole('tab',{name:tab,exact:true}).click();
        await assertNoOverflow(`${tab}/${palette}`);
        if (tab==='Equipment' && palette==='expressive' && [320,1440].includes(width)) { await page.evaluate(()=>scrollTo(0,0)); await page.screenshot({path:out+`expressive-equipment-${width}.png`}); }
        const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
        assert.deepEqual(axe.violations,[],JSON.stringify({width,palette,tab,violations:axe.violations}));
      }
    }
    await page.getByRole('button',{name:'Expressive palette'}).click();
    await page.getByRole('tab',{name:'Loadouts',exact:true}).click();
    await page.getByLabel('Project setup').selectOption('principles');
    await expect(page.locator('.profile-card')).toHaveCount(1);
    await expect(page.locator('.profile-card')).toContainText('No added task guidance; ordinary work uses native tools');
    if ([320,1440].includes(width)) { await page.evaluate(()=>scrollTo(0,0)); await page.screenshot({path:out+`native-loadout-${width}.png`}); }
    await page.getByLabel('Project setup').selectOption('signals');
    await expect(page.locator('.profile-card')).toContainText(data.library.options.find(item=>item.id==='context-output').name);
    await expect(page.locator('.profile-card')).toContainText(data.library.profiles.find(profile => profile.id === 'signals').selections.find(choice => choice.option === 'context-output').reason);
    await page.locator('.profile-card summary').click();
    await assertNoOverflow('profile details');
    if ([320,1440].includes(width)) { await page.evaluate(()=>scrollTo(0,0)); await page.screenshot({path:out+`loadout-${width}.png`}); }
    const groups=page.locator('.preview-group');
    await expect(groups).toHaveCount(4);
    await expect(page.locator('.preview-group.conflicts')).not.toContainText('None in this example');
    if ([320,1440].includes(width)) await page.locator('.delivery').screenshot({path:out+`preview-conflict-${width}.png`});
    await page.getByText('Prepare the selected profile request',{exact:true}).click();
    const requestNetwork=[];
    const recordRequest=request=>requestNetwork.push({url:request.url(),method:request.method()});
    page.on('request',recordRequest);
    await page.getByText('Explicit equipment commands and recovery',{exact:true}).click();
    await page.getByLabel('Equipment to inspect locally').selectOption('context-output');
    await page.getByLabel('Host',{exact:true}).selectOption('both');
    await expect(page.locator('#local-command')).toContainText('plan --with context-output --project /absolute/project --provider both');
    const downloaded=page.waitForEvent('download');
    await page.getByRole('button',{name:'Export profile plan request'}).click();
    const download=await downloaded;
    const request=JSON.parse(await readFile(await download.path(),'utf8'));
    assert.deepEqual(Object.keys(request).sort(),['constraints','findings','method','profile_id','project_ref','request_id','schema_version']);
    assert.equal(request.profile_id,'signals');assert.equal(request.method,'plan');
    assert.deepEqual(request.project_ref,{id:'signals',source_ref:data.library.profiles.find(item=>item.id==='signals').project || 'interest:signals'});
    assert.deepEqual(request.constraints,[]);assert.deepEqual(request.findings,[]);
    assert(!JSON.stringify(request).includes('/Users/'));
    await expect(page.locator('#request-status')).toContainText('nothing was installed');
    await page.getByLabel('Project setup').selectOption('principles');
    await page.getByLabel('Equipment to inspect locally').selectOption('web-experience');
    await expect(page.locator('#request-status')).toBeEmpty();
    await expect(page.locator('#local-command')).toContainText('plan web-experience --project /absolute/project');
    assert.deepEqual(requestNetwork,[],'public controls/export must not send requests');page.off('request',recordRequest);
    await expect(page.getByRole('button',{name:'Apply',exact:true})).toHaveCount(0);
    await assertNoOverflow('request and commands');
    await page.getByText('Browse all concern-specific loadouts',{exact:true}).click();
    await page.getByLabel('Find a loadout').fill('no-such-loadout');
    await expect(page.getByRole('heading',{name:'No matching loadouts'})).toBeVisible();
    await page.getByRole('button',{name:'Clear filters'}).click();
    await expect(page.getByLabel('Find a loadout')).toBeFocused();
    await expect(page.locator('.loadout')).toHaveCount(data.loadouts.length);
    await page.getByLabel('Web',{exact:true}).check();
    await expect(page.locator('.loadout')).toHaveCount(data.loadouts.filter(item=>item.kind==='web').length);
    await page.getByRole('tab',{name:'Trials',exact:true}).click();
    await expect(page.locator('.trial-card')).toHaveCount(data.trials.length);
    for (const trial of data.trials) await expect(page.locator(`#trial-${trial.id} .trial-outcome`)).toHaveText(trial.outcome);
    await page.locator('.trial-card').first().locator('summary').click();
    await assertNoOverflow('negative trial detail');
    if ([320,1440].includes(width)) { await page.evaluate(()=>scrollTo(0,0)); await page.screenshot({path:out+`negative-trial-${width}.png`}); }
    await page.goto(base);await page.keyboard.press('Tab');
    await expect(page.getByRole('link',{name:'Skip to equipment library'})).toBeFocused();
    await page.keyboard.press('Enter');await expect(page.locator('#main')).toBeFocused();
    await page.keyboard.press('Tab');await expect(page.getByRole('tab',{name:'Equipment',exact:true})).toBeFocused();
    await page.keyboard.press('ArrowRight');await expect(page.getByRole('tab',{name:'Loadouts',exact:true})).toBeFocused();
    await expect(page.locator('#loadouts')).toBeVisible();
    await page.keyboard.press('End');await expect(page.getByRole('tab',{name:'Trials',exact:true})).toBeFocused();
    await page.keyboard.press('Home');await expect(page.getByRole('tab',{name:'Equipment',exact:true})).toBeFocused();
    assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');
    assert(!(await page.evaluate(()=>document.body.textContent.includes('/Users/'))),'public UI must exclude private absolute target paths');
    results.push({width,axe_scans:6,axe_violations:0,overflow:false,public_action_requests:0,states:'equipment filter/empty/focus recovery, text-only source, native and focused profiles, canonical protected conflict, request download/edit, legacy loadout recovery, actual negative trial, keyboard tabs/skip, reduced motion'});
    await context.close();
  }
  assert.deepEqual(errors,[]);
  await writeFile(out+'results.json',JSON.stringify({evidence_class:'browser functional checks + builder visual inspection; canonical public fixture rendered, no local apply',results,errors,limits:['No assistive-technology user test. No deployed field Web Vitals. Axe does not certify WCAG conformance. No independent human usefulness measurement.']},null,2)+'\n');
  console.log(`Web verification passed: ${results.length} widths, 24 axe scans, public request export, scoped trials and canonical conflict; evidence ${out}`);
} finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
