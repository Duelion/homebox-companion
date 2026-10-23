import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { detectedItems } from './fixtures/data';
import { selectLocation, uploadPhoto, analyzePhotos } from './helpers/scan';

test('review keeps invalid fields editable and accepts a zero purchase price', async ({
	page,
	api,
}) => {
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Validated item'])));
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	for (const value of ['0', '1.5', '']) {
		await page.getByLabel('Quantity', { exact: true }).fill(value);
		await page.getByRole('button', { name: 'Confirm', exact: true }).click();
		await expect(page).toHaveURL(/\/review$/);
		await expect(page.getByLabel('Quantity', { exact: true })).toHaveAttribute(
			'aria-invalid',
			'true'
		);
		await expect(
			page.getByText('Enter a whole quantity of 1 or more.', { exact: true }).first()
		).toBeVisible();
	}
	await page.getByLabel('Quantity', { exact: true }).fill('1');
	await page.getByLabel('Name', { exact: true }).fill('   ');
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page).toHaveURL(/\/review$/);
	await expect(page.getByLabel('Name', { exact: true })).toHaveAttribute('aria-invalid', 'true');
	await page.getByLabel('Name', { exact: true }).fill('Valid item');
	await page.getByRole('button', { name: 'Extended Fields' }).click();
	await page.getByLabel('Purchase Price', { exact: true }).fill('-1');
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page).toHaveURL(/\/review$/);
	await expect(page.getByLabel('Purchase Price', { exact: true })).toHaveAttribute(
		'aria-invalid',
		'true'
	);
	expect(
		api.requests.filter(
			(request) => new URL(request.url()).pathname === '/api/items' && request.method() === 'POST'
		)
	).toHaveLength(0);
	await page.getByLabel('Purchase Price', { exact: true }).fill('0');
	await page.getByRole('button', { name: 'Confirm', exact: true }).click();
	await expect(page).toHaveURL(/\/summary$/);
});
