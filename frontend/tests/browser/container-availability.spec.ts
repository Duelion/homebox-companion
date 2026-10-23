import { expect, test } from './fixtures/test';
import { json } from './fixtures/api';

test('a location with zero total quantity can select an existing container record', async ({
	page,
	api,
}) => {
	api.on('GET', '/api/items', () =>
		json([{ id: 'empty-box', name: 'Empty reusable box', quantity: 0, thumbnailId: null }])
	);
	await page.goto('/location');
	await page.getByRole('button', { name: /Storage/ }).click();
	await page.getByRole('button', { name: 'Select current location', exact: true }).click();
	const picker = page.getByRole('button', { name: 'Place Inside an Item', exact: true });
	await expect(picker).toBeEnabled();
	await picker.click();
	const dialog = page.getByRole('dialog', { name: 'Select Container Item', exact: true });
	await dialog.getByRole('button', { name: 'Empty reusable box Quantity: 0', exact: true }).click();
	await expect(dialog).toBeHidden();
	await expect(
		page.getByRole('button', { name: 'Inside: Empty reusable box', exact: true })
	).toBeVisible();
	await page.getByRole('button', { name: 'Continue to Capture', exact: true }).click();
	await expect(page).toHaveURL(/\/capture$/);
	await expect(page.getByText('Inside: Empty reusable box', { exact: true })).toBeVisible();
});

test('a genuinely empty location opens the picker and explains there are no items', async ({
	page,
	api,
}) => {
	api.on('GET', '/api/items', () => json([]));
	await page.goto('/location');
	await page.getByRole('button', { name: /Storage/ }).click();
	await page.getByRole('button', { name: 'Select current location', exact: true }).click();
	await page.getByRole('button', { name: 'Place Inside an Item', exact: true }).click();
	const dialog = page.getByRole('dialog', { name: 'Select Container Item', exact: true });
	await expect(dialog.getByText('No items in this location', { exact: true })).toBeVisible();
	await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
	await expect(dialog).toBeHidden();
	await expect(
		page.getByRole('button', { name: 'Continue to Capture', exact: true })
	).toBeEnabled();
});
