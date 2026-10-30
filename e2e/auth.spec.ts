import {test,expect} from '@playwright/test';
test.use({storageState:{cookies:[],origins:[]},trace:'off',screenshot:'off'});
async function password(page:any,value:string){await page.locator('#password').evaluate((el:HTMLInputElement,p:string)=>{el.value=p;el.dispatchEvent(new Event('input',{bubbles:true}));},value);}
test('cashier browser signs in and signs out without browser token storage',async({page})=>{
 await page.goto('/');await expect(page.getByRole('heading',{name:'MerchantOS POS'})).toBeVisible();await page.getByLabel('Username',{exact:true}).fill(process.env['TEST_CASHIER_USERNAME']!);await password(page,process.env['TEST_CASHIER_PASSWORD']!);
 await page.getByRole('button',{name:'Sign In',exact:true}).click();await expect(page.locator('.product')).toHaveCount(30);
 const cookie=(await page.context().cookies()).find(c=>c.name==='MerchantOS.Pos.Session');expect(cookie?.httpOnly).toBeTruthy();expect(cookie?.sameSite).toBe('Strict');
 expect(await page.evaluate(()=>localStorage.length+sessionStorage.length)).toBe(0);
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.getByRole('heading',{name:'MerchantOS POS'})).toBeVisible();
 expect((await page.request.get('/api/products')).status()).toBe(401);
});
test('invalid and administrator credentials cannot open cashier checkout',async({page})=>{
 await page.goto('/');await page.getByLabel('Username',{exact:true}).fill('missing-user');await password(page,'invalid-password');await page.getByRole('button',{name:'Sign In',exact:true}).click();await expect(page.getByRole('alert')).toContainText('Unable to sign in');
 await page.getByLabel('Username',{exact:true}).fill(process.env['TEST_ADMIN_USERNAME']!);await password(page,process.env['TEST_ADMIN_PASSWORD']!);await page.getByRole('button',{name:'Sign In',exact:true}).click();await expect(page.getByRole('alert')).toContainText('Unable to sign in');await expect(page.locator('.product')).toHaveCount(0);
});
