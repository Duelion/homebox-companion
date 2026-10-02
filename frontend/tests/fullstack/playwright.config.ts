import { defineConfig } from '@playwright/test';

if (!process.env.HBC_SMOKE_URL) {
	throw new Error(
		'Run this smoke test through tests/test_fullstack_smoke.py; see tests/README.md.'
	);
}

export default defineConfig({
	testDir: '.',
	testMatch: 'scan.spec.ts',
	workers: 1,
	retries: 0,
	forbidOnly: true,
	timeout: 60_000,
	outputDir: '../../test-results/fullstack',
	reporter: 'list',
	use: {
		baseURL: process.env.HBC_SMOKE_URL,
		browserName: 'chromium',
		serviceWorkers: 'block',
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
	},
});
