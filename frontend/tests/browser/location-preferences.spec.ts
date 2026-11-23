import { expect, test } from './fixtures/test';
import { json } from './fixtures/api';
import { location } from './fixtures/data';

test('location options persist and use Homebox container locations', async ({ page, api }) => {
	const box = { ...location('box', 'Reusable box'), type: 'location', totalItemQuantity: 12 };
	const record = { ...location('record', 'Vinyl record'), type: 'item' };
	const storage = { ...location(), children: [box, record], totalItemQuantity: 15 };
	api.on('GET', '/api/locations/tree', () => json([storage]));
	api.on('GET', '/api/locations/loc-1', () => json(storage));

	await page.goto('/settings');
	const totals = page.getByRole('checkbox', { name: /Show total item quantities/ });
	const containers = page.getByRole('checkbox', {
		name: /Only pick containers marked as locations/,
	});
	await expect(totals).not.toBeChecked();
	await expect(containers).not.toBeChecked();
	await totals.check();
	await containers.check();
	await page.reload();
	await expect(totals).toBeChecked();
	await expect(containers).toBeChecked();

	await page.goto('/location');
	await page.getByRole('button', { name: 'Storage 15 items', exact: true }).click();
	expect(
		api.requests.some(
			(request) =>
				new URL(request.url()).pathname === '/api/locations/tree' &&
				new URL(request.url()).searchParams.get('include_item_totals') === 'true'
		)
	).toBe(true);
	await page.getByRole('button', { name: 'Select current location', exact: true }).click();
	await page.getByRole('button', { name: 'Place Inside a Container', exact: true }).click();

	const dialog = page.getByRole('dialog', { name: 'Select Container', exact: true });
	await expect(dialog.getByRole('button', { name: 'Vinyl record' })).toHaveCount(0);
	await dialog.getByRole('button', { name: 'Reusable box', exact: true }).click();
	await expect(page.getByText('Storage / Reusable box', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Continue to Capture', exact: true }).click();
	await expect(page.getByText('Storage / Reusable box', { exact: true })).toBeVisible();
});

test('the default location view avoids requesting totals', async ({ page, api }) => {
	await page.goto('/location');
	await expect(page.getByRole('button', { name: /Storage/ })).toBeVisible();

	const treeRequest = api.requests.find(
		(request) => new URL(request.url()).pathname === '/api/locations/tree'
	);
	expect(treeRequest).toBeDefined();
	expect(new URL(treeRequest!.url()).searchParams.has('include_item_totals')).toBe(false);
});
