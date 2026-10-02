import { expect, test } from './fixtures/test';
import { fileURLToPath } from 'node:url';
import { detectedItems } from './fixtures/data';
import { selectLocation, uploadPhoto, analyzePhotos } from './helpers/scan';
import { json } from './fixtures/api';

test('a late profile save cannot close a reopened profile draft', async ({ page, api }) => {
	const gate = api.gate();
	api.on('POST', '/api/llm/profiles', async () => {
		await gate.promise;
		return json({ name: 'First', model: 'gpt-5-nano', status: 'off' });
	});
	await page.goto('/settings');
	await page.getByRole('button', { name: 'Add', exact: true }).click();
	const dialog = page.getByRole('dialog', { name: 'New Profile' });
	await dialog.getByLabel('Name', { exact: true }).fill('First');
	await dialog.getByLabel('Model', { exact: true }).fill('gpt-5-nano');
	await dialog.getByRole('button', { name: 'Save', exact: true }).click();
	await expect(dialog.getByRole('button', { name: 'Saving...' })).toBeVisible();
	await page.keyboard.press('Escape');
	await page.getByRole('button', { name: 'Add', exact: true }).click();
	await dialog.getByLabel('Name', { exact: true }).fill('Second');
	const finished = page.waitForResponse(
		(response) =>
			response.url().endsWith('/api/llm/profiles') && response.request().method() === 'POST'
	);
	gate.release();
	await finished;
	await expect(dialog).toBeVisible();
	await expect(dialog.getByLabel('Name', { exact: true })).toHaveValue('Second');
	await expect(dialog.getByRole('button', { name: 'Save', exact: true })).toBeEnabled();
});

test('profile connection tests serialize their shared result state', async ({ page, api }) => {
	const gate = api.gate();
	api.on('GET', '/api/llm/profiles', () =>
		json({
			profiles: [
				{ name: 'One', model: 'gpt-5-nano', status: 'off' },
				{ name: 'Two', model: 'gpt-5-nano', status: 'off' },
			],
		})
	);
	api.on('POST', '/api/llm/profiles/One/test', async () => {
		await gate.promise;
		return json({ success: true, message: 'One connected' });
	});
	await page.goto('/settings');
	const tests = page.getByRole('button', { name: 'Test connection' });
	await tests.first().click();
	await expect(tests.first()).toBeDisabled();
	await expect(tests.nth(1)).toBeDisabled();
	gate.release();
	await expect(page.getByText('One connected')).toBeVisible();
	await expect(tests.nth(1)).toBeEnabled();
});

test('a pending location save prevents Escape from dismissing the editor', async ({
	page,
	api,
}) => {
	const gate = api.gate();
	api.on('POST', '/api/locations', async () => {
		await gate.promise;
		return json({ id: 'new-location', name: 'New room', description: '' });
	});
	await page.goto('/location');
	await page.getByRole('button', { name: 'Create New Location', exact: true }).click();
	const dialog = page.getByRole('dialog', { name: 'Create Location', exact: true });
	await dialog.getByLabel('Name').fill('New room');
	await dialog.getByRole('button', { name: 'Create Location', exact: true }).click();
	await expect(dialog.getByRole('button', { name: 'Saving...' })).toBeVisible();
	await page.keyboard.press('Escape');
	await expect(dialog).toBeVisible();
	await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeDisabled();
	gate.release();
	await expect(dialog).toBeHidden();
});

test('cancelled asset QR resolution cannot overwrite a later manual value', async ({
	page,
	api,
}) => {
	await page.addInitScript(() => {
		Object.defineProperty(window, 'BarcodeDetector', {
			configurable: true,
			value: class {
				static async getSupportedFormats() {
					return ['qr_code'];
				}
				async detect() {
					return [
						{
							rawValue: 'https://short.example/asset',
							cornerPoints: [
								{ x: 0, y: 0 },
								{ x: 1, y: 0 },
								{ x: 1, y: 1 },
								{ x: 0, y: 1 },
							],
						},
					];
				}
			},
		});
		navigator.mediaDevices.getUserMedia = async () => {
			throw new DOMException('Camera unavailable in test', 'NotAllowedError');
		};
	});
	const gate = api.gate();
	let resolving = false;
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Lamp'])));
	api.on('POST', '/api/qr/resolve', async () => {
		resolving = true;
		await gate.promise;
		return json({ resolved_url: 'https://homebox.example/a/obsolete' });
	});
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByRole('button', { name: 'Scan QR code', exact: true }).click();
	const photo = fileURLToPath(
		new URL('../../../tests/assets/multi_item_single_image.jpg', import.meta.url)
	);
	await page
		.getByRole('dialog', { name: 'Scan Asset ID QR Code' })
		.locator('input[type="file"]')
		.setInputFiles(photo);
	await expect.poll(() => resolving).toBe(true);
	const cancelled = page.waitForEvent(
		'requestfailed',
		(request) => new URL(request.url()).pathname === '/api/qr/resolve'
	);
	await page.getByRole('button', { name: 'Close scanner' }).click();
	await cancelled;
	await page.getByLabel('Asset ID', { exact: true }).fill('manual');
	gate.release();
	await expect(page.getByLabel('Asset ID', { exact: true })).toHaveValue('manual');
	await expect(page.getByRole('button', { name: 'Confirm', exact: true })).toBeEnabled();
});
