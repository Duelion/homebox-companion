import { expect, test } from './fixtures/test';
import { fieldPreferences } from './fixtures/data';
import { json } from './fixtures/api';

test('saving a default tag survives a reload', async ({ page, api }) => {
	let savedPreferences = fieldPreferences();
	const savedRequests: Record<string, unknown>[] = [];

	api.on('GET', '/api/tags', () => json([{ id: 'tag-toolbox', name: 'Toolbox' }]));
	api.on('GET', '/api/settings/field-preferences', () => json(savedPreferences));
	api.on('PUT', '/api/settings/field-preferences', (request) => {
		const values = request.postDataJSON() as Record<string, unknown>;
		savedRequests.push(values);
		savedPreferences = { ...fieldPreferences(), ...values };
		return json(savedPreferences);
	});
	api.on('PUT', '/api/settings/custom-fields', () => json([]));

	await page.goto('/settings');
	await page.getByRole('button', { name: 'General Settings' }).click();
	await page.getByLabel('Default Tag').selectOption('tag-toolbox');
	await page.getByRole('button', { name: 'Save' }).click();
	await expect(page.getByRole('button', { name: 'Saved!' })).toBeVisible();

	expect(savedRequests).toEqual([expect.objectContaining({ default_tag_id: 'tag-toolbox' })]);
	await page.reload();
	await page.getByRole('button', { name: 'General Settings' }).click();
	await expect(page.getByLabel('Default Tag')).toHaveValue('tag-toolbox');
});
