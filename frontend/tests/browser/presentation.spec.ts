import type { Page } from '@playwright/test';
import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { createdItem, detectedItems } from './fixtures/data';
import {
	selectLocation,
	uploadPhoto,
	analyzePhotos,
	confirmItems,
	submitItems,
} from './helpers/scan';

test.beforeEach(async ({ api, page }) => {
	await page.clock.setFixedTime(new Date('2026-10-01T12:00:00Z'));
	api.on('POST', '/api/tools/vision/detect', () =>
		json(detectedItems(['Desk tools', 'Storage box']))
	);
	let created = 0;
	api.on('POST', '/api/items', () => json(createdItem(`item-${++created}`)));
	api.on('POST', /^\/api\/items\/[^/]+\/attachments$/, () => json({}));
});

async function reviewItems(page: Page) {
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Desk tools');
}

async function openConfirmAll(page: Page) {
	const confirm = page.getByRole('button', { name: 'Confirm', exact: true });
	await confirm.focus();
	await confirm.hover();
	await page.mouse.down();
	try {
		// Holding is the actual user gesture; wait for its outcome rather than a fixed delay.
		await expect(page.getByRole('heading', { name: 'Confirm All Remaining Items' })).toBeVisible();
	} finally {
		await page.mouse.up();
	}
	return page.getByRole('dialog', { name: 'Confirm All Remaining Items' });
}

async function renderReady(page: Page) {
	await page.evaluate(async () => {
		await document.fonts.ready;
		await Promise.all(Array.from(document.images, (image) => image.decode().catch(() => {})));
	});
}

test('confirm-all dialog contains keyboard focus and returns it when cancelled', async ({
	page,
}) => {
	await reviewItems(page);
	const dialog = await openConfirmAll(page);
	await expect(dialog).toBeVisible();
	await expect(dialog.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused();
	await page.keyboard.press('Shift+Tab');
	await expect(dialog.getByRole('button', { name: 'Confirm All', exact: true })).toBeFocused();
	await page.keyboard.press('Tab');
	await expect(dialog.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused();
	await page.keyboard.press('Escape');
	await expect(dialog).not.toBeVisible();
	await expect(page.getByRole('button', { name: 'Confirm', exact: true })).toBeFocused();
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Desk tools');
});

test('main scan actions remain usable on a phone @mobile', async ({ page }) => {
	await reviewItems(page);
	await page.getByLabel('Name', { exact: true }).fill('Travel tools');
	await confirmItems(page, 2);
	await expect(page.getByText('Travel tools', { exact: true })).toBeVisible();
	await submitItems(page);
	await expect(page.getByRole('heading', { name: 'Success!' })).toBeVisible();
});

test('thumbnail editing remains discoverable on a touch tablet @mobile', async ({ page }) => {
	await page.setViewportSize({ width: 1024, height: 768 });
	await reviewItems(page);
	const edit = page.getByRole('button', { name: 'Edit thumbnail image' });
	await expect(edit).toHaveCSS('opacity', '1');
	await edit.tap();
	await expect(page.getByRole('heading', { name: 'Edit Thumbnail', exact: true })).toBeVisible();
});

for (const [layout, viewport] of [
	['desktop', { width: 1280, height: 900 }],
	['mobile', { width: 390, height: 844 }],
] as const) {
	test(`review, summary${layout === 'desktop' ? ', and confirmation dialog' : ''} ${layout} @visual`, async ({
		page,
	}) => {
		await page.setViewportSize(viewport);
		await reviewItems(page);
		await renderReady(page);
		await expect(page).toHaveScreenshot(`review-${layout}.png`, { animations: 'disabled' });
		if (layout === 'desktop') {
			const dialog = await openConfirmAll(page);
			await expect(dialog).toBeVisible();
			await expect(page).toHaveScreenshot('confirm-all-desktop.png', { animations: 'disabled' });
			await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
		}
		await confirmItems(page, 2);
		await renderReady(page);
		await expect(page).toHaveScreenshot(`summary-${layout}.png`, { animations: 'disabled' });
	});
}
