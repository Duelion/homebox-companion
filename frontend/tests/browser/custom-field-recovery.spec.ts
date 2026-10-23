import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { createdItem, detectedItems } from './fixtures/data';
import { readDrafts } from './helpers/recovery';
import { analyzePhotos, selectLocation, uploadPhoto } from './helpers/scan';

test('confirmed custom fields survive reload recovery and submission', async ({ page, api }) => {
	api.allowPageError(/navigation aborted/);
	const creations: unknown[] = [];
	api.on('POST', '/api/tools/vision/detect', () =>
		json({
			...detectedItems(['Desk lamp']),
			items: [{ name: 'Desk lamp', quantity: 1, custom_fields: { Warranty: 'One year' } }],
		})
	);
	api.on('POST', '/api/items', (request) => {
		creations.push(request.postDataJSON());
		return json(createdItem('recovered-lamp'));
	});
	api.on('POST', '/api/items/recovered-lamp/attachments', () => json({}));

	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByLabel('Warranty', { exact: true }).fill('Two years');
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page).toHaveURL(/\/summary$/);
	await expect
		.poll(async () => (await readDrafts(page, 'deployment:user:g1'))[0])
		.toMatchObject({
			confirmedItems: [
				expect.objectContaining({ name: 'Desk lamp', custom_fields: { Warranty: 'Two years' } }),
			],
		});

	await page.reload();
	await expect(page).toHaveURL(/\/location$/);
	await page.getByRole('button', { name: 'Resume Session' }).click();
	await expect(page).toHaveURL(/\/summary$/);
	await expect(page.getByText('Desk lamp', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Edit item', exact: true }).click();
	await expect(page.getByLabel('Warranty', { exact: true })).toHaveValue('Two years');
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await page.getByRole('button', { name: /Submit All Items/ }).click();
	await expect(page).toHaveURL(/\/success$/);
	expect(creations).toEqual([
		expect.objectContaining({
			items: [
				expect.objectContaining({ name: 'Desk lamp', custom_fields: { Warranty: 'Two years' } }),
			],
		}),
	]);
});
