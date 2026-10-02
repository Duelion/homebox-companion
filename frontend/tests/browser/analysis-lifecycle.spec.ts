import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { detectedItems, fieldPreferences } from './fixtures/data';
import { readDrafts } from './helpers/recovery';
import { selectLocation, uploadPhoto } from './helpers/scan';

const detectPath = '/api/tools/vision/detect';

async function beginScan(page: Parameters<typeof selectLocation>[0]) {
	await selectLocation(page);
	await uploadPhoto(page);
}

test('cancel while preferences load prevents detection and allows a fresh analysis', async ({
	page,
	api,
}) => {
	const preferenceGate = api.gate();
	let preferenceRequests = 0;
	api.on('GET', '/api/settings/field-preferences', async () => {
		preferenceRequests++;
		if (preferenceRequests === 1) await preferenceGate.promise;
		return json(fieldPreferences());
	});
	api.on('POST', detectPath, () => json(detectedItems(['Fresh item'])));

	await beginScan(page);
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await expect.poll(() => preferenceRequests).toBe(1);
	const oldPreferencesFailed = page.waitForEvent(
		'requestfailed',
		(request) => new URL(request.url()).pathname === '/api/settings/field-preferences'
	);
	await page.getByRole('button', { name: 'Cancel Analysis' }).click();
	await oldPreferencesFailed;
	await expect(page.getByRole('button', { name: /Analyze with AI/ })).toBeEnabled();
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await expect(page).toHaveURL(/\/review$/);
	preferenceGate.release();
	await expect(page.getByLabel('Name')).toHaveValue('Fresh item');
	expect(
		api.requests.filter((request) => new URL(request.url()).pathname === detectPath)
	).toHaveLength(1);
});

test('cancel during detection ignores the obsolete response and keeps the new run active', async ({
	page,
	api,
}) => {
	const firstDetectGate = api.gate();
	const secondDetectGate = api.gate();
	let detectionRequests = 0;
	api.on('POST', detectPath, async () => {
		detectionRequests++;
		if (detectionRequests === 1) {
			await firstDetectGate.promise;
			return json(detectedItems(['Obsolete item']));
		}
		await secondDetectGate.promise;
		return json(detectedItems(['Current item']));
	});

	await beginScan(page);
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await expect.poll(() => detectionRequests).toBe(1);
	await page.getByRole('button', { name: 'Cancel Analysis' }).click();
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await expect.poll(() => detectionRequests).toBe(2);
	firstDetectGate.release();
	await expect(page.getByRole('button', { name: 'Cancel Analysis' })).toBeVisible();
	secondDetectGate.release();
	await expect(page).toHaveURL(/\/review$/);
	await expect(page.getByLabel('Name')).toHaveValue('Current item');
});

test('an old run settling during tag loading cannot clear a newer controller', async ({
	page,
	api,
}) => {
	const tagsGate = api.gate();
	const secondDetectGate = api.gate();
	let detectionRequests = 0;
	let tagRequests = 0;
	api.on('GET', '/api/tags', async () => {
		tagRequests++;
		await tagsGate.promise;
		return json([]);
	});
	api.on('POST', detectPath, async () => {
		detectionRequests++;
		if (detectionRequests === 2) await secondDetectGate.promise;
		return json(detectedItems([detectionRequests === 1 ? 'Old item' : 'New item']));
	});

	await beginScan(page);
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await expect.poll(() => tagRequests).toBe(1);
	await expect.poll(() => detectionRequests).toBe(1);
	await expect(page.getByText('1 / 1')).toBeVisible();
	await page.getByRole('button', { name: 'Cancel Analysis' }).click();
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await expect.poll(() => detectionRequests).toBe(2);
	const tagsFinished = page.waitForEvent(
		'requestfinished',
		(request) => new URL(request.url()).pathname === '/api/tags'
	);
	tagsGate.release();
	await tagsFinished;
	await page.evaluate(() => Promise.resolve());
	await expect(page.getByRole('button', { name: 'Cancel Analysis' })).toBeVisible();
	const secondDetectFailed = page.waitForEvent(
		'requestfailed',
		(request) => new URL(request.url()).pathname === detectPath
	);
	await page.getByRole('button', { name: 'Cancel Analysis' }).click();
	await secondDetectFailed;
	secondDetectGate.release();
	await expect(page.getByRole('button', { name: /Analyze with AI/ })).toBeEnabled();
	await expect(page).not.toHaveURL(/\/review$/);
});

test('cancelled retry retains failed images and can be retried again', async ({ page, api }) => {
	const retryGate = api.gate();
	let detectionRequests = 0;
	api.on('POST', detectPath, async () => {
		detectionRequests++;
		if (detectionRequests === 1) return json(detectedItems(['Saved item']));
		if (detectionRequests === 2) return json({ detail: 'Detection failed' }, 500);
		if (detectionRequests === 3) await retryGate.promise;
		return json(detectedItems(['Retried item']));
	});

	await beginScan(page);
	await uploadPhoto(page);
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await expect(page.getByRole('button', { name: 'Retry Failed Images' })).toBeVisible();
	await page.getByRole('button', { name: 'Retry Failed Images' }).click();
	await expect.poll(() => detectionRequests).toBe(3);
	await page.getByRole('button', { name: 'Cancel Analysis' }).click();
	await expect(page.getByRole('button', { name: 'Retry Failed Images' })).toBeVisible();
	retryGate.release();
	await page.getByRole('button', { name: 'Retry Failed Images' }).click();
	await expect(page).toHaveURL(/\/review$/);
	await expect(page.getByLabel('Name')).toHaveValue('Saved item');
	expect(detectionRequests).toBe(4);
});

test('switching collection invalidates a pending analysis and its draft', async ({ page, api }) => {
	const detectGate = api.gate();
	let detectionRequests = 0;
	api.on('POST', detectPath, async () => {
		detectionRequests++;
		await detectGate.promise;
		return json(detectedItems(['Old collection item']));
	});

	await beginScan(page);
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await expect.poll(() => detectionRequests).toBe(1);
	await page.getByRole('button', { name: /Personal/ }).click();
	await page.getByRole('option', { name: /Shared/ }).click();
	detectGate.release();
	await expect(page.getByRole('button', { name: /Shared/ })).toBeVisible();
	await expect(page).not.toHaveURL(/\/review$/);
	await expect.poll(async () => readDrafts(page, 'deployment:user:g2')).toEqual([]);
});
