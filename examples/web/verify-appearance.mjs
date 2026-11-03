import {expect} from '@playwright/test';
import assert from 'node:assert/strict';

const KEY = 'context-ai.appearance.v1';
const open = page => page.locator('.appearance-settings > summary').click();
const theme = page => page.locator('html');

export async function verifyAppearance(browser, base) {
  const context = await browser.newContext({colorScheme:'light', viewport:{width:390,height:844}});
  const page = await context.newPage();
  try {
    await page.goto(base); await open(page);
    await expect(theme(page)).toHaveAttribute('data-theme','neon1-light');
    await page.emulateMedia({colorScheme:'dark'});
    await expect(theme(page)).toHaveAttribute('data-theme','neon1-dark');
    await page.getByLabel('Theme preset',{exact:true}).selectOption('forest-light');
    await page.emulateMedia({colorScheme:'light'});
    await expect(theme(page)).toHaveAttribute('data-theme','forest-light');
    await page.reload(); await open(page);
    await expect(theme(page)).toHaveAttribute('data-theme','forest-light');
    await page.getByLabel('Density',{exact:true}).selectOption('compact');
    await page.getByRole('button',{name:'Apply changes',exact:true}).click();
    await expect(theme(page)).toHaveAttribute('data-theme-density','compact');
    await page.getByLabel('Accent color',{exact:true}).evaluate(input => {
      input.value='#ffffff'; input.dispatchEvent(new Event('input',{bubbles:true}));
    });
    await page.getByRole('button',{name:'Apply changes',exact:true}).click();
    await expect(page.locator('#appearance-status')).toContainText('Invalid theme preference');
    await expect(theme(page)).toHaveAttribute('data-theme','forest-light');
    const saved = await page.evaluate(key=>localStorage.getItem(key),KEY);
    assert(!saved.includes('#ffffff'),'rejected overrides must not persist');
    await page.evaluate(()=>localStorage.setItem('deep.appearance.v1','independent'));
    const second=await context.newPage(); await second.goto(base); await open(second);
    await second.getByLabel('Theme preset',{exact:true}).selectOption('matrix-dark');
    await expect(theme(page)).toHaveAttribute('data-theme','matrix-dark');
    await second.getByRole('button',{name:'Reset appearance',exact:true}).click();
    await expect(theme(page)).toHaveAttribute('data-theme','neon1-light');
    assert.equal(await page.evaluate(()=>localStorage.getItem('deep.appearance.v1')),'independent');
    await second.close();
    await page.getByRole('button',{name:'Alternate colors',exact:true}).focus();
    await page.keyboard.press('Enter');
    await expect(theme(page)).toHaveAttribute('data-theme','matrix-dark');
    await expect(page.getByRole('button',{name:'Alternate colors',exact:true})).toHaveAttribute('aria-pressed','true');
    await page.keyboard.press('Space');
    await expect(theme(page)).toHaveAttribute('data-theme','neon1-light');
    await page.getByLabel('Theme preset',{exact:true}).focus();
    await expect(page.getByLabel('Theme preset',{exact:true})).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByLabel('Accent color',{exact:true})).toBeFocused();
    const invalid='{"version":99}';
    await page.evaluate(({key,invalid})=>localStorage.setItem(key,invalid),{key:KEY,invalid});
    await page.reload(); await open(page);
    await expect(page.locator('#appearance-status')).toContainText('Saved appearance is invalid');
    assert.equal(await page.evaluate(key=>localStorage.getItem(key),KEY),invalid);
    await expect(theme(page)).toHaveAttribute('data-theme','neon1-light');
  } finally { await context.close(); }

  for (const kind of ['methods','getter']) {
    const blocked = await browser.newContext({viewport:{width:320,height:900}});
    try {
      await blocked.addInitScript(kind=>{
        const fail=()=>{throw new DOMException('blocked','SecurityError');};
        if (kind==='getter') Object.defineProperty(window,'localStorage',{get:fail});
        else for (const method of ['getItem','setItem','removeItem']) Object.defineProperty(Storage.prototype,method,{value:fail});
      },kind);
      const page=await blocked.newPage(); await page.goto(base); await open(page);
      await page.getByLabel('Theme preset',{exact:true}).selectOption('slate-dark');
      await expect(theme(page)).toHaveAttribute('data-theme','slate-dark');
      await expect(page.locator('#appearance-status')).toContainText('only to this page');
      await page.locator('.appearance-settings > summary').click();
      await page.getByRole('button',{name:'Alternate colors',exact:true}).click();
      await expect(page.locator('#appearance-status')).toBeVisible();
      await expect(theme(page)).toHaveAttribute('data-theme','matrix-dark');
      await page.getByRole('tab',{name:'Project setups',exact:true}).click();
      await page.getByLabel('Project setup',{exact:true}).selectOption('signals');
      await expect(page.locator('.profile-card')).toContainText('Capture and inspect command output');
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      await page.getByRole('button',{name:'Reset appearance',exact:true}).click();
      await expect(page.locator('#appearance-status')).toContainText(kind==='getter'?'Browser storage is unavailable':'Reset for this page');
    } finally {await blocked.close();}
  }
  return {system_changes:true,explicit_reload:true,tab_sync:true,independent_key:true,invalid_preserved:true,low_contrast_rejected:true,keyboard:'shortcut Enter/Space and native select focus/tab; native menu Arrow selection unavailable in this headless macOS run',blocked_storage:['methods','getter']};
}
