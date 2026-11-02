import {test,expect} from '@playwright/test';
import {writeFileSync} from 'node:fs';
test.describe.configure({mode:'default'});
async function catalog(page:any){await page.goto('/');await expect(page.locator('.product')).toHaveCount(30);}
async function cart(page:any,info:any){if(info.project.name!=='desktop')await page.getByRole('button',{name:/Open cart/}).click();}
test('retail search reset restores visible input and keyboard search',async({page},info)=>{
 await catalog(page);const search=page.getByRole('searchbox',{name:'Search products'});await search.fill('no-such-fictional-product');await expect(page.locator('.product')).toHaveCount(0);await page.screenshot({path:info.outputPath('search-empty.png')});await page.getByRole('button',{name:'Clear filters',exact:true}).click();await expect(page.locator('.product')).toHaveCount(30);await expect(search).toHaveValue('');await page.keyboard.press('F2');await expect(search).toBeFocused();
});
test('committed response lost freezes sale and retries exactly once',async({page},info)=>{
 await catalog(page);const before=(await(await page.request.get('/api/inventory/p28')).json()).stock;
 await page.getByRole('button',{name:'Add Xbox Wireless Controller',exact:true}).click();await cart(page,info);await page.getByRole('button',{name:/Proceed to Checkout/}).click();await page.getByRole('combobox',{name:'Payment method'}).selectOption('card');
 const requests:any[]=[];let dropped=false;await page.route('**/api/checkout',async route=>{requests.push(route.request().postDataJSON());if(!dropped){dropped=true;const response=await route.fetch();expect(response.ok()).toBeTruthy();await route.abort('failed');}else await route.continue();});
 await page.getByRole('button',{name:'Complete sale',exact:true}).click();await expect(page.getByRole('alert')).toContainText('uncertain');await page.screenshot({path:info.outputPath('committed-response-lost.png')});
 await expect(page.getByRole('combobox',{name:'Payment method'})).toBeDisabled();await expect(page.getByRole('button',{name:'Close payment',exact:true})).toBeDisabled();await page.keyboard.press('Escape');await expect(page.getByRole('dialog',{name:'Complete payment'})).toBeVisible();
 await page.reload();await expect(page.getByRole('alert')).toContainText('uncertain');await page.locator('.payment-dialog .checkout').evaluate((b:HTMLButtonElement)=>{b.click();b.click();});await expect(page.getByRole('heading',{name:/Receipt MOS-/})).toBeVisible();expect(requests).toHaveLength(2);expect(requests[1]).toEqual(requests[0]);expect((await(await page.request.get('/api/inventory/p28')).json()).stock).toBe(before-1);await page.screenshot({path:info.outputPath('receipt.png'),fullPage:true});
});
test('mixed cart cash discount VAT removal and keyboard payment cancellation',async({page},info)=>{
 await catalog(page);await page.getByRole('button',{name:'Add Braided USB-C Cable',exact:true}).click();await page.getByRole('button',{name:'Add Anker 737 Power Bank',exact:true}).click();await cart(page,info);await page.getByRole('button',{name:'Increase Braided USB-C Cable',exact:true}).click();await page.getByRole('button',{name:'Remove Anker 737 Power Bank',exact:true}).click();await page.getByRole('combobox',{name:'Store Discount',exact:true}).selectOption('5');await page.screenshot({path:info.outputPath('cart.png'),fullPage:true});
 const total=await page.locator('.payable strong').innerText();await page.getByRole('button',{name:/Proceed to Checkout/}).click();await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:/Proceed to Checkout/})).toBeFocused();await page.getByRole('button',{name:/Proceed to Checkout/}).click();await page.getByRole('spinbutton',{name:/Cash tendered/}).fill('5000');await page.getByRole('button',{name:'Complete sale',exact:true}).click();await expect(page.getByRole('heading',{name:/Receipt MOS-/})).toBeVisible();await expect(page.locator('.receipt')).toContainText(total);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
test('retail performance observations use actual catalog and browser timings',async({page},info)=>{
 const samples:number[]=[];const start=performance.now();await catalog(page);const initial=performance.now()-start;await page.screenshot({path:info.outputPath('catalog.png'),fullPage:true});
 for(let i=0;i<10;i++){const t=performance.now();await page.getByRole('searchbox',{name:'Search products'}).fill(i%2?'Sony':'Galaxy');await expect(page.locator('.product')).toHaveCount(i%2?1:4);samples.push(performance.now()-t);}
 samples.sort((a,b)=>a-b);writeFileSync(info.outputPath('performance.json'),JSON.stringify({schema:1,viewport:info.project.use.viewport,revision:process.env.GITHUB_SHA,runner:process.env.RUNNER_OS,node:process.version,dataset:{catalog:30},concurrency:1,method:'Playwright fill plus rendered count, warm client filtering; initial includes session check',initialMs:initial,searchP50Ms:samples[4],searchP95Ms:samples[9],samplesMs:samples,productionGuarantee:false},null,2));
});

test('automated accessibility, narrow reflow and keyboard critical path',async({page},info)=>{
 const {resolve}=await import('node:path');await catalog(page);
 const results:any[]=[];
 for(const state of ['catalog','arabic','payment']){
  if(state==='arabic')await page.getByRole('button',{name:/Switch language to Arabic/}).click();
  if(state==='payment'){await page.getByRole('button',{name:/Switch language to English/}).click();await page.getByRole('button',{name:'Add Braided USB-C Cable',exact:true}).click();await cart(page,info);await page.getByRole('button',{name:/Proceed to Checkout/}).click();await page.keyboard.press('Shift+Tab');await expect(page.getByRole('button',{name:'Close payment',exact:true})).toBeFocused();await page.keyboard.press('Shift+Tab');await expect(page.getByRole('button',{name:'Complete sale',exact:true})).toBeFocused();}
  await page.addScriptTag({path:resolve('node_modules/axe-core/axe.min.js')});const r=await page.evaluate(async()=>await(window as any).axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}}));results.push({state,violations:r.violations,incomplete:r.incomplete.map((x:any)=>({id:x.id,impact:x.impact})),passes:r.passes.length});await page.screenshot({path:info.outputPath('accessibility-'+state+'.png'),fullPage:true});
 }
 writeFileSync(info.outputPath('accessibility.json'),JSON.stringify(results,null,2));
 await page.keyboard.press('Escape');await page.setViewportSize({width:320,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:info.outputPath('narrow-320.png'),fullPage:true});
});
