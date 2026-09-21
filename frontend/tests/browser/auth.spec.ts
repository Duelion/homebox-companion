import { expect, test, type BrowserContext, type Page, type Request } from '@playwright/test';

const config = (authMode: 'legacy' | 'api_key') => ({
	auth_mode: authMode,
	is_demo_mode: false,
	demo_mode_explicit: false,
	homebox_url: 'http://homebox.test',
	llm_model: 'gpt-5-mini',
	update_check_enabled: false,
	image_quality: 'high',
	log_level: 'INFO',
	capture_max_images: 10,
	capture_max_file_size_mb: 20,
	print_enabled: false,
});

const json = (body: unknown, status = 200) => ({
	status,
	contentType: 'application/json',
	body: JSON.stringify(body),
});

async function mockApi(
	page: Page,
	options: {
		mode?: 'legacy' | 'api_key';
		connectionStatus?: () => number;
		requests?: Request[];
		chatStatus?: number;
		locationTree?: (request: Request) => Promise<unknown>;
		refreshStatus?: number;
		assistantResponse?: string;
	} = {}
) {
	const mode = options.mode ?? 'api_key';
	await page.route('**/api/**', async (route) => {
		const request = route.request();
		options.requests?.push(request);
		const path = new URL(request.url()).pathname;
		if (path === '/api/config') return route.fulfill(json(config(mode)));
		if (path === '/api/homebox/connection') {
			const status = options.connectionStatus?.() ?? 200;
			return route.fulfill(
				status === 200
					? json({
							connected: true,
							context_id: 'deployment:user',
							user_id: 'user-1',
							default_group_id: 'g1',
						})
					: json(
							status === 502
								? {
										detail: 'The configured Homebox API key was rejected.',
										code: 'HOMEBOX_API_KEY_REJECTED',
									}
								: { detail: 'Homebox is unavailable', code: 'HOMEBOX_UNAVAILABLE' },
							status
						)
			);
		}
		if (path === '/api/groups') {
			return route.fulfill(
				json([
					{ id: 'g2', name: 'Shared' },
					{ id: 'g1', name: 'Personal' },
				])
			);
		}
		if (path === '/api/version') {
			return route.fulfill(
				json({ version: 'test', latest_version: null, update_available: false })
			);
		}
		if (path === '/api/locations/tree') {
			return route.fulfill(json(options.locationTree ? await options.locationTree(request) : []));
		}
		if (path === '/api/tags') return route.fulfill(json([]));
		if (path === '/api/locations') return route.fulfill(json([]));
		if (path === '/api/chat/health') {
			return route.fulfill(
				json({ status: 'ok', chat_enabled: true, max_history: 20, approval_timeout_seconds: 300 })
			);
		}
		if (path === '/api/chat/status') {
			if (options.chatStatus && options.chatStatus !== 200) {
				return route.fulfill(
					json(
						{
							detail: 'The configured Homebox API key was rejected.',
							code: 'HOMEBOX_API_KEY_REJECTED',
						},
						options.chatStatus
					)
				);
			}
			return route.fulfill(json({ session_id: 's1', message_count: 0 }));
		}
		if (path === '/api/chat/pending') return route.fulfill(json({ approvals: [] }));
		if (path === '/api/chat/messages') {
			return route.fulfill({
				status: 200,
				contentType: 'text/event-stream',
				body: `event: text\ndata: ${JSON.stringify({ content: options.assistantResponse ?? 'Hello' })}\n\nevent: done\ndata: {}\n\n`,
			});
		}
		if (path === '/api/login') {
			return route.fulfill(
				json({
					token: 'fresh-token',
					expires_at: new Date(Date.now() + 3_600_000).toISOString(),
					message: 'ok',
				})
			);
		}
		if (path === '/api/refresh') {
			return route.fulfill(
				options.refreshStatus && options.refreshStatus !== 200
					? json({ detail: 'Session expired' }, options.refreshStatus)
					: json({
							token: 'refreshed-token',
							expires_at: new Date(Date.now() + 3_600_000).toISOString(),
							message: 'ok',
						})
			);
		}
		return route.fulfill(json({}));
	});
}

function lifecycleRequests(requests: Request[]) {
	return requests.filter((request) =>
		/\/api\/(login|refresh|logout)$/.test(new URL(request.url()).pathname)
	);
}

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

for (const mode of ['api_key', 'legacy'] as const) {
	test(`${mode} startup redirects without briefly rendering the login form`, async ({ page }) => {
		await mockApi(page, { mode });
		await page.addInitScript((authMode) => {
			if (authMode === 'legacy') {
				localStorage.setItem('hbc_token', 'valid-legacy-token');
				localStorage.setItem('hbc_token_expires', new Date(Date.now() + 3_600_000).toISOString());
			}
			// Observe every DOM insertion so a transient form cannot escape the assertion.
			new MutationObserver((records) => {
				for (const record of records) {
					for (const node of record.addedNodes) {
						if (
							node instanceof Element &&
							(node.matches('#email') || node.querySelector('#email'))
						) {
							document.documentElement.dataset.loginFormSeen = 'true';
						}
					}
				}
			}).observe(document, { childList: true, subtree: true });
		}, mode);

		await page.goto('/');
		await expect(page).toHaveURL(/\/location$/);
		await expect(page.getByRole('heading', { name: 'Select Location' })).toBeVisible();
		expect(
			await page.evaluate(() => document.documentElement.dataset.loginFormSeen)
		).toBeUndefined();
	});
}

test('configured-key deep link enters directly and never sends browser credentials', async ({
	page,
}) => {
	const requests: Request[] = [];
	await mockApi(page, { requests });
	await page.addInitScript(() => {
		localStorage.setItem('hbc_token', 'stale-browser-token');
		localStorage.setItem('hbc_token_expires', new Date(Date.now() + 86_400_000).toISOString());
	});

	await page.goto('/location');
	await expect(page).toHaveURL(/\/location$/);
	await expect(page.getByRole('heading', { name: 'Select Location' })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Welcome back' })).toHaveCount(0);
	expect(lifecycleRequests(requests)).toHaveLength(0);
	expect(requests.filter((request) => request.headers().authorization)).toHaveLength(0);
	await expect
		.poll(
			() =>
				requests.filter((request) =>
					['/api/locations/tree', '/api/tags'].includes(new URL(request.url()).pathname)
				).length
		)
		.toBeGreaterThan(0);
	const scopedRequests = requests.filter((request) =>
		['/api/locations/tree', '/api/tags'].includes(new URL(request.url()).pathname)
	);
	expect(scopedRequests.every((request) => request.headers()['x-group-id'] === 'g1')).toBe(true);
	expect(await page.evaluate(() => localStorage.getItem('hbc_token'))).toBeNull();
});

for (const failure of [
	{ status: 502, name: 'rejected key' },
	{ status: 503, name: 'outage' },
]) {
	test(`${failure.name} stays in key mode and Retry preserves quarantined browser state`, async ({
		page,
	}) => {
		const requests: Request[] = [];
		let connectionAttempts = 0;
		await mockApi(page, {
			requests,
			connectionStatus: () => (++connectionAttempts === 1 ? failure.status : 200),
		});
		await page.addInitScript(() =>
			localStorage.setItem('hbc-chat-messages', '[{"content":"old"}]')
		);

		await page.goto('/location');
		await expect(page.getByText('Homebox connection failed')).toBeVisible();
		await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
		await page.getByRole('button', { name: 'Retry' }).click();
		await expect(page.getByRole('heading', { name: 'Select Location' })).toBeVisible();
		expect(lifecycleRequests(requests)).toHaveLength(0);
		expect(await page.evaluate(() => localStorage.getItem('hbc-chat-messages'))).toContain('old');
	});
}

test('invalid config cannot be inferred as configured-key mode', async ({ page }) => {
	const requests: Request[] = [];
	await page.route('**/api/**', async (route) => {
		requests.push(route.request());
		const path = new URL(route.request().url()).pathname;
		if (path === '/api/config')
			return route.fulfill(json({ ...config('api_key'), auth_mode: 'broken' }));
		if (path === '/api/version') {
			return route.fulfill(
				json({ version: 'test', latest_version: null, update_available: false })
			);
		}
		return route.fulfill(json({}));
	});

	await page.goto('/location');
	await expect(page.getByText('Homebox connection failed')).toBeVisible();
	await expect(page.getByText('invalid authentication configuration')).toBeVisible();
	expect(
		requests.some((request) => new URL(request.url()).pathname === '/api/homebox/connection')
	).toBe(false);
});

test('expired legacy session can sign in and recover its scoped draft', async ({ page }) => {
	const requests: Request[] = [];
	await mockApi(page, { mode: 'legacy', requests });
	await page.addInitScript(async () => {
		localStorage.setItem('hbc_token', 'expired-token');
		localStorage.setItem('hbc_token_expires', new Date(Date.now() - 60_000).toISOString());
		await new Promise<void>((resolve, reject) => {
			const open = indexedDB.open('hbc-scan-recovery', 2);
			open.onupgradeneeded = () => open.result.createObjectStore('sessions');
			open.onerror = () => reject(open.error);
			open.onsuccess = () => {
				const tx = open.result.transaction('sessions', 'readwrite');
				tx.objectStore('sessions').put(
					{ id: 'draft-1', status: 'capturing' },
					'deployment:user:g1'
				);
				tx.oncomplete = () => resolve();
				tx.onerror = () => reject(tx.error);
			};
		});
	});

	await page.goto('/');
	await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
	await page.getByLabel('Email').fill('demo@example.com');
	await page.locator('#password').fill('demo');
	await page.getByRole('button', { name: 'Sign In' }).click();
	await expect(page).toHaveURL(/\/location$/);
	const draft = await page.evaluate(async () => {
		const db = await new Promise<IDBDatabase>((resolve, reject) => {
			const open = indexedDB.open('hbc-scan-recovery', 2);
			open.onsuccess = () => resolve(open.result);
			open.onerror = () => reject(open.error);
		});
		return new Promise((resolve, reject) => {
			const request = db.transaction('sessions').objectStore('sessions').get('deployment:user:g1');
			request.onsuccess = () => resolve(request.result);
			request.onerror = () => reject(request.error);
		});
	});
	expect(draft).toMatchObject({ id: 'draft-1' });
	expect(requests.some((request) => new URL(request.url()).pathname === '/api/refresh')).toBe(
		false
	);
});

test('legacy bootstrap refreshes a rejected token once and retries connection', async ({
	page,
}) => {
	const requests: Request[] = [];
	let connectionAttempts = 0;
	await mockApi(page, {
		mode: 'legacy',
		requests,
		connectionStatus: () => (++connectionAttempts === 1 ? 401 : 200),
	});
	await page.addInitScript(() => {
		localStorage.setItem('hbc_token', 'stale-token');
		localStorage.setItem('hbc_token_expires', new Date(Date.now() + 3_600_000).toISOString());
	});

	await page.goto('/location');
	await expect(page.getByRole('heading', { name: 'Select Location' })).toBeVisible();
	const refreshes = requests.filter(
		(request) => new URL(request.url()).pathname === '/api/refresh'
	);
	expect(refreshes).toHaveLength(1);
	const connections = requests.filter(
		(request) => new URL(request.url()).pathname === '/api/homebox/connection'
	);
	expect(connections).toHaveLength(2);
	expect(connections[0].headers().authorization).toBe('Bearer stale-token');
	expect(connections[1].headers().authorization).toBe('Bearer refreshed-token');
});

test('legacy failed refresh shows the modal and reauthentication completes bootstrap', async ({
	page,
}) => {
	let connectionAttempts = 0;
	await mockApi(page, {
		mode: 'legacy',
		refreshStatus: 401,
		connectionStatus: () => (++connectionAttempts === 1 ? 401 : 200),
	});
	await page.addInitScript(() => {
		localStorage.setItem('hbc_token', 'rejected-token');
		localStorage.setItem('hbc_token_expires', new Date(Date.now() + 3_600_000).toISOString());
	});

	await page.goto('/location');
	await expect(page.getByRole('heading', { name: 'Session Expired' })).toBeVisible();
	await page.locator('#reauth-email').fill('demo@example.com');
	await page.locator('#reauth-password').fill('demo');
	await page.getByRole('button', { name: 'Sign In' }).click();
	await expect(page.getByRole('heading', { name: 'Select Location' })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Session Expired' })).toHaveCount(0);
});

test('configured-key rejection after readiness returns to the retry shell', async ({ page }) => {
	const requests: Request[] = [];
	await mockApi(page, { requests, chatStatus: 502 });
	await page.goto('/location');
	await expect(page.getByRole('heading', { name: 'Select Location' })).toBeVisible();
	await page.goto('/chat');
	await expect(page.getByText('Homebox connection failed')).toBeVisible();
	await expect(page.getByText('configured Homebox API key was rejected')).toBeVisible();
	expect(lifecycleRequests(requests)).toHaveLength(0);
	await expect(page.getByText('Session expired')).toHaveCount(0);
});

test('group switch discards a late response and preserves the old scoped draft', async ({
	page,
}) => {
	let releaseOld!: () => void;
	const oldResponse = new Promise<void>((resolve) => (releaseOld = resolve));
	await mockApi(page, {
		locationTree: async (request) => {
			if (request.headers()['x-group-id'] === 'g1') {
				await oldResponse;
				return [{ id: 'old', name: 'Old Group Location', description: '', children: [] }];
			}
			return [{ id: 'new', name: 'New Group Location', description: '', children: [] }];
		},
	});

	await page.goto('/location');
	await expect(page.getByRole('button', { name: /Personal/ })).toBeVisible();
	await page.evaluate(async () => {
		const db = await new Promise<IDBDatabase>((resolve, reject) => {
			const open = indexedDB.open('hbc-scan-recovery', 2);
			open.onupgradeneeded = () => open.result.createObjectStore('sessions');
			open.onsuccess = () => resolve(open.result);
			open.onerror = () => reject(open.error);
		});
		await new Promise<void>((resolve, reject) => {
			const tx = db.transaction('sessions', 'readwrite');
			tx.objectStore('sessions').put(
				{ id: 'old-draft', status: 'capturing' },
				'deployment:user:g1'
			);
			tx.oncomplete = () => resolve();
			tx.onerror = () => reject(tx.error);
		});
	});
	await page.getByRole('button', { name: /Personal/ }).click();
	await page.getByRole('option', { name: /Shared/ }).click();
	await expect(page.getByText('New Group Location')).toBeVisible();
	releaseOld();
	await page.waitForTimeout(100);
	await expect(page.getByText('Old Group Location')).toHaveCount(0);
	const drafts = await page.evaluate(async () => {
		const db = await new Promise<IDBDatabase>((resolve, reject) => {
			const open = indexedDB.open('hbc-scan-recovery', 2);
			open.onsuccess = () => resolve(open.result);
			open.onerror = () => reject(open.error);
		});
		return new Promise<Record<string, unknown>[]>((resolve, reject) => {
			const request = db.transaction('sessions').objectStore('sessions').getAll();
			request.onsuccess = () => resolve(request.result);
			request.onerror = () => reject(request.error);
		});
	});
	expect(drafts).toEqual([expect.objectContaining({ id: 'old-draft' })]);
});

async function chatContext(context: BrowserContext): Promise<string> {
	const page = await context.newPage();
	const requests: Request[] = [];
	await mockApi(page, { requests });
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
	return id!;
}

test('separate browsers use distinct chat contexts', async ({ browser }) => {
	const first = await browser.newContext();
	const second = await browser.newContext();
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
		await mockApi(page, { requests });
		await page.route('**/api/chat/messages', (route) =>
			failure.status === 200
				? route.fulfill({
						status: 200,
						contentType: 'text/event-stream',
						body: `event: error\ndata: ${JSON.stringify({ code: failure.code, message: 'Homebox connection failed' })}\n\nevent: done\ndata: {}\n\n`,
					})
				: route.fulfill(
						json({ code: failure.code, detail: 'Homebox connection failed' }, failure.status)
					)
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
	await mockApi(page, { mode: 'legacy' });
	await page.addInitScript(() => {
		localStorage.setItem('hbc_token', 'valid-legacy-token');
		localStorage.setItem('hbc_token_expires', new Date(Date.now() + 3_600_000).toISOString());
	});
	await page.route('**/api/chat/messages', (route) =>
		route.fulfill({
			status: 200,
			contentType: 'text/event-stream',
			body: 'event: error\ndata: {"code":"AUTH_FAILED","message":"Session expired"}\n\nevent: done\ndata: {}\n\n',
		})
	);
	await page.goto('/chat');
	await page.getByLabel('Chat message input').fill('List locations');
	await page.getByRole('button', { name: 'Send message' }).click();
	await expect(page.getByRole('heading', { name: 'Session Expired' })).toBeVisible();
});
