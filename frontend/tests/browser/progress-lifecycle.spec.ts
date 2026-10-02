import type { Page } from '@playwright/test';
import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { detectedItems } from './fixtures/data';
import { selectLocation, uploadPhoto } from './helpers/scan';

async function installProgressClock(page: Page) {
	await page.clock.install({ time: new Date('2026-01-01T12:00:00Z') });
	await page.clock.pauseAt(new Date('2026-01-01T12:00:10Z'));
	await page.addInitScript(() => {
		// Keep native view-transition scheduling out of these controlled timer tests.
		Object.defineProperty(document, 'startViewTransition', {
			configurable: true,
			value: undefined,
		});
	});
}

async function beginAnalysis(page: Page) {
	await selectLocation(page);
	await uploadPhoto(page);
	const detection = page.waitForResponse(
		(response) => new URL(response.url()).pathname === '/api/tools/vision/detect' && response.ok()
	);
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await detection;
}

for (const suffix of ['', ' @mobile']) {
	test(`progress completion navigates to review exactly once${suffix}`, async ({ page, api }) => {
		await installProgressClock(page);
		api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Desk lamp'])));

		let reviewNavigations = 0;
		page.on('framenavigated', (frame) => {
			if (frame === page.mainFrame() && new URL(frame.url()).pathname === '/review') {
				reviewNavigations++;
			}
		});

		await beginAnalysis(page);
		await expect(page.getByText('Analysis complete!')).toBeVisible();
		await page.clock.runFor(1_500);
		await expect(page).toHaveURL(/\/review$/);
		await page.clock.runFor(2_000);
		expect(reviewNavigations).toBe(1);
	});

	test(`leaving capture during completion delay keeps Settings active${suffix}`, async ({
		page,
		api,
	}) => {
		await installProgressClock(page);
		api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Desk lamp'])));

		await beginAnalysis(page);
		await expect(page.getByText('Analysis complete!')).toBeVisible();
		// Enter the success animation and start its completion hold before navigating away.
		await page.clock.runFor(100);
		// Use client-side navigation: a full document load would discard leaked timers too.
		await page.locator('nav a[href="/settings"]:visible').click();
		// Let SvelteKit's click-navigation frame run, before the completion hold expires.
		await page.clock.runFor(50);
		await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
		await page.clock.runFor(1_000);
		await expect(page).toHaveURL(/\/settings$/);
	});
}

test('full image progress waits for tag processing before completion is ready', async ({
	page,
	api,
}) => {
	await installProgressClock(page);
	const tagGate = api.gate();
	api.on('GET', '/api/tags', async () => {
		await tagGate.promise;
		return json([]);
	});
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Desk lamp'])));

	await beginAnalysis(page);
	await expect(page.getByText('1 / 1')).toBeVisible();
	await page.clock.runFor(1_500);
	await expect(page).toHaveURL(/\/capture$/);
	await expect(page.getByText('Analysis complete!')).toHaveCount(0);

	tagGate.release();
	await expect(page.getByText('Analysis complete!')).toBeVisible();
	await page.clock.runFor(1_500);
	await expect(page).toHaveURL(/\/review$/);
});
