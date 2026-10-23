import { expect, test } from './fixtures/test';
import { json } from './fixtures/api';
import { selectLocation, uploadPhoto, analyzePhotos } from './helpers/scan';
import { readDrafts } from './helpers/recovery';

test('Back and Forward preserve the original review entry, rich draft, and confirmed items', async ({
	page,
	api,
}) => {
	api.on('POST', '/api/tools/vision/detect', () =>
		json({
			items: [
				{ name: 'First item', quantity: 1, custom_fields: { Material: 'Wood' } },
				{ name: 'Second item', quantity: 1, custom_fields: { Material: 'Wood' } },
			],
		})
	);
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Second item');
	await page.getByLabel('Name', { exact: true }).fill('Saved second item');
	await page.getByLabel('Quantity', { exact: true }).fill('3');
	await expect(page.getByLabel('Quantity', { exact: true })).toHaveValue('3');
	// Populated custom fields are already expanded when this item is opened.
	await expect(page.getByLabel('Material', { exact: true })).toBeVisible();
	await page.getByLabel('Material', { exact: true }).fill('Steel');
	await expect(page.getByLabel('Material', { exact: true })).toHaveValue('Steel');
	await expect(page.getByLabel('Quantity', { exact: true })).toHaveValue('3');
	await page.getByRole('button', { name: 'Edit thumbnail image', exact: true }).click();
	const dialog = page.getByRole('dialog', { name: 'Edit Thumbnail', exact: true });
	await expect(dialog.getByRole('button', { name: 'Save Thumbnail' })).toBeEnabled();
	await dialog.getByRole('button', { name: 'Rotate 90° right' }).click();
	await dialog.getByRole('button', { name: 'Save Thumbnail' }).click();
	await expect(page.getByLabel('Quantity', { exact: true })).toHaveValue('3');
	await expect(page.getByRole('status').filter({ hasText: /^Saved$/ })).toBeVisible();
	const before = (await readDrafts(page, 'deployment:user:g1'))[0];
	expect(before.currentReviewIndex).toBe(1);
	expect(before.confirmedItems).toHaveLength(1);
	expect(before.activeReviewDraft).toMatchObject({
		quantity: 3,
		custom_fields: { Material: 'Steel' },
	});
	const historyLength = await page.evaluate(() => history.length);
	for (let visit = 0; visit < 2; visit++) {
		await page.goBack();
		await expect(page).toHaveURL(/\/capture$/);
		await expect(page.getByRole('button', { name: 'Return to Review', exact: true })).toBeVisible();
		await expect(page.getByRole('img', { name: 'Captured 1', exact: true })).toBeVisible();
		for (const name of [
			'Change location',
			'Remove image',
			'Expand options',
			'Analyze with AI',
			'Retry Failed Images',
		]) {
			await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0);
		}
		await expect(page.locator('main input, main textarea, main select')).toHaveCount(0);
		await expect(page.getByText('Analysis complete!', { exact: true })).toHaveCount(0);
		const during = (await readDrafts(page, 'deployment:user:g1'))[0];
		for (const key of [
			'status',
			'currentReviewIndex',
			'detectedItems',
			'confirmedItems',
			'activeReviewDraft',
		]) {
			expect(during[key]).toEqual(before[key]);
		}
		await page.goForward();
		await expect(page).toHaveURL(/\/review$/);
		await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Saved second item');
		await expect(page.getByLabel('Quantity', { exact: true })).toHaveValue('3');
		expect(await page.evaluate(() => history.length)).toBe(historyLength);
	}
	await page.goBack();
	await expect(page).toHaveURL(/\/capture$/);
	await page.getByRole('button', { name: 'Return to Review', exact: true }).click();
	await expect(page).toHaveURL(/\/review$/);
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Saved second item');
	await page.reload();
	await expect(page).toHaveURL(/\/location$/);
	await page.getByRole('button', { name: 'Resume Session', exact: true }).click();
	await expect(page).toHaveURL(/\/review$/);
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Saved second item');
	const after = (await readDrafts(page, 'deployment:user:g1'))[0];
	for (const key of [
		'status',
		'currentReviewIndex',
		'detectedItems',
		'confirmedItems',
		'activeReviewDraft',
	]) {
		expect(after[key]).toEqual(before[key]);
	}
});
