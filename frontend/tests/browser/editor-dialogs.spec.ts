import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { detectedItems } from './fixtures/data';
import { selectLocation, uploadPhoto, analyzePhotos } from './helpers/scan';

test('thumbnail editor contains focus and Escape restores the edit trigger', async ({
	page,
	api,
}) => {
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Lamp'])));
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	const trigger = page.getByRole('button', { name: 'Edit thumbnail image' });
	await trigger.click();
	const dialog = page.getByRole('dialog', { name: 'Edit Thumbnail', exact: true });
	await expect(dialog.getByRole('button', { name: 'Close', exact: true })).toBeFocused();
	await page.keyboard.press('Shift+Tab');
	await expect(dialog.getByRole('button', { name: 'Save Thumbnail' })).toBeFocused();
	await page.keyboard.press('Escape');
	await expect(dialog).toBeHidden();
	await expect(trigger).toBeFocused();
});

test('QR scanner closes with Escape and restores focus without changing location', async ({
	page,
}) => {
	await page.addInitScript(() => {
		navigator.mediaDevices.getUserMedia = async () => {
			throw new DOMException('Camera unavailable in test', 'NotAllowedError');
		};
	});
	await page.goto('/location');
	const trigger = page.getByRole('button', { name: 'Scan QR Code' });
	await trigger.click();
	const dialog = page.getByRole('dialog');
	await expect(dialog.getByRole('button', { name: 'Close scanner' })).toBeFocused();
	await page.keyboard.press('Escape');
	await expect(dialog).toBeHidden();
	await expect(trigger).toBeFocused();
	await expect(page).toHaveURL(/\/location$/);
});

test('thumbnail editor fits a narrow viewport and permits browser zoom @mobile', async ({
	page,
	api,
}) => {
	await page.setViewportSize({ width: 320, height: 640 });
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Lamp'])));
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByRole('button', { name: 'Edit thumbnail image' }).tap();
	const dialog = page.getByRole('dialog', { name: 'Edit Thumbnail', exact: true });
	await expect(dialog).toBeVisible();
	expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
	const close = dialog.getByRole('button', { name: 'Close', exact: true });
	const bounds = await close.boundingBox();
	expect(bounds?.width).toBeGreaterThanOrEqual(44);
	expect(bounds?.height).toBeGreaterThanOrEqual(44);
	const viewport = await page.locator('meta[name="viewport"]').getAttribute('content');
	expect(viewport).not.toMatch(/maximum-scale|user-scalable\s*=\s*no/);
	await close.tap();
	await expect(dialog).toBeHidden();
});
