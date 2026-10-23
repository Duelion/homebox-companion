import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { config, detectedItems } from './fixtures/data';
import { selectLocation, uploadPhoto } from './helpers/scan';

const detectPath = '/api/tools/vision/detect';

// Native AbortSignal.timeout uses browser active time rather than Playwright's clock.
// Exercise the supported timer fallback to advance request deadlines deterministically.
test.beforeEach(async ({ page }) => {
	await page.addInitScript(() => {
		Object.defineProperty(AbortSignal, 'timeout', { value: undefined, configurable: true });
	});
	await page.clock.install();
});

for (const outcome of ['success', 'expiry', 'cancel'] as const) {
	test(`configured vision deadline: ${outcome} after more than 60 seconds`, async ({
		page,
		api,
	}) => {
		api.on('GET', '/api/config', () => json({ ...config(), ai_request_timeout_seconds: 90 }));
		const gate = api.gate();
		let started = false;
		api.on('POST', detectPath, async () => {
			started = true;
			await gate.promise;
			return json(detectedItems(['Patient camera']));
		});
		await selectLocation(page);
		await uploadPhoto(page);
		await page.getByRole('button', { name: /Analyze with AI/ }).click();
		await expect.poll(() => started).toBe(true);
		await page.clock.fastForward(61_000);
		await expect(page.getByRole('button', { name: 'Cancel Analysis' })).toBeVisible();
		if (outcome === 'success') {
			gate.release();
			await expect(page).toHaveURL(/\/review$/);
			await expect(page.getByLabel('Name')).toHaveValue('Patient camera');
		} else {
			const failed = page.waitForEvent(
				'requestfailed',
				(request) => new URL(request.url()).pathname === detectPath
			);
			if (outcome === 'expiry') {
				await page.clock.fastForward(28_000);
				await expect(page.getByRole('button', { name: 'Cancel Analysis' })).toBeVisible();
				await page.clock.fastForward(1_000);
			} else await page.getByRole('button', { name: 'Cancel Analysis' }).click();
			await failed;
			await expect(page.getByRole('button', { name: /Analyze with AI/ })).toBeEnabled();
		}
	});
}
