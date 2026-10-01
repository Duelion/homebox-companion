import type { Page, Request } from '@playwright/test';
import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { createdItem, detectedItems } from './fixtures/data';
import { analyzePhotos, selectLocation, uploadPhoto } from './helpers/scan';

type StoredSession = {
	confirmedItems?: Array<{ name: string; manufacturer?: string | null }>;
};

async function readStoredSession(page: Page): Promise<StoredSession | null> {
	return page.evaluate(
		() =>
			new Promise<StoredSession | null>((resolve, reject) => {
				const open = indexedDB.open('hbc-scan-recovery');
				open.onerror = () => reject(open.error ?? new Error('Could not open recovery database'));
				open.onblocked = () => reject(new Error('Recovery database is blocked'));
				open.onsuccess = () => {
					const database = open.result;
					try {
						const transaction = database.transaction('sessions', 'readonly');
						const request = transaction.objectStore('sessions').get('deployment:user:g1');
						let session: StoredSession | null = null;
						let readError: DOMException | Error | null = null;
						request.onsuccess = () => {
							session = request.result ?? null;
						};
						request.onerror = () => {
							readError = request.error ?? new Error('Could not read recovery session');
						};
						transaction.oncomplete = () => {
							database.close();
							if (readError) reject(readError);
							else resolve(session);
						};
						transaction.onerror = () => {
							database.close();
							reject(transaction.error ?? new Error('Recovery session transaction failed'));
						};
						transaction.onabort = () => {
							database.close();
							reject(transaction.error ?? new Error('Recovery session transaction was aborted'));
						};
					} catch (error) {
						database.close();
						reject(error);
					}
				};
			})
	);
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
