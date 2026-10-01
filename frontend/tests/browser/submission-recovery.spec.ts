import { type Page } from '@playwright/test';
import { test, expect } from './fixtures/test';
import { installApi, json } from './fixtures/api';
import { detectedItems, createdItem, rejectedItem, incompleteItem } from './fixtures/data';
import { seedLegacySession } from './fixtures/auth';
import {
	selectLocation,
	uploadPhoto,
	analyzePhotos,
	confirmItems,
	submitItems,
} from './helpers/scan';

interface Submission {
	name: string;
}

async function openSummary(
	page: Page,
	itemNames: string[],
	submissions: Submission[],
	options: {
		authMode?: 'legacy' | 'api_key';
		selectedGroupId?: string;
		rejectedItems?: string[];
		expireOnItem?: string;
		incompleteItem?: string;
		failedUploadCleanup?: boolean;
		operations?: string[];
	} = {}
) {
	const api = await installApi(page.context());
	api.setAuthMode(options.authMode ?? 'api_key');
	if (options.authMode === 'legacy') {
		await seedLegacySession(page, 'valid-token', options.selectedGroupId);
	}
	if (options.operations) {
		page.on('request', (request) => {
			const path = new URL(request.url()).pathname;
			if (path.startsWith('/api/')) options.operations?.push(`${request.method()} ${path}`);
		});
	}
	if (options.selectedGroupId) {
		api.on('GET', '/api/groups', () =>
			json([
				{ id: 'g1', name: 'Personal' },
				{ id: options.selectedGroupId!, name: 'Shared' },
			])
		);
	}
	if (options.authMode === 'legacy') {
		api.on('POST', '/api/refresh', () => json({ detail: 'Session expired' }, 401));
	}
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(itemNames)));
	let expired = false;
	api.on('POST', '/api/items', (request) => {
		const name = request.postDataJSON().items[0].name as string;
		submissions.push({ name });
		if (name === options.expireOnItem && !expired) {
			expired = true;
			return json({ detail: 'Session expired' }, 401);
		}
		if (options.rejectedItems?.includes(name)) {
			return json(rejectedItem(name), 207);
		}
		if (name === options.incompleteItem) {
			return json(incompleteItem(`created-${submissions.length}`, name), 207);
		}
		return json(createdItem(`created-${submissions.length}`, name));
	});
	api.on('POST', /^\/api\/items\/[^/]+\/attachments$/, () =>
		options.failedUploadCleanup ? json({ detail: 'Upload failed' }, 400) : json({})
	);
	api.on('DELETE', /^\/api\/items\/[^/]+$/, () =>
		options.failedUploadCleanup
			? json({ detail: 'Cleanup failed' }, 400)
			: json({ message: 'deleted' })
	);
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await confirmItems(page, itemNames.length);
	await submitItems(page);
}
test('edits and retries a single failed item with its photo', async ({ page }) => {
	const submissions: Submission[] = [];
	await openSummary(page, ['Bad lamp'], submissions, { rejectedItems: ['Bad lamp'] });

	await page.getByRole('button', { name: 'Edit failed item Bad lamp' }).click();
	await page.getByLabel('Name').fill('Fixed lamp');
	await page.getByRole('button', { name: 'Save Changes' }).click();
	await expect(page).toHaveURL(/\/summary$/);
	await expect(page.getByRole('img', { name: 'Fixed lamp' })).toBeVisible();
	await page.getByRole('button', { name: 'Retry Failed Items' }).click();

	expect(submissions.map(({ name }) => name)).toEqual(['Bad lamp', 'Fixed lamp']);
	await expect(page).toHaveURL(/\/success$/);
});

test('mixed batch retries only the corrected failure', async ({ page }) => {
	const submissions: Submission[] = [];
	await openSummary(page, ['Good chair', 'Bad table'], submissions, {
		rejectedItems: ['Bad table'],
	});

	await page.getByRole('button', { name: 'Edit failed item Bad table' }).click();
	await page.getByLabel('Name').fill('Fixed table');
	await page.getByRole('button', { name: 'Save Changes' }).click();
	await page.getByRole('button', { name: 'Retry Failed Items' }).click();

	expect(submissions.map(({ name }) => name)).toEqual(['Good chair', 'Bad table', 'Fixed table']);
	await expect(page).toHaveURL(/\/success$/);
});

test('post-create auth failure is visible and cannot be retried as a new item', async ({
	page,
}) => {
	const submissions: Submission[] = [];
	const operations: string[] = [];
	await openSummary(page, ['Incomplete lamp'], submissions, {
		incompleteItem: 'Incomplete lamp',
		operations,
	});
	await expect(page.getByRole('heading', { name: 'Items need attention' })).toBeVisible();
	await expect(
		page.getByText(/some details were not saved and photos were not uploaded/)
	).toBeVisible();
	await expect(page.getByRole('button', { name: 'Retry Failed Items' })).toHaveCount(0);
	expect(operations.filter((op) => op.includes('/attachments') || op.startsWith('DELETE'))).toEqual(
		[]
	);
	expect(submissions).toEqual([{ name: 'Incomplete lamp' }]);
});

for (const reload of [false, true]) {
	test(`mixed batch protects completed and incomplete items on retry, reload=${reload}`, async ({
		page,
		api,
	}) => {
		if (reload) api.allowPageError(/^navigation aborted$/);
		const submissions: Submission[] = [];
		await openSummary(page, ['Good chair', 'Incomplete lamp', 'Bad table'], submissions, {
			incompleteItem: 'Incomplete lamp',
			rejectedItems: ['Bad table'],
		});
		await expect(page.getByRole('button', { name: 'Retry Failed Items' })).toBeVisible();
		if (reload) {
			await page.reload();
			await page.getByRole('button', { name: 'Resume Session' }).click();
		}
		await expect(page.getByRole('button', { name: 'Submit All Items' })).toHaveCount(0);
		await page.getByRole('button', { name: 'Edit failed item Bad table' }).click();
		await page.getByLabel('Name').fill('Fixed table');
		await page.getByRole('button', { name: 'Save Changes' }).click();
		await page.getByRole('button', { name: 'Retry Failed Items' }).click();
		await expect(page.getByRole('heading', { name: 'Items need attention' })).toBeVisible();
		expect(submissions.map(({ name }) => name)).toEqual([
			'Good chair',
			'Incomplete lamp',
			'Bad table',
			'Fixed table',
		]);
	});
}

test('failed primary-photo cleanup is an incomplete item, not a retryable create', async ({
	page,
}) => {
	const submissions: Submission[] = [];
	const operations: string[] = [];
	await openSummary(page, ['Created lamp'], submissions, { failedUploadCleanup: true, operations });
	await expect(page.getByRole('heading', { name: 'Items need attention' })).toBeVisible();
	await expect(
		page.getByText(/Image upload failed and item deletion could not be confirmed/)
	).toBeVisible();
	expect(operations.filter((op) => op.startsWith('DELETE'))).toEqual([
		'DELETE /api/items/created-1',
	]);
	expect(submissions).toEqual([{ name: 'Created lamp' }]);
});

test('back cancels a failed-item edit without losing the original row', async ({ page, api }) => {
	api.allowPageError(/^(navigation aborted|Transition was skipped\. New ViewTransition started)$/);
	const submissions: Submission[] = [];
	await openSummary(page, ['Bad camera'], submissions, { rejectedItems: ['Bad camera'] });

	await page.getByRole('button', { name: 'Edit failed item Bad camera' }).click();
	await page.getByLabel('Name').fill('Discarded change');
	await page.getByRole('link', { name: 'Back to Summary' }).click();

	await expect(page).toHaveURL(/\/summary$/);
	await expect(page.getByText('Bad camera', { exact: true })).toBeVisible();
	await expect(page.getByText('Discarded change', { exact: true })).toHaveCount(0);
	expect(submissions.map(({ name }) => name)).toEqual(['Bad camera']);
});

test('reload during a failed-item edit recovers the unchanged summary', async ({ page, api }) => {
	api.allowPageError(/^navigation aborted$/);
	const submissions: Submission[] = [];
	await openSummary(page, ['Bad monitor'], submissions, { rejectedItems: ['Bad monitor'] });

	await page.getByRole('button', { name: 'Edit failed item Bad monitor' }).click();
	await page.getByLabel('Name').fill('Unsaved monitor');
	await page.reload();

	await expect(page).toHaveURL(/\/location$/);
	await page.getByRole('button', { name: 'Resume Session' }).click();
	await expect(page).toHaveURL(/\/summary$/);
	await expect(page.getByText('Bad monitor', { exact: true })).toBeVisible();
	await expect(page.getByText('Unsaved monitor', { exact: true })).toHaveCount(0);
});

test('native browser back cancels editing and a new scan does not reuse its index', async ({
	page,
}) => {
	const submissions: Submission[] = [];
	await openSummary(page, ['Bad speaker'], submissions, { rejectedItems: ['Bad speaker'] });

	await page.getByRole('button', { name: 'Edit failed item Bad speaker' }).click();
	await page.getByLabel('Name').fill('Unsaved speaker');
	await page.goBack();

	await expect(page).toHaveURL(/\/summary$/);
	await expect(page.getByText('Bad speaker', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Continue with Successful Items' }).click();
	await expect(page).toHaveURL(/\/success$/);
	await page.getByRole('button', { name: /Scan More Items/ }).click();
	await expect(page).toHaveURL(/\/capture$/);
});

test('same-account reauthentication preserves successful rows and the selected collection', async ({
	page,
}) => {
	const submissions: Submission[] = [];
	const submittedGroups: string[] = [];
	page.on('request', (request) => {
		if (new URL(request.url()).pathname === '/api/items' && request.method() === 'POST') {
			submittedGroups.push(request.headers()['x-group-id']);
		}
	});
	await openSummary(page, ['Good chair', 'Later table', 'Pending lamp'], submissions, {
		authMode: 'legacy',
		selectedGroupId: 'g2',
		expireOnItem: 'Later table',
	});
	await expect(page.getByRole('heading', { name: 'Session Expired' })).toBeVisible();
	await page.locator('#reauth-email').fill('same@example.com');
	await page.locator('#reauth-password').fill('password');
	await page.getByRole('button', { name: 'Sign In', exact: true }).click();

	await expect(page.getByRole('button', { name: 'Retry Failed Items' })).toBeVisible();
	await expect(page).toHaveURL(/\/summary$/);
	await expect(page.getByRole('button', { name: /Shared/ })).toBeVisible();
	await expect(page.getByRole('button', { name: /Submit All Items/ })).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Resume Session' })).toHaveCount(0);
	await page.getByRole('button', { name: 'Retry Failed Items' }).click();
	await expect(page).toHaveURL(/\/success$/);
	expect(submissions.map(({ name }) => name)).toEqual([
		'Good chair',
		'Later table',
		'Later table',
		'Pending lamp',
	]);
	expect(submittedGroups).toEqual(['g2', 'g2', 'g2', 'g2']);
});

for (const identityChanged of [true, false]) {
	test(`connection retry clears old scan and caches when ${identityChanged ? 'identity' : 'collection membership'} changes`, async ({
		page,
	}) => {
		const submissions: Submission[] = [];
		await openSummary(page, ['Bad private inventory'], submissions, {
			rejectedItems: ['Bad private inventory'],
		});
		await expect(page.getByRole('button', { name: 'Retry Failed Items' })).toBeVisible();
		const api = await installApi(page.context());
		api.on('GET', '/api/chat/status', () =>
			json({ detail: 'Rejected key', code: 'HOMEBOX_API_KEY_REJECTED' }, 502)
		);
		await page.locator('a[href="/chat"]').first().click();
		await expect(page.getByRole('button', { name: 'Retry', exact: true })).toBeVisible();
		api.on('GET', '/api/homebox/connection', () =>
			json({
				connected: true,
				context_id: identityChanged ? 'deployment:other-user' : 'deployment:user',
				user_id: identityChanged ? 'other-user' : 'user-1',
				default_group_id: 'g2',
			})
		);
		api.on('GET', '/api/groups', () => json([{ id: 'g2', name: 'New collection' }]));
		api.on('GET', '/api/locations/tree', () =>
			json([{ id: 'new-location', name: 'New location', children: [] }])
		);
		api.on('GET', '/api/chat/status', () => json({ session_id: 'new-session', message_count: 0 }));
		await page.getByRole('button', { name: 'Retry', exact: true }).click();
		await expect(page.getByLabel('Chat message input')).toBeVisible();
		await page.locator('a[href="/location"]').first().click();
		await expect(page.getByRole('heading', { name: 'Select Location' })).toBeVisible();
		await expect(page.getByRole('button', { name: /New location/ })).toBeVisible();
		await expect(page.getByRole('button', { name: /Storage/ })).toHaveCount(0);
		await expect(page.getByText('Bad private inventory', { exact: true })).toHaveCount(0);
		await expect(page.getByRole('button', { name: 'Resume Session' })).toHaveCount(0);
		expect(submissions.map(({ name }) => name)).toEqual(['Bad private inventory']);
	});
}
