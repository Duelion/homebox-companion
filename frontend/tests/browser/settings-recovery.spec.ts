import { expect, test } from './fixtures/test';
import { json } from './fixtures/api';

for (const logs of [
	{ title: 'Application Logs', toggle: 'Show Server Logs', path: '/api/logs' },
	{ title: 'LLM Debug Log', toggle: 'Show LLM Debug Log', path: '/api/logs/llm-debug' },
]) {
	test(`${logs.title} exposes initial errors, retains diagnostics on refresh errors, and recovers`, async ({
		page,
		api,
	}) => {
		let fail = true;
		let content = 'Initial diagnostic';
		api.on('GET', logs.path, (request) => {
			expect(request.headers()['x-companion-log-token']).toBeUndefined();
			return fail
				? json({ detail: 'Log service unavailable' }, 503)
				: json({ logs: content, filename: 'test.log', total_lines: 1, truncated: false });
		});
		await page.goto('/settings');
		await page.getByRole('button', { name: 'View Logs', exact: true }).click();
		const panel = page.getByRole('heading', { name: logs.title, exact: true }).locator('../..');
		await panel.getByRole('button', { name: logs.toggle, exact: true }).click();
		await expect(panel.getByRole('alert')).toContainText('Log service unavailable');
		fail = false;
		await panel.getByRole('button', { name: 'Retry', exact: true }).click();
		await expect(panel.getByText('Initial diagnostic', { exact: true })).toBeVisible();
		await expect(panel.getByRole('alert')).toHaveCount(0);
		fail = true;
		await panel.getByRole('button', { name: 'Refresh', exact: true }).click();
		await expect(panel.getByRole('alert')).toBeVisible();
		await expect(panel.getByText('Initial diagnostic', { exact: true })).toBeVisible();
		fail = false;
		content = 'Recovered diagnostic';
		await panel.getByRole('button', { name: 'Retry', exact: true }).click();
		await expect(panel.getByText('Recovered diagnostic', { exact: true })).toBeVisible();
		await expect(panel.getByRole('alert')).toHaveCount(0);
		api.on('GET', `${logs.path}/download`, (request) => {
			expect(request.headers()['x-companion-log-token']).toBeUndefined();
			return { status: 200, contentType: 'text/plain', body: content };
		});
		const download = page.waitForEvent('download');
		await panel.getByRole('button', { name: 'Download', exact: true }).click();
		expect((await download).suggestedFilename()).toBe('test.log');
	});

	test(`${logs.title} can refresh an empty result`, async ({ page, api }) => {
		let content = '';
		api.on('GET', logs.path, () =>
			json({ logs: content, filename: null, total_lines: content ? 1 : 0, truncated: false })
		);
		await page.goto('/settings');
		await page.getByRole('button', { name: 'View Logs', exact: true }).click();
		const panel = page.getByRole('heading', { name: logs.title, exact: true }).locator('../..');
		await panel.getByRole('button', { name: logs.toggle, exact: true }).click();
		await expect(
			panel.getByText(/^No (server logs available|LLM debug log files found)\.$/)
		).toBeVisible();
		content = 'New diagnostic';
		await panel.getByRole('button', { name: 'Refresh', exact: true }).click();
		await expect(panel.getByText('New diagnostic', { exact: true })).toBeVisible();
	});
}

test('prompt previews reload the current draft with one click after edits, reset, custom removal, and save', async ({
	page,
	api,
}) => {
	const previews: Record<string, unknown>[] = [];
	api.on('GET', '/api/settings/custom-fields', () =>
		json([{ name: 'Condition', ai_instruction: 'Describe wear' }])
	);
	api.on('POST', '/api/settings/prompt-preview', (request) => {
		previews.push(request.postDataJSON() as Record<string, unknown>);
		return json({ prompt: `Current preview ${previews.length}` });
	});
	api.on('PUT', '/api/settings/field-preferences', (request) => json(request.postDataJSON()));
	api.on('PUT', '/api/settings/custom-fields', (request) => json(request.postDataJSON()));
	await page.goto('/settings');
	const preview = page.getByRole('button', { name: 'Preview AI Prompt' });
	const openPreview = async (count: number) => {
		await preview.click();
		await expect(page.getByText(`Current preview ${count}`, { exact: true })).toBeVisible();
		expect(previews).toHaveLength(count);
	};
	await openPreview(1);
	await page.getByRole('button', { name: 'General Settings' }).click();
	await page.getByLabel('Output Language', { exact: true }).fill('Spanish');
	await openPreview(2);
	expect(previews[1].field_preferences).toEqual({ output_language: 'Spanish' });
	await page.getByRole('button', { name: 'Reset to default' }).click();
	await openPreview(3);
	expect(previews[2].field_preferences).toEqual({});
	await page.getByRole('button', { name: 'Custom Fields', exact: true }).click();
	await page.getByRole('button', { name: 'Remove field' }).click();
	await openPreview(4);
	expect(previews[3].custom_fields).toEqual([]);
	await page.getByRole('button', { name: 'Save', exact: true }).click();
	await expect(page.getByRole('button', { name: 'Saved!' })).toBeVisible();
	await openPreview(5);
});

test('an unavailable latest release is visible and can be checked again', async ({ page, api }) => {
	let latest: string | null = null;
	api.on('GET', '/api/version', () =>
		json({ version: 'test', latest_version: latest, update_available: false })
	);
	await page.goto('/settings');
	await page.getByRole('button', { name: 'Check', exact: true }).click();
	await expect(page.getByText('Unable to check for updates. Please try again.')).toBeVisible();
	await expect(page.getByText('Up to date', { exact: true })).toHaveCount(0);
	latest = 'test';
	await page.getByRole('button', { name: 'Check', exact: true }).click();
	await expect(page.getByText('Up to date', { exact: true })).toBeVisible();
});

test('remote diagnostics are cleared on collection changes and teardown', async ({ page, api }) => {
	api.on('GET', '/api/logs', () =>
		json({ logs: 'Session diagnostic', filename: 'test.log', total_lines: 1, truncated: false })
	);
	await page.goto('/settings');
	await page.getByRole('button', { name: 'View Logs', exact: true }).click();
	await expect(page.getByLabel('Server log access key', { exact: true })).toHaveCount(0);
	await page.getByRole('button', { name: 'Show Server Logs', exact: true }).click();
	await expect(page.getByText('Session diagnostic', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: /Personal/ }).click();
	await page.getByRole('option', { name: /Shared/ }).click();
	await expect(page.getByText('Session diagnostic', { exact: true })).toHaveCount(0);
	await page.getByRole('button', { name: 'Show Server Logs', exact: true }).click();
	await expect(page.getByText('Session diagnostic', { exact: true })).toBeVisible();
	await page.getByRole('link', { name: 'Scan', exact: true }).click();
	await page.locator('a[href="/settings"]:visible').click();
	await page.getByRole('button', { name: 'View Logs', exact: true }).click();
	await expect(page.getByText('Session diagnostic', { exact: true })).toHaveCount(0);
	expect(api.requests.some((request) => request.headers()['x-companion-log-token'])).toBe(false);
});
