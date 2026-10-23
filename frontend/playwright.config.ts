import { defineConfig, devices } from '@playwright/test';

const isCanonicalVisualPlatform = process.platform === 'linux';
const useSystemChrome = process.env.PLAYWRIGHT_SYSTEM_CHROME === '1';

const desktopGrepInvert = isCanonicalVisualPlatform ? /@mobile/ : /@mobile|@visual/;

export default defineConfig({
	testDir: './tests/browser',
	fullyParallel: true,
	workers: 2,
	retries: 0,
	forbidOnly: Boolean(process.env.CI),
	reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
	outputDir: 'test-results',
	use: {
		baseURL: 'http://127.0.0.1:4173',
		serviceWorkers: 'block',
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
	},
	projects: [
		{
			name: 'chromium',
			grepInvert: desktopGrepInvert,
			use: { browserName: 'chromium' },
		},
		{
			name: 'webkit-mobile',
			grep: /@mobile/,
			grepInvert: /@visual/,
			use: { ...devices['iPhone 13'], browserName: 'webkit' },
		},
		...(useSystemChrome
			? [
					{
						name: 'chrome',
						grepInvert: /@mobile|@visual/,
						use: { browserName: 'chromium' as const, channel: 'chrome' },
					},
				]
			: []),
	],
	webServer: {
		command:
			'node node_modules/vite/bin/vite.js preview --mode browser-test --host 127.0.0.1 --port 4173 --strictPort',
		url: 'http://127.0.0.1:4173',
		reuseExistingServer: false,
	},
});
