import type { Page, Request } from '@playwright/test';
import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { createdItem, detectedItems } from './fixtures/data';
import { readDrafts } from './helpers/recovery';
import { analyzePhotos, selectLocation, uploadPhoto } from './helpers/scan';

async function readStoredSession(page: Page) {
	const drafts = await readDrafts(page, 'deployment:user:g1');
	return drafts[0] ?? null;
}

async function createConfirmedScan(page: Page, itemName: string, manufacturer?: string) {
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByLabel('Name').fill(itemName);
	if (manufacturer) {
		await page.getByRole('button', { name: 'Extended Fields' }).click();
		await page.getByLabel('Manufacturer').fill(manufacturer);
	}
	await page.getByRole('button', { name: 'Confirm' }).click();
	await expect(page).toHaveURL(/\/summary$/);
}

test('reediting a confirmed item preserves its asset ID and edited custom fields through submission', async ({
	page,
	api,
}) => {
	const creations: unknown[] = [];
	const updates: unknown[] = [];
	api.on('POST', '/api/tools/vision/detect', () =>
		json({
			...detectedItems(['Desk lamp']),
			items: [{ name: 'Desk lamp', quantity: 1, custom_fields: { Warranty: 'One year' } }],
		})
	);
	api.on('POST', '/api/items', (request) => {
		creations.push(request.postDataJSON());
		return json(createdItem('lamp-1'));
	});
	api.on('POST', '/api/items/lamp-1/attachments', () => json({}));
	api.on('PUT', '/api/items/lamp-1', (request) => {
		updates.push(request.postDataJSON());
		return json({});
	});

	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByLabel('Asset ID', { exact: true }).fill('000-042');
	await page.getByLabel('Warranty', { exact: true }).fill('Two years');
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page).toHaveURL(/\/summary$/);
	await page.getByRole('button', { name: 'Edit item', exact: true }).click();
	await expect(page.getByLabel('Asset ID', { exact: true })).toHaveValue('000-042');
	await expect(page.getByLabel('Warranty', { exact: true })).toHaveValue('Two years');
	await page.getByLabel('Name', { exact: true }).fill('Edited desk lamp');
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await page.getByRole('button', { name: /Submit All Items/ }).click();
	await expect(page).toHaveURL(/\/success$/);
	expect(creations).toEqual([
		expect.objectContaining({
			items: [
				expect.objectContaining({
					name: 'Edited desk lamp',
					custom_fields: { Warranty: 'Two years' },
				}),
			],
		}),
	]);
	expect(updates).toEqual([{ assetId: '000-042' }]);
});

test('submits a corrected item to the selected location with its photo', async ({ page, api }) => {
	const creations: unknown[] = [];
	const uploads: Request[] = [];
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Unlabeled lamp'])));
	api.on('POST', '/api/items', (request) => {
		creations.push(request.postDataJSON());
		return json(createdItem('lamp-1'));
	});
	api.on('POST', '/api/items/lamp-1/attachments', (request) => {
		uploads.push(request);
		return json({});
	});

	await createConfirmedScan(page, 'Desk lamp', 'Lumina');
	await page.getByRole('button', { name: /Submit All Items/ }).click();

	await expect(page).toHaveURL(/\/success$/);
	await expect(page.getByRole('heading', { name: 'Success!' })).toBeVisible();
	await expect(page.getByText('1 item added to Storage')).toBeVisible();
	expect(creations).toEqual([
		{
			location_id: 'loc-1',
			items: [
				expect.objectContaining({
					name: 'Desk lamp',
					manufacturer: 'Lumina',
				}),
			],
		},
	]);
	expect(uploads).toHaveLength(1);
	expect(uploads[0].headers()['content-type']).toContain('multipart/form-data');
	expect(uploads[0].postDataBuffer()?.byteLength).toBeGreaterThan(0);
});

test('reload recovers a UI-created scan and its confirmed edits', async ({ page, api }) => {
	api.allowPageError(/navigation aborted/);
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Unlabeled camera'])));

	await createConfirmedScan(page, 'Recovered camera', 'Acme Optics');
	await expect
		.poll(async () => readStoredSession(page))
		.toMatchObject({
			confirmedItems: [
				expect.objectContaining({ name: 'Recovered camera', manufacturer: 'Acme Optics' }),
			],
		});

	await page.reload();
	await expect(page).toHaveURL(/\/location$/);
	await page.getByRole('button', { name: 'Resume Session' }).click();
	await expect(page).toHaveURL(/\/summary$/);
	await expect(page.getByText('Recovered camera', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Edit item' }).click();
	await expect(page.getByLabel('Manufacturer')).toHaveValue('Acme Optics');
});

test('Start Fresh clears the persisted scan created through the UI', async ({ page, api }) => {
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Draft radio'])));

	await createConfirmedScan(page, 'Draft radio');
	await expect.poll(async () => readStoredSession(page)).not.toBeNull();

	await page.reload();
	await expect(page).toHaveURL(/\/location$/);
	await page.getByRole('button', { name: 'Start Fresh' }).click();
	await expect.poll(async () => readStoredSession(page)).toBeNull();

	await page.reload();
	await expect(page).toHaveURL(/\/location$/);
	await expect(page.getByRole('button', { name: 'Resume Session' })).toHaveCount(0);
});
