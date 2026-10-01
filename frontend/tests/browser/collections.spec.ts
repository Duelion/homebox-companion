import { type Request } from '@playwright/test';
import { test, expect } from './fixtures/test';
import { mockApi } from './fixtures/auth-api';
import { putDraft, readDrafts } from './helpers/recovery';
test('group switch discards a late response and preserves the old scoped draft', async ({
	page,
}) => {
	const api = await mockApi(page, {
		locationTree: async (request) => {
			if (request.headers()['x-group-id'] === 'g1') {
				await gate.promise;
				return [{ id: 'old', name: 'Old Group Location', description: '', children: [] }];
			}
			return [{ id: 'new', name: 'New Group Location', description: '', children: [] }];
		},
	});
	const gate = api.gate();

	await page.goto('/location');
	await expect(page.getByRole('button', { name: /Personal/ })).toBeVisible();
	await putDraft(page, 'deployment:user:g1', { id: 'old-draft', status: 'capturing' });
	await page.getByRole('button', { name: /Personal/ }).click();
	const oldSettled = new Promise<void>((resolve) => {
		const matches = (request: Request) =>
			new URL(request.url()).pathname === '/api/locations/tree' &&
			request.headers()['x-group-id'] === 'g1';
		const finish = (request: Request) => {
			if (!matches(request)) return;
			page.off('requestfinished', finish);
			page.off('requestfailed', finish);
			resolve();
		};
		page.on('requestfinished', finish);
		page.on('requestfailed', finish);
	});
	await page.getByRole('option', { name: /Shared/ }).click();
	await expect(page.getByText('New Group Location')).toBeVisible();
	gate.release();
	await oldSettled;
	await expect(page.getByText('Old Group Location')).toHaveCount(0);
	const drafts = await readDrafts(page);
	expect(drafts).toEqual([expect.objectContaining({ id: 'old-draft' })]);
});
