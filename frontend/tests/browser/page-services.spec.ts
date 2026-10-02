import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { detectedItems, location } from './fixtures/data';
import { selectLocation, uploadPhoto, analyzePhotos } from './helpers/scan';

test('leaving review cancels a pending correction and preserves the next editor', async ({
	page,
	api,
}) => {
	const gate = api.gate();
	let corrections = 0;
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Lamp'])));
	api.on('POST', '/api/tools/vision/correct', async () => {
		corrections++;
		await gate.promise;
		return json({ items: [{ name: 'Obsolete correction', quantity: 1 }], message: 'Corrected' });
	});
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByRole('button', { name: 'AI Correction', exact: true }).click();
	await page.getByPlaceholder(/The brand is Sony/).fill('Correct the model');
	await page.getByRole('button', { name: 'Correct with AI', exact: true }).click();
	await expect.poll(() => corrections).toBe(1);
	const cancelled = page.waitForEvent(
		'requestfailed',
		(request) => new URL(request.url()).pathname === '/api/tools/vision/correct'
	);
	await page.locator('a[href="/settings"]:visible').click();
	await cancelled;
	await expect(page).toHaveURL(/\/settings$/);
	await page.locator('a[href="/review"]:visible').click();
	await expect(page).toHaveURL(/\/review$/);
	await page.getByLabel('Name', { exact: true }).fill('Fresh draft');
	gate.release();
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Fresh draft');
	await expect(page.getByRole('button', { name: 'Confirm', exact: true })).toBeEnabled();
});

test('AI correction applies extended fields and keeps the review photo', async ({ page, api }) => {
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Lamp'])));
	api.on('POST', '/api/tools/vision/correct', () =>
		json({
			items: [
				{
					name: 'Desk lamp',
					quantity: 2,
					description: 'Corrected',
					manufacturer: 'Acme',
					model_number: 'L2',
					serial_number: 'S2',
					purchase_price: 12,
					purchase_from: 'Shop',
					notes: 'Working',
				},
			],
			message: 'Corrected',
		})
	);
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByRole('button', { name: 'AI Correction', exact: true }).click();
	await page.getByPlaceholder(/The brand is Sony/).fill('Correct the model');
	await page.getByRole('button', { name: 'Correct with AI', exact: true }).click();
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Desk lamp');
	await expect(page.getByLabel('Quantity', { exact: true })).toHaveValue('2');
	await expect(page.getByRole('img', { name: 'Desk lamp', exact: true })).toBeVisible();
	await page.getByRole('button', { name: /Extended Fields/ }).click();
	for (const [label, value] of [
		['Manufacturer', 'Acme'],
		['Model Number', 'L2'],
		['Serial Number', 'S2'],
		['Purchase Price', '12'],
		['Purchased From', 'Shop'],
		['Notes', 'Working'],
	]) {
		await expect(page.getByLabel(label, { exact: true })).toHaveValue(value);
	}
});

test('creating a nested location updates browsing and searchable hierarchy', async ({
	page,
	api,
}) => {
	let created = false;
	const child = location('loc-2', 'Drawer');
	const parent = () => ({ ...location(), children: created ? [child] : [] });
	api.on('GET', '/api/locations/tree', () => json([parent()]));
	api.on('GET', '/api/locations/loc-1', () => json(parent()));
	api.on('POST', '/api/locations', (request) => {
		expect(request.postDataJSON()).toMatchObject({ name: 'Drawer', parent_id: 'loc-1' });
		created = true;
		return json(child);
	});
	await page.goto('/location');
	await page.getByRole('button', { name: /Storage/ }).click();
	await page.getByRole('button', { name: 'Create Location in Storage' }).click();
	const dialog = page.getByRole('dialog', { name: 'Create Location' });
	await dialog.getByRole('textbox', { name: /^Name/ }).fill('Drawer');
	await dialog.getByRole('button', { name: /Create/ }).click();
	await expect(dialog).toBeHidden();
	await expect(page.getByRole('button', { name: /Drawer/ })).toBeVisible();
	await page.getByPlaceholder('Search all locations...').fill('Drawer');
	await expect(page.getByRole('button', { name: /Storage.*Drawer/ })).toBeVisible();
});

test('renaming a selected location synchronizes breadcrumbs and subsequent selection', async ({
	page,
	api,
}) => {
	let name = 'Storage';
	api.on('GET', '/api/locations/tree', () => json([location('loc-1', name)]));
	api.on('GET', '/api/locations/loc-1', () => json(location('loc-1', name)));
	api.on('PUT', '/api/locations/loc-1', (request) => {
		name = request.postDataJSON().name;
		return json(location('loc-1', name));
	});
	await page.goto('/location');
	await page.getByRole('button', { name: /Storage/ }).click();
	await page.getByRole('button', { name: 'Select current location' }).click();
	await page.getByRole('button', { name: 'Edit location' }).click();
	const dialog = page.getByRole('dialog', { name: 'Edit Location' });
	await dialog.getByRole('textbox', { name: /^Name/ }).fill('Workshop');
	await dialog.getByRole('button', { name: /Save/ }).click();
	await expect(dialog).toBeHidden();
	await expect(page.getByText('Workshop', { exact: true })).toBeVisible();
	await expect(page.getByText('Storage', { exact: true })).toHaveCount(0);
	await page.getByRole('link', { name: 'Choose a different location' }).click();
	await expect(page.getByRole('button', { name: 'Create Location in Workshop' })).toBeVisible();
});
