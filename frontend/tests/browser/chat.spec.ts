import { type BrowserContext, type Request } from '@playwright/test';
import { test, expect } from './fixtures/test';
import { json, sse } from './fixtures/api';
import { mockApi, lifecycleRequests } from './fixtures/auth-api';
test('Markdown rendering failures display assistant content as escaped text', async ({ page }) => {
	// Deeply nested, benign Markdown exercises a real parser failure without script content.
	const response = '<strong>Literal markup</strong>\n\n' + '> '.repeat(10_000) + 'Nested text';
	const renderErrors: string[] = [];
	page.on('console', (message) => {
		if (message.type() === 'error' && message.text().includes('Markdown render failed:')) {
			renderErrors.push(message.text());
		}
	});
	await mockApi(page, { assistantResponse: response });
	await page.goto('/chat');
	await page.getByLabel('Chat message input').fill('Show the sample');
	await page.getByRole('button', { name: 'Send message' }).click();

	const bubble = page.locator('.chat-bubble').last();
	await expect(bubble.locator('p')).toHaveText(response);
	await expect(bubble.locator('strong')).toHaveCount(0);
	await expect(bubble.locator('.markdown-content')).toHaveCount(0);
	expect(renderErrors.length).toBeGreaterThan(0);
});

async function chatContext(context: BrowserContext): Promise<string> {
	const page = await context.newPage();
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	const requests: Request[] = [];
	const api = await mockApi(page, { requests });
	await page.goto('/chat');
	await expect(page).toHaveURL(/\/chat$/);
	await expect
		.poll(() => requests.some((request) => new URL(request.url()).pathname === '/api/chat/status'))
		.toBe(true);
	const statusRequest = requests.find(
		(candidate) => new URL(candidate.url()).pathname === '/api/chat/status'
	);
	const id = statusRequest?.headers()['x-companion-chat-context'];
	expect(id).toMatch(/^[0-9a-f-]{36}$/);
	await page.getByLabel('Chat message input').fill('Hi');
	await page.getByRole('button', { name: 'Send message' }).click();
	await expect(page.getByText('Hello')).toBeVisible();
	const messageRequest = requests.find(
		(candidate) => new URL(candidate.url()).pathname === '/api/chat/messages'
	);
	expect(messageRequest?.headers()['x-companion-chat-context']).toBe(id);
	expect(messageRequest?.headers()['x-companion-request']).toBe('1');
	expect(messageRequest?.headers()['x-group-id']).toBe('g1');
	expect(messageRequest?.headers().authorization).toBeUndefined();
	await page.close();
	expect(api.unknown, 'Undeclared /api requests in secondary browser').toEqual([]);
	expect(api.external, 'Unexpected external requests in secondary browser').toEqual([]);
	expect(api.routeErrors, 'Mock handler errors in secondary browser').toEqual([]);
	expect(errors, 'Unhandled browser errors in secondary browser').toEqual([]);
	return id!;
}

test('separate browsers use distinct chat contexts', async ({ browser }) => {
	const options = { baseURL: 'http://127.0.0.1:4173', serviceWorkers: 'block' as const };
	const first = await browser.newContext(options);
	const second = await browser.newContext(options);
	try {
		const [firstId, secondId] = await Promise.all([chatContext(first), chatContext(second)]);
		expect(firstId).not.toBe(secondId);
	} finally {
		await first.close();
		await second.close();
	}
});

test('chat context falls back to UUIDv4 when randomUUID is unavailable', async ({ page }) => {
	const requests: Request[] = [];
	await mockApi(page, { requests });
	await page.addInitScript(() => {
		Object.defineProperty(crypto, 'randomUUID', { value: undefined, configurable: true });
	});
	await page.goto('/chat');
	await expect
		.poll(() =>
			requests.filter((request) => new URL(request.url()).pathname === '/api/chat/status')
		)
		.toHaveLength(1);
	const firstStatus = requests.find(
		(request) => new URL(request.url()).pathname === '/api/chat/status'
	);
	const firstId = firstStatus?.headers()['x-companion-chat-context'];
	expect(firstId).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);

	await page.reload();
	await expect
		.poll(() =>
			requests.filter((request) => new URL(request.url()).pathname === '/api/chat/status')
		)
		.toHaveLength(2);
	const statusRequests = requests.filter(
		(request) => new URL(request.url()).pathname === '/api/chat/status'
	);
	expect(statusRequests[1].headers()['x-companion-chat-context']).toBe(firstId);
});

for (const failure of [
	{ name: 'HTTP key rejection', status: 502, code: 'HOMEBOX_API_KEY_REJECTED' },
	{ name: 'stream key rejection', status: 200, code: 'HOMEBOX_API_KEY_REJECTED' },
	{ name: 'stream Homebox outage', status: 200, code: 'HOMEBOX_UNAVAILABLE' },
]) {
	test(`${failure.name} uses the key-mode Retry shell`, async ({ page }) => {
		const requests: Request[] = [];
		const api = await mockApi(page, { requests });
		api.on('POST', '/api/chat/messages', () =>
			failure.status === 200
				? sse([
						{ event: 'error', data: { code: failure.code, message: 'Homebox connection failed' } },
						{ event: 'done', data: {} },
					])
				: json({ code: failure.code, detail: 'Homebox connection failed' }, failure.status)
		);
		await page.goto('/chat');
		await page.getByLabel('Chat message input').fill('List locations');
		await page.getByRole('button', { name: 'Send message' }).click();
		await expect(page.getByRole('button', { name: 'Retry', exact: true })).toBeVisible();
		await expect(page.locator('input[type="password"]')).toHaveCount(0);
		expect(lifecycleRequests(requests)).toHaveLength(0);
	});
}

test('legacy stream AUTH_FAILED opens reauthentication', async ({ page }) => {
	const api = await mockApi(page, { mode: 'legacy' });
	await page.addInitScript(() => {
		localStorage.setItem('hbc_token', 'valid-legacy-token');
		localStorage.setItem('hbc_token_expires', new Date(Date.now() + 3_600_000).toISOString());
	});
	api.on('POST', '/api/chat/messages', () =>
		sse([
			{ event: 'error', data: { code: 'AUTH_FAILED', message: 'Session expired' } },
			{ event: 'done', data: {} },
		])
	);
	await page.goto('/chat');
	await page.getByLabel('Chat message input').fill('List locations');
	await page.getByRole('button', { name: 'Send message' }).click();
	await expect(page.getByRole('heading', { name: 'Session Expired' })).toBeVisible();
});
