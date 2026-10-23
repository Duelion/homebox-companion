import { expect, test } from './fixtures/test';
import type { Page } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { json } from './fixtures/api';
import { createdItem, detectedItems } from './fixtures/data';
import { analyzePhotos, selectLocation, uploadPhoto } from './helpers/scan';
import { readDrafts } from './helpers/recovery';

async function saved(page: Page) {
	await expect(
		page.getByRole('status', { name: '', exact: true }).filter({ hasText: /^Saved$/ })
	).toBeVisible();
}
async function resume(page: Page) {
	await page.reload();
	await expect(page).toHaveURL(/\/location$/);
	await page.getByRole('button', { name: 'Resume Session' }).click();
	await expect(page).toHaveURL(/\/review$/);
}

test('unconfirmed rich edits and ordered replacement photos recover, including summary editing', async ({
	page,
	api,
}) => {
	api.allowPageError(/navigation aborted/);
	api.on('GET', '/api/tags', () => json([{ id: 'chosen', name: 'Chosen' }]));
	api.on('POST', '/api/tools/vision/detect', () =>
		json({ items: [{ name: 'Original', quantity: 1, custom_fields: { Material: 'Wood' } }] })
	);
	const creations: unknown[] = [];
	api.on('POST', '/api/items', (request) => {
		creations.push(request.postDataJSON());
		return json(createdItem('saved'));
	});
	api.on('PUT', '/api/items/saved', () => json({}));
	const uploads: string[] = [];
	api.on('POST', '/api/items/saved/attachments', (request) => {
		uploads.push(request.postDataBuffer()?.toString('base64') ?? '');
		return json({});
	});
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByLabel('Name', { exact: true }).fill('Recovered 名称');
	await page.getByLabel('Quantity', { exact: true }).fill('7');
	await page.getByLabel('Description', { exact: true }).fill('Description — edited');
	await page.getByLabel('Asset ID', { exact: true }).fill('123-456');
	await page.getByRole('button', { name: 'Chosen', exact: true }).click();
	await page.getByRole('button', { name: 'Extended Fields', exact: true }).click();
	for (const [label, value] of Object.entries({
		Manufacturer: 'Maker',
		'Model Number': 'Model',
		'Serial Number': 'Serial',
		'Purchase Price': '12.34',
		'Purchased From': 'Shop',
		Notes: '日本語 — notes',
	})) {
		await page.getByLabel(label, { exact: true }).fill(value);
	}
	await page.getByRole('button', { name: /Custom Fields/ }).click();
	await page.getByLabel('Material', { exact: true }).fill('Steel — 紫');
	await page.getByRole('button', { name: /Attached Photos/ }).click();
	await page.getByRole('button', { name: 'Remove image', exact: true }).click();
	const photo = fileURLToPath(
		new URL('../../../tests/assets/multi_item_single_image.jpg', import.meta.url)
	);
	await page.locator('input[type="file"]').first().setInputFiles([photo, photo]);
	await expect(page.getByText('2 photos', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Edit thumbnail image', exact: true }).click();
	await page.getByRole('button', { name: 'Rotate 90° right', exact: true }).click();
	await page.getByRole('button', { name: 'Save Thumbnail', exact: true }).click();
	await saved(page);
	const stored = (await readDrafts(page, 'deployment:user:g1'))[0];
	expect(stored.confirmedItems).toEqual([]);
	expect(stored.activeReviewDraft).toMatchObject({
		name: 'Recovered 名称',
		quantity: 7,
		custom_fields: { Material: 'Steel — 紫' },
		photos: [expect.anything(), expect.anything()],
	});
	await resume(page);
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Recovered 名称');
	await expect(page.getByLabel('Quantity', { exact: true })).toHaveValue('7');
	await expect(page.getByLabel('Description', { exact: true })).toHaveValue('Description — edited');
	await expect(page.getByLabel('Asset ID', { exact: true })).toHaveValue('123-456');
	expect((await readDrafts(page, 'deployment:user:g1'))[0].activeReviewDraft).toMatchObject({
		customThumbnail: expect.stringMatching(/^data:image/),
		thumbnailTransform: expect.objectContaining({ rotation: 90 }),
	});
	await expect(page.getByRole('button', { name: 'Chosen', exact: true })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	await expect(page.getByLabel('Manufacturer', { exact: true })).toHaveValue('Maker');
	await expect(page.getByLabel('Notes', { exact: true })).toHaveValue('日本語 — notes');
	await page.getByRole('button', { name: /Custom Fields/ }).click();
	await expect(page.getByLabel('Material', { exact: true })).toHaveValue('Steel — 紫');
	await page.getByRole('button', { name: /Attached Photos/ }).click();
	await expect(page.getByText('2 photos', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page).toHaveURL(/\/summary$/);
	await page.getByRole('button', { name: 'Edit item', exact: true }).click();
	await page.getByLabel('Name', { exact: true }).fill('Summary recovered');
	await saved(page);
	await resume(page);
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Summary recovered');
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page).toHaveURL(/\/summary$/);
	await page.getByRole('button', { name: /Submit All Items/ }).click();
	await expect(page).toHaveURL(/\/success$/);
	expect(creations).toEqual([
		expect.objectContaining({
			items: [
				expect.objectContaining({
					name: 'Summary recovered',
					quantity: 7,
					description: 'Description — edited',
					manufacturer: 'Maker',
					model_number: 'Model',
					serial_number: 'Serial',
					purchase_price: 12.34,
					purchase_from: 'Shop',
					notes: '日本語 — notes',
					tag_ids: ['chosen'],
					custom_fields: { Material: 'Steel — 紫' },
				}),
			],
		}),
	]);
	expect(uploads).toHaveLength(2);
	const payload = JSON.stringify(creations);
	for (const internal of ['reviewId', 'activeReviewDraft', 'photos', 'sourceImageIndex'])
		expect(payload).not.toContain(`"${internal}"`);
});

test('multiple detections from one photo keep distinct drafts and correction survives recovery', async ({
	page,
	api,
}) => {
	api.allowPageError(/navigation aborted/);
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['First', 'Second'])));
	api.on('POST', '/api/tools/vision/correct', () => json(detectedItems(['Corrected second'])));
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByLabel('Name', { exact: true }).fill('First edited');
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Second');
	await page.getByRole('button', { name: 'AI Correction', exact: true }).click();
	await page.getByPlaceholder(/The brand is Sony/).fill('Correct');
	await page.getByRole('button', { name: 'Correct with AI', exact: true }).click();
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Corrected second');
	await page.getByRole('link', { name: 'Settings', exact: true }).click();
	await page.goBack();
	await expect(page).toHaveURL(/\/review$/);
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Corrected second');
	await saved(page);
	const stored = (await readDrafts(page, 'deployment:user:g1'))[0];
	const items = stored.detectedItems as Array<{ reviewId: string }>;
	expect(items[0].reviewId).not.toEqual(items[1].reviewId);
	await resume(page);
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Corrected second');
	await page.getByRole('button', { name: 'Skip', exact: true }).click();
	await expect(page).toHaveURL(/\/summary$/);
	expect((await readDrafts(page, 'deployment:user:g1'))[0].activeReviewDraft).toBeUndefined();
});

test('failed storage reports an unsaved draft and retry reaches a completed checkpoint', async ({
	page,
	api,
}) => {
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Lamp'])));
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await saved(page);
	await page.evaluate(() => {
		const original = IDBObjectStore.prototype.put;
		Object.assign(window, {
			restoreDraftStorage: () => {
				IDBObjectStore.prototype.put = original;
			},
		});
		IDBObjectStore.prototype.put = function () {
			throw new DOMException('Test quota exhausted', 'QuotaExceededError');
		};
	});
	await page.getByLabel('Name', { exact: true }).fill('Unsaved draft');
	await expect(
		page.getByText('Unable to save. Keep this page open and retry.', { exact: true })
	).toBeVisible();
	await page.evaluate(() =>
		(window as unknown as { restoreDraftStorage: () => void }).restoreDraftStorage()
	);
	await page.getByRole('button', { name: 'Retry save', exact: true }).click();
	await saved(page);
	expect((await readDrafts(page, 'deployment:user:g1'))[0].activeReviewDraft).toMatchObject({
		name: 'Unsaved draft',
	});
});

test('Start Fresh removes the unconfirmed overlay without resurrecting it after reload', async ({
	page,
	api,
}) => {
	api.allowPageError(/navigation aborted/);
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Original'])));
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByLabel('Name', { exact: true }).fill('Unconfirmed work');
	await saved(page);
	await page.reload();
	await expect(page).toHaveURL(/\/location$/);
	await page.getByRole('button', { name: 'Start Fresh', exact: true }).click();
	await expect.poll(async () => readDrafts(page, 'deployment:user:g1')).toEqual([]);
	await page.reload();
	await expect(page.getByRole('button', { name: 'Resume Session', exact: true })).toHaveCount(0);
});

test('collection switching drops access to the active draft and rejects its late correction', async ({
	page,
	api,
}) => {
	api.allowPageError(/navigation aborted/);
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Original'])));
	const gate = api.gate();
	let correcting = false;
	api.on('POST', '/api/tools/vision/correct', async () => {
		correcting = true;
		await gate.promise;
		return json(detectedItems(['Obsolete correction']));
	});
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByLabel('Name', { exact: true }).fill('Personal unconfirmed');
	await saved(page);
	await page.getByRole('button', { name: 'AI Correction', exact: true }).click();
	await page.getByPlaceholder(/The brand is Sony/).fill('Delayed correction');
	await page.getByRole('button', { name: 'Correct with AI', exact: true }).click();
	await expect.poll(() => correcting).toBe(true);
	await page.getByRole('button', { name: /Personal/ }).click();
	await page.getByRole('option', { name: /Shared/ }).click();
	gate.release();
	await expect(page.getByLabel('Name', { exact: true })).toHaveCount(0);
	await page.getByRole('link', { name: 'Scan', exact: true }).click();
	await expect(page).toHaveURL(/\/location$/);
	await expect(page.getByRole('button', { name: 'Resume Session', exact: true })).toHaveCount(0);
	expect((await readDrafts(page, 'deployment:user:g1'))[0].activeReviewDraft).toMatchObject({
		name: 'Personal unconfirmed',
	});
	expect(await readDrafts(page, 'deployment:user:g2')).toEqual([]);
});
