import { expect, test, type Page } from '@playwright/test';

const json = (body: unknown, status = 200) => ({
	status,
	contentType: 'application/json',
	body: JSON.stringify(body),
});

interface Submission {
	name: string;
}

async function openSummary(page: Page, itemNames: string[], submissions: Submission[]) {
	await page.route('**/api/**', async (route) => {
		const request = route.request();
		const path = new URL(request.url()).pathname;
		if (path === '/api/config') {
			return route.fulfill(
				json({
					auth_mode: 'api_key',
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
				})
			);
		}
		if (path === '/api/homebox/connection') {
			return route.fulfill(
				json({
					connected: true,
					context_id: 'deployment:user',
					user_id: 'user-1',
					default_group_id: 'g1',
				})
			);
		}
		if (path === '/api/groups') return route.fulfill(json([{ id: 'g1', name: 'Personal' }]));
		if (path === '/api/locations/tree') {
			return route.fulfill(json([{ id: 'loc-1', name: 'Storage', itemCount: 0, children: [] }]));
		}
		if (path === '/api/locations/loc-1') {
			return route.fulfill(json({ id: 'loc-1', name: 'Storage', itemCount: 0, children: [] }));
		}
		if (path === '/api/tags') return route.fulfill(json([]));
		if (path === '/api/version') {
			return route.fulfill(
				json({ version: 'test', latest_version: null, update_available: false })
			);
		}
		if (path === '/api/field-preferences') return route.fulfill(json({ default_tag_id: null }));
		if (path === '/api/tools/vision/detect') {
			return route.fulfill(
				json({
					items: itemNames.map((name) => ({ name, quantity: 1, description: `${name} photo` })),
					compressed_images: [],
				})
			);
		}
		if (path === '/api/items' && request.method() === 'POST') {
			const name = request.postDataJSON().items[0].name as string;
			submissions.push({ name });
			if (name.startsWith('Bad')) {
				return route.fulfill(json({ created: [], errors: [`${name} rejected`] }, 207));
			}
			return route.fulfill(
				json({ created: [{ id: `created-${submissions.length}` }], errors: [] })
			);
		}
		if (/\/api\/items\/[^/]+\/attachments$/.test(path)) return route.fulfill(json({}));
		return route.fulfill(json({}));
	});

	await page.goto('/location');
	await page.getByRole('button', { name: /Storage/ }).click();
	await page.getByRole('button', { name: 'Select current location' }).click();
	await page.getByRole('button', { name: 'Continue to Capture' }).click();
	await page
		.locator('input[type="file"]')
		.first()
		.setInputFiles({
			name: 'item.png',
			mimeType: 'image/png',
			buffer: Buffer.from(
				'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
				'base64'
			),
		});
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await expect(page).toHaveURL(/\/review$/);
	for (let index = 0; index < itemNames.length; index++) {
		await page.getByRole('button', { name: 'Confirm' }).click();
	}
	await expect(page).toHaveURL(/\/summary$/);
	await page.getByRole('button', { name: /Submit All Items/ }).click();
}

test('edits and retries a single failed item with its photo', async ({ page }) => {
	const submissions: Submission[] = [];
	await openSummary(page, ['Bad lamp'], submissions);

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
	await openSummary(page, ['Good chair', 'Bad table'], submissions);

	await page.getByRole('button', { name: 'Edit failed item Bad table' }).click();
	await page.getByLabel('Name').fill('Fixed table');
	await page.getByRole('button', { name: 'Save Changes' }).click();
	await page.getByRole('button', { name: 'Retry Failed Items' }).click();

	expect(submissions.map(({ name }) => name)).toEqual(['Good chair', 'Bad table', 'Fixed table']);
	await expect(page).toHaveURL(/\/success$/);
});

test('back cancels a failed-item edit without losing the original row', async ({ page }) => {
	const submissions: Submission[] = [];
	await openSummary(page, ['Bad camera'], submissions);

	await page.getByRole('button', { name: 'Edit failed item Bad camera' }).click();
	await page.getByLabel('Name').fill('Discarded change');
	await page.getByRole('link', { name: 'Back to Summary' }).click();

	await expect(page).toHaveURL(/\/summary$/);
	await expect(page.getByText('Bad camera', { exact: true })).toBeVisible();
	await expect(page.getByText('Discarded change', { exact: true })).toHaveCount(0);
	expect(submissions.map(({ name }) => name)).toEqual(['Bad camera']);
});

test('reload during a failed-item edit recovers the unchanged summary', async ({ page }) => {
	const submissions: Submission[] = [];
	await openSummary(page, ['Bad monitor'], submissions);

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
	await openSummary(page, ['Bad speaker'], submissions);

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
