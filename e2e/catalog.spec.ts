import { test, expect } from '@playwright/test';

test('loads the live catalog and supports cart, filtering and language', async ({ page }, testInfo) => {
  const response = await page.goto('/');
  expect(response?.ok()).toBeTruthy();
  await expect(page.locator('.product')).toHaveCount(30);
  await expect(page.locator('.product').first()).toContainText('iPhone 15 Pro');
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
