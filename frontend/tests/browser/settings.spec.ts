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

test('the Workers AI Gemma option is saved and restored with the profile', async ({
	page,
	api,
}) => {
	let profile = {
		name: 'Workers AI',
		model: 'openai/@cf/google/gemma-4-26b-a4b-it',
		api_base:
			'https://api.cloudflare.com/client/v4/accounts/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/ai/v1',
		has_api_key: true,
		status: 'primary',
		disable_workers_ai_gemma_thinking: false,
	};
	api.on('GET', '/api/llm/profiles', () => json({ profiles: [profile] }));
	api.on('PUT', '/api/llm/profiles/Workers%20AI', (request) => {
		const changes = request.postDataJSON();
		expect(changes.disable_workers_ai_gemma_thinking).toBe(true);
		expect(changes.api_key).toBeUndefined();
		profile = { ...profile, disable_workers_ai_gemma_thinking: true };
		return json(profile);
	});

	await page.goto('/settings');
	const edit = page.getByRole('button', { name: 'Edit profile', exact: true });
	await edit.click();
	const option = page.getByRole('checkbox', { name: /Disable Gemma thinking/ });
	await expect(option).not.toBeChecked();
	await option.check();
	await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
	await expect(page.getByRole('dialog')).toBeHidden();
	await page.reload();
	await edit.click();
	await expect(option).toBeChecked();
});
