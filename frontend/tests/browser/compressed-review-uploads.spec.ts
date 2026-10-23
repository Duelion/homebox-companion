import type { Page, Request } from '@playwright/test';
import { test, expect } from './fixtures/test';
import { json, type MockApi } from './fixtures/api';
import { createdItem, detectedItems } from './fixtures/data';
import { selectLocation, uploadPhoto, analyzePhotos, submitItems } from './helpers/scan';

const compressedPrimary = 'SERVER_COMPRESSED_PRIMARY_BYTES_49';
const compressedPrimaryBase64 = Buffer.from(compressedPrimary).toString('base64');

async function beginReview(page: Page, itemNames: string[]) {
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue(itemNames[0]);
}

async function confirmAllRemaining(page: Page) {
	const confirm = page.getByRole('button', { name: 'Confirm', exact: true });
	await confirm.focus();
	await confirm.hover();
	await page.mouse.down();
	try {
		const dialog = page.getByRole('dialog', { name: 'Confirm All Remaining Items' });
		await expect(dialog).toBeVisible();
		await dialog.getByRole('button', { name: 'Confirm All', exact: true }).click();
	} finally {
		await page.mouse.up();
	}
}

function installCompressedDetection(api: MockApi, names: string[]) {
	api.on('POST', '/api/tools/vision/detect', () =>
		json({
			...detectedItems(names),
			compressed_images: [{ data: compressedPrimaryBase64, mime_type: 'image/jpeg' }],
		})
	);
}

function assertCompressedPayloads(uploads: Request[], expectedCount: number) {
	expect(uploads).toHaveLength(expectedCount);
	for (const upload of uploads) {
		expect(upload.postDataBuffer()?.includes(Buffer.from(compressedPrimary))).toBe(true);
	}
}

test('ordinary confirmation submits the server-compressed primary image', async ({ page, api }) => {
	const uploads: Request[] = [];
	installCompressedDetection(api, ['Desk lamp']);
	api.on('POST', '/api/items', () => json(createdItem('lamp-1', 'Edited desk lamp')));
	api.on('POST', '/api/items/lamp-1/attachments', (request) => {
		uploads.push(request);
		return json({});
	});

	await beginReview(page, ['Desk lamp']);
	await page.getByLabel('Name', { exact: true }).fill('Edited desk lamp');
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page).toHaveURL(/\/summary$/);
	await submitItems(page);
	await expect(page).toHaveURL(/\/success$/);

	assertCompressedPayloads(uploads, 1);
});

test('confirm-all submits the current edited item with its server-compressed image', async ({
	page,
	api,
}) => {
	const uploads: Request[] = [];
	const submittedNames: string[] = [];
	installCompressedDetection(api, ['Desk tools', 'Storage box']);
	api.on('POST', '/api/items', (request) => {
		const name = request.postDataJSON().items[0].name as string;
		submittedNames.push(name);
		return json(createdItem(`item-${submittedNames.length}`, name));
	});
	api.on('POST', /^\/api\/items\/item-\d+\/attachments$/, (request) => {
		uploads.push(request);
		return json({});
	});

	await beginReview(page, ['Desk tools', 'Storage box']);
	await page.getByLabel('Name', { exact: true }).fill('Edited desk tools');
	await confirmAllRemaining(page);
	await expect(page).toHaveURL(/\/summary$/);
	await submitItems(page);
	await expect(page).toHaveURL(/\/success$/);

	expect(submittedNames).toEqual(['Edited desk tools', 'Storage box']);
	assertCompressedPayloads(uploads, 2);
});
