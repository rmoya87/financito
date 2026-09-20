import {defineConfig,devices} from '@playwright/test';

export default defineConfig({
  testDir:'./e2e',
  timeout:30_000,
  expect:{timeout:8_000},
  use:{
    baseURL:process.env.FINANCITO_E2E_URL||'http://127.0.0.1:8765',
    trace:'retain-on-failure',
    screenshot:'only-on-failure',
  },
  reporter:process.env.CI?'github':'list',
  projects:[
    {name:'chromium',use:{...devices['Desktop Chrome']}},
  ],
});
