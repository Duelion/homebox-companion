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

test.describe('location cache refresh', () => {
	test.beforeEach(async ({ page }) => {
		await page.addInitScript(() => {
			localStorage.setItem(
				'hbc-location-preferences',
				JSON.stringify({ showItemQuantities: true, containerLocationsOnly: true })
			);
		});
	});

	test('returning to All refreshes quantities in browsing and search', async ({ page, api }) => {
		let quantity = 15;
		api.on('GET', '/api/locations/tree', () =>
			json([{ ...location(), totalItemQuantity: quantity }])
		);
		await page.goto('/location');
		await page.getByRole('button', { name: 'Storage 15 items', exact: true }).click();
		quantity = 27;
		await page.getByRole('button', { name: 'All', exact: true }).click();
		await expect(page.getByRole('button', { name: 'Storage 27 items', exact: true })).toBeVisible();
		await page.getByPlaceholder('Search all locations...').fill('Storage');
		await expect(page.getByRole('button', { name: 'Storage 27 items', exact: true })).toBeVisible();
	});

	for (const selectedName of ['New box', 'Moved box']) {
		test(`selected refresh updates containers and the path of ${selectedName}`, async ({
			page,
			api,
		}) => {
			const oldBox = { ...location('old', 'Old box'), type: 'location' };
			const newBox = { ...location('new', 'New box'), type: 'location' };
			const movedBox = { ...location('moved', 'Moved box'), type: 'location' };
			const record = { ...location('record', 'Vinyl record'), type: 'item' };
			let storage = { ...location(), children: [oldBox] };
			let other = { ...location('other', 'Other room'), children: [movedBox] };
			api.on('GET', '/api/locations/tree', () => json([storage, other]));
			// The details endpoint enriches children without the tree-only type field.
			api.on('GET', '/api/locations/loc-1', () =>
				json({
					...storage,
					children: storage.children.map((child) => location(child.id, child.name)),
				})
			);
			await page.goto('/location');
			await page.getByRole('button', { name: 'Storage 0 items', exact: true }).click();
			await page.getByRole('button', { name: 'Select current location', exact: true }).click();

			storage = { ...storage, children: [newBox, movedBox, record] };
			other = { ...other, children: [oldBox] };
			const refreshed = page.waitForResponse('**/api/tags');
			await pullToRefresh(page);
			await refreshed;
			await page.getByRole('button', { name: 'Place Inside a Container', exact: true }).click();
			const dialog = page.getByRole('dialog', { name: 'Select Container', exact: true });
			await expect(dialog.getByRole('button', { name: 'Old box', exact: true })).toHaveCount(0);
			await expect(dialog.getByRole('button', { name: 'Vinyl record', exact: true })).toHaveCount(
				0
			);
			await expect(dialog.getByRole('button', { name: 'New box', exact: true })).toBeVisible();
			await expect(dialog.getByRole('button', { name: 'Moved box', exact: true })).toBeVisible();
			await dialog.getByRole('button', { name: selectedName, exact: true }).click();
			await expect(page.getByText(`Storage / ${selectedName}`, { exact: true })).toBeVisible();
			await page.getByRole('button', { name: 'Continue to Capture', exact: true }).click();
			await expect(page.getByText(`Storage / ${selectedName}`, { exact: true })).toBeVisible();
		});
	}
});

async function pullToRefresh(page: import('@playwright/test').Page) {
	await page.evaluate(() => window.scrollTo(0, 0));
	await page.dispatchEvent('body', 'touchstart', { touches: [{ clientY: 0 }] });
	await page.dispatchEvent('body', 'touchmove', { touches: [{ clientY: 400 }] });
	await page.dispatchEvent('body', 'touchend', { touches: [] });
}
