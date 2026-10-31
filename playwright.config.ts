import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  globalSetup:"./e2e/auth.setup.ts",
  testDir: './e2e',
  timeout: 30_000,
  retries: 0,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: { storageState:'/tmp/merchant-pos-state.json', baseURL: 'http://127.0.0.1:4200', trace: 'off', screenshot: 'only-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'tablet', use: { ...devices['Desktop Chrome'], viewport: { width: 768, height: 1024 }, isMobile: true, hasTouch: true } },
    { name: 'mobile', use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: 'npm start -- --host 127.0.0.1',
    url: 'http://127.0.0.1:4200',
    reuseExistingServer: !process.env['CI'],
    timeout: 120_000,
  },
});
