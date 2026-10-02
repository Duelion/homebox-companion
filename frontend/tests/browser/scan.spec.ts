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
