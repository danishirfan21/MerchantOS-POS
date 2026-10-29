import { test, expect } from '@playwright/test';

test('loads the live catalog and supports cart, filtering and language', async ({ page }, testInfo) => {
  const response = await page.goto('/');
  expect(response?.ok()).toBeTruthy();
  await expect(page.locator('.product')).toHaveCount(30);
  await expect(page.locator('.product').filter({ hasText: 'iPhone 15 Pro' })).toHaveCount(1);
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-catalog.png`), fullPage: true });

  await page.getByRole('searchbox', { name: 'Search products' }).fill('Sony');
  await expect(page.locator('.product')).toHaveCount(1);
  await page.getByRole('searchbox', { name: 'Search products' }).fill('');
  await page.getByRole('button', { name: 'Audio', exact: false }).click();
  await expect(page.locator('.product')).toHaveCount(5);
  await page.getByRole('button', { name: 'All products', exact: false }).click();
  await page.getByRole('button', { name: 'Add iPhone 15 Pro' }).click();
  await page.getByRole('button', { name: 'Switch language' }).click();
  await expect(page.locator('.pos')).toHaveAttribute('dir', 'rtl');
  if (testInfo.project.name === 'mobile') {
    await page.getByRole('button', { name: /Open cart/ }).click();
    await expect(page.locator('.cart')).toHaveClass(/open/);
    await page.screenshot({ path: testInfo.outputPath('mobile-cart.png'), fullPage: true });
  }
  await expect(page.locator('.cart .line')).toHaveCount(1);
  await page.getByRole('button', { name: 'Increase iPhone 15 Pro' }).click();
  await expect(page.locator('.cart .stepper span')).toHaveText('2');
  await expect(page.locator('.cart .line')).toHaveCount(1);
  if (testInfo.project.name === 'mobile') {
    await page.keyboard.press('Escape');
    await expect(page.locator('.cart')).not.toHaveClass(/open/);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('completes cash checkout against live API and views receipt', async ({ page }, testInfo) => {
  await page.goto('/');
  await expect(page.locator('.product')).toHaveCount(30);
  await page.getByRole('button', { name: 'Add iPhone 15 Pro' }).click();
  if (testInfo.project.name === 'mobile') await page.getByRole('button', { name: /Open cart/ }).click();
  await page.getByRole('button', { name: /Proceed to Checkout/ }).click();
  await page.getByRole('spinbutton', { name: /Cash tendered/ }).fill('5000');
  await page.getByRole('button', { name: 'Complete sale' }).click();
  await expect(page.getByRole('heading', { name: /Receipt MOS-/ })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-receipt.png`), fullPage: true });
  await page.getByRole('button', { name: 'Orders', exact: true }).click();
  await expect(page.locator('.history-row')).not.toHaveCount(0);
});

test('recovers from declined card and deducts inventory once', async ({ page }, testInfo) => {
  const productId = testInfo.project.name === 'mobile' ? 'p03' : 'p02';
  const productName = productId === 'p03' ? 'Pixel 8 Pro' : 'Galaxy S24 Ultra';
  const before = await (await page.request.get(`/api/inventory/${productId}`)).json();
  await page.goto('/');
  await expect(page.locator('.product')).toHaveCount(30);
  await page.getByRole('button', { name: `Add ${productName}` }).click();
  if (testInfo.project.name === 'mobile') await page.getByRole('button', { name: /Open cart/ }).click();
  await page.getByRole('button', { name: /Proceed to Checkout/ }).click();
  await page.getByRole('combobox', { name: 'Payment method' }).selectOption('card');
  await page.getByRole('combobox', { name: 'Simulation' }).selectOption('decline');
  await page.getByRole('button', { name: 'Complete sale' }).click();
  await expect(page.getByRole('alert')).toContainText('Simulated card declined');
  await expect(page.locator('.cart .line')).toHaveCount(1);
  expect((await (await page.request.get(`/api/inventory/${productId}`)).json()).stock).toBe(before.stock);
  await page.getByRole('combobox', { name: 'Simulation' }).selectOption('success');
  await page.getByRole('button', { name: 'Complete sale' }).click();
  await expect(page.getByRole('heading', { name: /Receipt MOS-/ })).toBeVisible();
  expect((await (await page.request.get(`/api/inventory/${productId}`)).json()).stock).toBe(before.stock - 1);
  await page.screenshot({ path: testInfo.outputPath(`${testInfo.project.name}-payment-recovery.png`), fullPage: true });
});
