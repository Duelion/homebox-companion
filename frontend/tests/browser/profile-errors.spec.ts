import { expect, test } from './fixtures/test';
import { json } from './fixtures/api';

const primary = { name: 'Primary', model: 'gpt-5-nano', status: 'primary' };
const validation = 'Profiles must have exactly one primary and at most one fallback';

for (const variant of ['desktop', '@mobile'] as const) {
	test(`profile validation is visible in the dialog and can be retried ${variant}`, async ({
		page,
		api,
	}) => {
		api.on('GET', '/api/llm/profiles', () => json({ profiles: [primary] }));
		let saves = 0;
		api.on('PUT', '/api/llm/profiles/Primary', (request) => {
			saves++;
			const body = request.postDataJSON() as { status: string };
			return body.status === 'off'
				? json({ detail: validation, error_code: 'VALIDATION_ERROR' }, 400)
				: json(primary);
		});
		await page.goto('/settings');
		await page.getByRole('button', { name: 'Edit profile' }).click();
		const dialog = page.getByRole('dialog', { name: 'Edit Profile' });
		await dialog.getByLabel('Name', { exact: true }).fill('Kept name');
		await dialog.getByLabel('Status', { exact: true }).selectOption('off');
		await dialog.getByRole('button', { name: 'Save', exact: true }).click();
		await expect(dialog.getByRole('alert')).toHaveText(validation);
		await expect(dialog.getByRole('alert')).toBeInViewport();
		await expect(dialog.getByRole('alert')).toBeFocused();
		await expect(dialog.getByLabel('Name', { exact: true })).toHaveValue('Kept name');
		await expect(dialog.getByRole('button', { name: 'Save', exact: true })).toBeEnabled();
		await dialog.getByLabel('Status', { exact: true }).selectOption('primary');
		await dialog.getByRole('button', { name: 'Save', exact: true }).click();
		await expect(dialog).toBeHidden();
		expect(saves).toBe(2);
		await page.getByRole('button', { name: 'Edit profile' }).click();
		await expect(dialog.getByRole('alert')).toHaveCount(0);
	});
}

test('a rejected save cannot add an error or move focus in a reopened editor', async ({
	page,
	api,
}) => {
	const gate = api.gate();
	api.on('POST', '/api/llm/profiles', async () => {
		await gate.promise;
		return json({ detail: validation }, 400);
	});
	await page.goto('/settings');
	await page.getByRole('button', { name: 'Add', exact: true }).click();
	const dialog = page.getByRole('dialog', { name: 'New Profile' });
	await dialog.getByLabel('Name', { exact: true }).fill('Old');
	await dialog.getByLabel('Model', { exact: true }).fill('gpt-5-nano');
	await dialog.getByRole('button', { name: 'Save', exact: true }).click();
	await expect(dialog.getByRole('button', { name: 'Saving...' })).toBeVisible();
	await page.keyboard.press('Escape');
	await page.getByRole('button', { name: 'Add', exact: true }).click();
	await dialog.getByLabel('Name', { exact: true }).fill('New');
	const response = page.waitForResponse(
		(reply) => reply.url().endsWith('/api/llm/profiles') && reply.request().method() === 'POST'
	);
	gate.release();
	await response;
	await expect(dialog.getByLabel('Name', { exact: true })).toHaveValue('New');
	await expect(dialog.getByLabel('Name', { exact: true })).toBeFocused();
	await expect(dialog.getByRole('alert')).toHaveCount(0);
	await expect(dialog.getByRole('button', { name: 'Save', exact: true })).toBeEnabled();
});

test('a saved profile with a failed list refresh cannot be created twice by retry', async ({
	page,
	api,
}) => {
	let saved = false;
	api.on('GET', '/api/llm/profiles', () =>
		saved ? json({ detail: 'Refresh unavailable' }, 503) : json({ profiles: [] })
	);
	api.on('POST', '/api/llm/profiles', () => {
		saved = true;
		return json(primary);
	});
	await page.goto('/settings');
	await page.getByRole('button', { name: 'Add', exact: true }).click();
	const dialog = page.getByRole('dialog', { name: 'New Profile' });
	await dialog.getByLabel('Name', { exact: true }).fill('Primary');
	await dialog.getByLabel('Model', { exact: true }).fill('gpt-5-nano');
	await dialog.getByRole('button', { name: 'Save', exact: true }).click();
	await expect(dialog).toBeHidden();
	await expect(page.getByRole('alert')).toHaveText(
		'Profile saved, but the list could not be refreshed: Refresh unavailable'
	);
	expect(
		api.requests.filter(
			(request) => request.method() === 'POST' && request.url().endsWith('/api/llm/profiles')
		)
	).toHaveLength(1);
});
