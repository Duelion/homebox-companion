import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { location } from './fixtures/data';

declare global {
	interface Window {
		__pickerUrls: { created: string[]; revoked: string[] };
		__pickerBlobStarted: boolean;
		__releasePickerBlob: () => void;
	}
}

type PickerItem = { id: string; name: string; quantity: number; thumbnailId?: string };

const items: PickerItem[] = [
	{ id: 'item-1', name: 'Blue storage box', quantity: 1, thumbnailId: 'thumb-1' },
	{ id: 'item-2', name: 'Red storage box', quantity: 1, thumbnailId: 'thumb-2' },
];

async function openPicker(page: import('@playwright/test').Page) {
	await page.goto('/location');
	await page.getByRole('button', { name: /Storage/ }).click();
	await page.getByRole('button', { name: 'Select current location' }).click();
	await page.getByRole('button', { name: /Place Inside an Item|Inside:/ }).click();
	await expect(page.getByRole('heading', { name: 'Select Container Item' })).toBeVisible();
}

function trackObjectUrls(page: import('@playwright/test').Page) {
	return page.addInitScript(() => {
		const created: string[] = [];
		const revoked: string[] = [];
		const originalCreate = URL.createObjectURL.bind(URL);
		const originalRevoke = URL.revokeObjectURL.bind(URL);
		URL.createObjectURL = (object) => {
			const url = originalCreate(object);
			created.push(url);
			return url;
		};
		URL.revokeObjectURL = (url) => {
			revoked.push(url);
			originalRevoke(url);
		};
		Object.assign(window, { __pickerUrls: { created, revoked } });
	});
}

async function prepareApi(
	api: import('./fixtures/api').MockApi,
	itemsResponse: PickerItem[] = items
) {
	api.on('GET', '/api/locations/tree', () =>
		json([{ ...location(), itemCount: itemsResponse.length }])
	);
	api.on('GET', '/api/locations/loc-1', () =>
		json({ ...location(), itemCount: itemsResponse.length })
	);
	api.on('GET', '/api/items', () => json(itemsResponse));
	api.on('GET', /^\/api\/items\/[^/]+\/attachments\/[^/]+$/, () => ({
		status: 200,
		contentType: 'image/png',
		body: 'thumbnail-bytes',
	}));
}

test('closing before the item list returns prevents thumbnail requests', async ({ page, api }) => {
	const gate = api.gate();
	await prepareApi(api);
	api.on('GET', '/api/items', async () => {
		await gate.promise;
		return json(items);
	});
	const listSettled = page.waitForEvent(
		'requestfailed',
		(request) => new URL(request.url()).pathname === '/api/items'
	);
	await openPicker(page);
	await expect
		.poll(
			() =>
				api.requests.filter((request) => new URL(request.url()).pathname === '/api/items').length
		)
		.toBe(1);
	await page.getByRole('button', { name: 'Cancel' }).click();
	gate.release();
	await listSettled;
	await expect(page.getByRole('heading', { name: 'Select Container Item' })).toHaveCount(0);
	await expect
		.poll(() =>
			api.requests.filter((request) => /\/attachments\//.test(new URL(request.url()).pathname))
		)
		.toHaveLength(0);
});

test('closing after one thumbnail arrives revokes URLs already owned by the picker', async ({
	page,
	api,
}) => {
	await trackObjectUrls(page);
	const secondThumbnail = api.gate();
	await prepareApi(api);
	api.on('GET', '/api/items/item-2/attachments/thumb-2', async () => {
		await secondThumbnail.promise;
		return { status: 200, contentType: 'image/png', body: 'thumbnail-two' };
	});
	await openPicker(page);
	await expect.poll(() => page.evaluate(() => window.__pickerUrls.created.length)).toBe(1);
	await page.getByRole('button', { name: 'Cancel' }).click();
	await expect.poll(() => page.evaluate(() => window.__pickerUrls.revoked.length)).toBe(1);
	secondThumbnail.release();
});

test('a blob that resolves after disposal has its newly created URL revoked', async ({
	page,
	api,
}) => {
	await trackObjectUrls(page);
	await page.addInitScript(() => {
		const originalBlob = Response.prototype.blob;
		let release!: () => void;
		const gate = new Promise<void>((resolve) => (release = resolve));
		Object.assign(window, {
			__pickerBlobStarted: false,
			__releasePickerBlob: () => release(),
		});
		Response.prototype.blob = async function () {
			if (this.url.includes('/api/items/item-1/attachments/thumb-1')) {
				const blob = await originalBlob.call(this);
				window.__pickerBlobStarted = true;
				await gate;
				return blob;
			}
			return originalBlob.call(this);
		};
	});
	await prepareApi(api, [items[0]]);
	await openPicker(page);
	await expect.poll(() => page.evaluate(() => window.__pickerBlobStarted)).toBe(true);
	await page.getByRole('button', { name: 'Cancel' }).click();
	await page.evaluate(() => window.__releasePickerBlob());
	await expect.poll(() => page.evaluate(() => window.__pickerUrls.created.length)).toBe(1);
	await expect.poll(() => page.evaluate(() => window.__pickerUrls.revoked.length)).toBe(1);
});

async function verifyReopenKeepsSelection(
	page: import('@playwright/test').Page,
	api: import('./fixtures/api').MockApi
) {
	await prepareApi(api, [items[0]]);
	await openPicker(page);
	await page.getByRole('button', { name: /Blue storage box/ }).click();
	await expect(page.getByRole('button', { name: /Inside: Blue storage box/ })).toBeVisible();
	await page.getByRole('button', { name: /Inside: Blue storage box/ }).click();
	await expect(page.locator('.selectable-item-selected')).toContainText('Blue storage box');
	await page.getByRole('button', { name: 'Cancel' }).click();
	expect(
		api.requests.filter((request) => new URL(request.url()).pathname === '/api/items')
	).toHaveLength(2);
}

test('reopening the picker reloads items and retains the selected container', async ({
	page,
	api,
}) => {
	await verifyReopenKeepsSelection(page, api);
});

test('reopening the picker reloads items and retains the selected container @mobile', async ({
	page,
	api,
}) => {
	await verifyReopenKeepsSelection(page, api);
});
