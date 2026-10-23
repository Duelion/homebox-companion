import { expect, test } from './fixtures/test';
import { createdItem, detectedItems, fieldPreferences } from './fixtures/data';
import { json } from './fixtures/api';
import {
	analyzePhotos,
	confirmItems,
	selectLocation,
	submitItems,
	uploadPhoto,
} from './helpers/scan';

for (const [label, tags] of [
	['omitted', undefined],
	['null', null],
	['empty', []],
	['duplicates and invalid', ['general', 'general', 'invalid']],
] as const) {
	test(`correction preserves selected default tags with ${label} suggestions`, async ({
		page,
		api,
	}) => {
		api.on('GET', '/api/tags', () =>
			json([
				{ id: 'default', name: 'Verified' },
				{ id: 'general', name: 'General' },
			])
		);
		api.on('GET', '/api/settings/field-preferences', () =>
			json({ ...fieldPreferences(), default_tag_id: 'default' })
		);
		api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Lamp'])));
		api.on('POST', '/api/tools/vision/correct', () =>
			json({ items: [{ name: 'Corrected lamp', quantity: 2, tag_ids: tags }] })
		);
		api.on('POST', '/api/items', () => json(createdItem('saved', 'Corrected lamp')));
		api.on('POST', '/api/items/saved/attachments', () => json({}));
		await selectLocation(page);
		await uploadPhoto(page);
		await analyzePhotos(page);
		await expect(page.getByRole('button', { name: 'Verified', exact: true })).toHaveAttribute(
			'aria-pressed',
			'true'
		);
		await page.getByRole('button', { name: 'AI Correction', exact: true }).click();
		await page.getByPlaceholder(/The brand is Sony/).fill('Correct the name');
		await page.getByRole('button', { name: 'Correct with AI', exact: true }).click();
		await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Corrected lamp');
		await expect(page.getByRole('button', { name: 'Verified', exact: true })).toHaveAttribute(
			'aria-pressed',
			'true'
		);
		await confirmItems(page, 1);
		await submitItems(page);
		await expect(page).toHaveURL(/\/success$/);
		const submission = api.requests.find(
			(request) => request.method() === 'POST' && new URL(request.url()).pathname === '/api/items'
		);
		expect(submission?.postDataJSON().items[0].tag_ids).toEqual(
			label === 'duplicates and invalid' ? ['default', 'general'] : ['default']
		);
	});
}

test('correction respects manually removed default and discards late responses after navigation', async ({
	page,
	api,
}) => {
	api.on('GET', '/api/tags', () => json([{ id: 'default', name: 'Verified' }]));
	api.on('GET', '/api/settings/field-preferences', () =>
		json({ ...fieldPreferences(), default_tag_id: 'default' })
	);
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Lamp', 'Chair'])));
	api.on('POST', '/api/tools/vision/correct', () => json(detectedItems(['Corrected lamp'])));
	api.on('POST', '/api/items/saved/attachments', () => json({}));
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByRole('button', { name: 'Verified', exact: true }).click();
	await page.getByRole('button', { name: 'AI Correction', exact: true }).click();
	await page.getByPlaceholder(/The brand is Sony/).fill('Correct the name');
	await page.getByRole('button', { name: 'Correct with AI', exact: true }).click();
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Corrected lamp');
	await expect(page.getByRole('button', { name: 'Verified', exact: true })).toHaveAttribute(
		'aria-pressed',
		'false'
	);
	const gate = api.gate();
	let correcting = false;
	api.on('POST', '/api/tools/vision/correct', async () => {
		correcting = true;
		await gate.promise;
		return json(detectedItems(['Obsolete']));
	});
	await page.getByRole('button', { name: 'AI Correction', exact: true }).click();
	await page.getByPlaceholder(/The brand is Sony/).fill('Delayed correction');
	await page.getByRole('button', { name: 'Correct with AI', exact: true }).click();
	await expect.poll(() => correcting).toBe(true);
	const cancelled = page.waitForEvent(
		'requestfailed',
		(request) => new URL(request.url()).pathname === '/api/tools/vision/correct'
	);
	await page.getByRole('link', { name: 'Settings', exact: true }).click();
	await cancelled;
	gate.release();
	await page.getByRole('link', { name: 'Scan', exact: true }).click();
	await expect(page).toHaveURL(/\/review$/);
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Corrected lamp');
	await expect(page.getByRole('button', { name: 'Verified', exact: true })).toHaveAttribute(
		'aria-pressed',
		'false'
	);
});

test('metadata failure preserves draft tags without accepting unverified suggestions', async ({
	page,
	api,
}) => {
	api.allowPageError(/metadata unavailable/);
	api.on('GET', '/api/tags', () => json({ detail: 'metadata unavailable' }, 500));
	api.on('POST', '/api/tools/vision/detect', () =>
		json({ items: [{ name: 'Lamp', quantity: 1, tag_ids: ['existing'] }] })
	);
	api.on('POST', '/api/tools/vision/correct', () =>
		json({ items: [{ name: 'Corrected lamp', quantity: 1, tag_ids: ['unverified'] }] })
	);
	api.on('POST', '/api/items', () => json(createdItem('saved')));
	api.on('POST', '/api/items/saved/attachments', () => json({}));
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByRole('button', { name: 'AI Correction', exact: true }).click();
	await page.getByPlaceholder(/The brand is Sony/).fill('Correct the name');
	await page.getByRole('button', { name: 'Correct with AI', exact: true }).click();
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Corrected lamp');
	await confirmItems(page, 1);
	await submitItems(page);
	await expect(page).toHaveURL(/\/success$/);
	const submission = api.requests.find(
		(request) => request.method() === 'POST' && new URL(request.url()).pathname === '/api/items'
	);
	expect(submission?.postData()).toContain('existing');
	expect(submission?.postData()).not.toContain('unverified');
});
