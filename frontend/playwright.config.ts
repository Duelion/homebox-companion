import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: './tests/browser',
	fullyParallel: true,
	use: {
		baseURL: 'http://127.0.0.1:4173',
		browserName: 'chromium',
		// Developers use their installed Chrome channel. CI installs Playwright's
		// bundled Chromium, which is available without a system Chrome install.
		channel: process.env.CI ? undefined : 'chrome',
	},
	webServer: {
		command: 'npm run build && npm run preview -- --host 127.0.0.1',
		url: 'http://127.0.0.1:4173',
		reuseExistingServer: false,
	},
});
