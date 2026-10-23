import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { detectedItems } from './fixtures/data';
import { selectLocation, uploadPhoto, analyzePhotos } from './helpers/scan';

test('invalid capture and review asset IDs block analysis and confirmation before creation', async ({
	page,
	api,
}) => {
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Validated item'])));
	await selectLocation(page);
	await uploadPhoto(page);
	await page.getByRole('button', { name: 'Expand options', exact: true }).click();
	await page.getByLabel('Asset ID', { exact: true }).fill('032-REVIEW-3');
	await expect(page.getByLabel('Asset ID', { exact: true })).toHaveAttribute(
		'aria-invalid',
		'true'
	);
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await expect(
		page.getByText('Fix the invalid asset ID before analyzing.', { exact: true })
	).toBeVisible();
	expect(
		api.requests.filter((request) => new URL(request.url()).pathname === '/api/tools/vision/detect')
	).toHaveLength(0);
	// Starting analysis collapses the photo options, including on validation failure.
	await page.getByRole('button', { name: 'Expand options', exact: true }).click();
	await page.getByLabel('Asset ID', { exact: true }).fill('032-303');
	await analyzePhotos(page);
	await page.getByLabel('Asset ID', { exact: true }).fill('032-REVIEW-3');
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page).toHaveURL(/\/review$/);
	await expect(page.getByLabel('Asset ID', { exact: true })).toHaveAttribute(
		'aria-invalid',
		'true'
	);
	expect(
		api.requests.filter(
			(request) => new URL(request.url()).pathname === '/api/items' && request.method() === 'POST'
		)
	).toHaveLength(0);
	const confirmError = page.getByRole('alert').filter({
		hasText: 'Enter a numeric Homebox asset ID',
		has: page.getByRole('button', { name: 'Dismiss notification' }),
	});
	await expect(confirmError).toBeVisible();
	await confirmError.getByRole('button', { name: 'Dismiss notification' }).click();
	await page.getByLabel('Asset ID', { exact: true }).fill('000-000');
	await expect(confirmError).toHaveCount(0);
	await page.goBack();
	await expect(page).toHaveURL(/\/capture$/);
	await expect(page.getByRole('button', { name: 'Return to Review', exact: true })).toBeVisible();
	await expect(confirmError).toHaveCount(0);
	await page.getByRole('button', { name: 'Return to Review', exact: true }).click();
	await expect(page.getByLabel('Asset ID', { exact: true })).toHaveValue('000-000');

	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page).toHaveURL(/\/summary$/);
});
