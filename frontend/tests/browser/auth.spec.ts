import { type Request } from '@playwright/test';
import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { config } from './fixtures/data';
import { mockApi, lifecycleRequests } from './fixtures/auth-api';
import { readDrafts, seedDraftOnce } from './helpers/recovery';

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
	const api = await mockApi(page, { requests });
	api.on('GET', '/api/config', () => json({ ...config('api_key'), auth_mode: 'broken' }));

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
	await page.addInitScript(() => {
		localStorage.setItem('hbc_token', 'expired-token');
		localStorage.setItem('hbc_token_expires', new Date(Date.now() - 60_000).toISOString());
	});
	await seedDraftOnce(page, 'deployment:user:g1', { id: 'draft-1', status: 'capturing' });

	await page.goto('/');
	await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
	await page.getByLabel('Email').fill('demo@example.com');
	await page.locator('#password').fill('demo');
	await page.getByRole('button', { name: 'Sign In' }).click();
	await expect(page).toHaveURL(/\/location$/);
	expect(await readDrafts(page)).toEqual([expect.objectContaining({ id: 'draft-1' })]);
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

test('signed-out legacy deep link still redirects to login', async ({ page }) => {
	await mockApi(page, { mode: 'legacy' });
	await page.goto('/location');
	await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
	await expect(page).toHaveURL('/');
});

for (const delayedErrorBody of [false, true]) {
	test(`legacy failed refresh completes reauthentication without leaving the deep link, delayed body=${delayedErrorBody}`, async ({
		page,
	}) => {
		const navigations: string[] = [];
		page.on('framenavigated', (frame) => {
			if (frame === page.mainFrame()) navigations.push(new URL(frame.url()).pathname);
		});
		let releaseErrorBody!: () => void;
		if (delayedErrorBody) {
			const errorBodyGate = new Promise<void>((resolve) => (releaseErrorBody = resolve));
			await page.exposeFunction('waitForConnectionError', () => errorBodyGate);
			await page.addInitScript(() => {
				const originalText = Response.prototype.text;
				Response.prototype.text = async function () {
					if (this.status === 401 && new URL(this.url).pathname === '/api/homebox/connection') {
						await (
							window as unknown as { waitForConnectionError: () => Promise<void> }
						).waitForConnectionError();
					}
					return originalText.call(this);
				};
			});
		}
		const requests: Request[] = [];
		let connectionAttempts = 0;
		await mockApi(page, {
			mode: 'legacy',
			requests,
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
		if (delayedErrorBody) {
			// Keep the expired phase active until the modal is usable, then finish bootstrap.
			const bootstrapFinished = page.waitForResponse('**/api/version');
			releaseErrorBody();
			await bootstrapFinished;
		}
		await page.locator('#reauth-password').fill('demo');
		await page.getByRole('button', { name: 'Sign In' }).click();
		await expect(page.getByRole('heading', { name: 'Select Location' })).toBeVisible();
		await expect(page.getByRole('heading', { name: 'Session Expired' })).toHaveCount(0);
		expect([...new Set(navigations)]).toEqual(['/location']);
		const login = requests.find((request) => new URL(request.url()).pathname === '/api/login');
		expect(login?.postDataJSON()).toEqual({ username: 'demo@example.com', password: 'demo' });
	});
}

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
