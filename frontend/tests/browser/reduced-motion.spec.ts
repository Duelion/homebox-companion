import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { createdItem, detectedItems } from './fixtures/data';
import { selectLocation, uploadPhoto, confirmItems, submitItems } from './helpers/scan';

test('reduced motion completes analysis without an animation hold and reveals success artwork', async ({
	page,
	api,
}) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.addInitScript(() => {
		// Keep native view-transition scheduling out of the controlled timer assertion.
		Object.defineProperty(document, 'startViewTransition', {
			configurable: true,
			value: undefined,
		});
	});
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Desk lamp'])));
	api.on('POST', '/api/items', () => json(createdItem('item-1')));
	api.on('POST', /^\/api\/items\/[^/]+\/attachments$/, () => json({}));

	await selectLocation(page);
	await uploadPhoto(page);
	await page.clock.install({ time: new Date('2026-01-01T12:00:00Z') });
	await page.clock.pauseAt(new Date('2026-01-01T12:00:10Z'));
	const detection = page.waitForResponse(
		(response) => new URL(response.url()).pathname === '/api/tools/vision/detect' && response.ok()
	);
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await detection;
	await page.clock.runFor(50);
	await expect(page).toHaveURL(/\/review$/);
	await page.clock.resume();

	await confirmItems(page, 1);
	await submitItems(page);
	await expect(page.getByRole('heading', { name: 'Success!' })).toBeVisible();
	await expect(page.locator('.success-scale').first()).toHaveCSS(
		'transform',
		'matrix(1, 0, 0, 1, 0, 0)'
	);
	await expect(page.locator('.checkmark-draw')).toHaveCSS('stroke-dashoffset', '0px');
});

test('reduced motion reveals expandable controls without a slide transition', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await selectLocation(page);
	await uploadPhoto(page);
	const expand = page.getByRole('button', { name: /options|expand/i }).first();
	await expand.click();
	await expect(page.getByText('Separate into multiple items')).toBeVisible();
	await expect(page.getByText('Separate into multiple items')).toHaveCSS('animation-name', 'none');
});
