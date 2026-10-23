import { test, expect } from './fixtures/test';
import { fileURLToPath } from 'node:url';
import { selectLocation } from './helpers/scan';
import { json } from './fixtures/api';
import { config } from './fixtures/data';

const photo = fileURLToPath(
	new URL('../../../tests/assets/single_item_single_image.jpg', import.meta.url)
);
const invalidImageMessage =
	'Invalid or unsupported image. Choose a JPEG, PNG, WebP, GIF or HEIC/HEIF photo.';
const invalid = {
	name: 'not-an-image.jpg',
	mimeType: 'image/jpeg',
	buffer: Buffer.from('not an image'),
};

for (const suffix of ['', ' @mobile']) {
	test(`invalid primary and additional photos never enter capture and valid retry works${suffix}`, async ({
		page,
	}) => {
		await selectLocation(page);
		await page.locator('input[type="file"]').first().setInputFiles(invalid);
		await expect(
			page.getByRole('alert').getByText(invalidImageMessage, { exact: true })
		).toBeVisible();
		await page.getByRole('alert').getByRole('button', { name: 'Dismiss notification' }).click();
		await expect(page.getByRole('alert')).toHaveCount(0);
		await expect(page.getByAltText('Captured 1', { exact: true })).toHaveCount(0);
		await expect(page.getByRole('button', { name: 'Analyze with AI' })).toBeDisabled();
		await page.locator('input[type="file"]').first().setInputFiles(photo);
		await expect(page.getByAltText('Captured 1', { exact: true })).toBeVisible();
		await expect(page.getByRole('button', { name: 'Analyze with AI' })).toBeEnabled();
		await page.getByRole('button', { name: 'Expand options' }).click();
		const additional = page.locator('input[type="file"]').first();
		await additional.setInputFiles(invalid);
		await expect(page.getByText('Image Count: 1', { exact: true })).toBeVisible();
		await expect(
			page.getByRole('alert').getByText(invalidImageMessage, { exact: true })
		).toBeVisible();
		await additional.setInputFiles(photo);
		await expect(page.getByText('Image Count: 2', { exact: true })).toBeVisible();
	});
}

test('a late decode cannot add a photo to a removed item', async ({ page }) => {
	await selectLocation(page);
	await page.locator('input[type="file"]').first().setInputFiles(photo);
	await expect(page.getByAltText('Captured 1', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Expand options' }).click();
	await page.evaluate(() => {
		const original = window.createImageBitmap.bind(window);
		let release!: () => void;
		const gate = new Promise<void>((resolve) => (release = resolve));
		Object.assign(window, { releaseImageValidation: release });
		window.createImageBitmap = (async (...args: Parameters<typeof createImageBitmap>) => {
			Object.assign(window, { imageValidationStarted: true });
			await gate;
			const bitmap = await original(...args);
			Object.assign(window, { imageValidationFinished: true });
			return bitmap;
		}) as typeof createImageBitmap;
	});
	await page.locator('input[type="file"]').first().setInputFiles(photo);
	await expect
		.poll(() =>
			page.evaluate(
				() => (window as unknown as { imageValidationStarted?: boolean }).imageValidationStarted
			)
		)
		.toBe(true);
	await page.getByRole('button', { name: 'Remove image', exact: true }).click();
	await page.evaluate(() =>
		(window as unknown as { releaseImageValidation: () => void }).releaseImageValidation()
	);
	await expect
		.poll(() =>
			page.evaluate(
				() => (window as unknown as { imageValidationFinished?: boolean }).imageValidationFinished
			)
		)
		.toBe(true);
	await expect(page.getByAltText('Captured 1', { exact: true })).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Analyze with AI' })).toBeDisabled();
});

test('async primary and additional batches cannot exceed the total image limit', async ({
	page,
	api,
}) => {
	api.on('GET', '/api/config', () => json({ ...config(), capture_max_images: 30 }));
	await selectLocation(page);
	const tiny = {
		name: 'tiny.png',
		mimeType: 'image/png',
		buffer: Buffer.from(
			'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC',
			'base64'
		),
	};
	await page.locator('input[type="file"]').first().setInputFiles(tiny);
	await expect(page.getByAltText('Captured 1', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Expand options' }).click();
	await page
		.locator('input[type="file"]')
		.first()
		.setInputFiles(Array.from({ length: 30 }, () => tiny));
	await expect(page.getByText('Image Count: 30', { exact: true })).toBeVisible();
	await expect(
		page.getByRole('alert').getByText('Maximum 30 images allowed', { exact: true })
	).toBeVisible();
	await page.locator('input[type="file"]').nth(-2).setInputFiles(tiny);
	await expect(page.getByAltText('Captured 2', { exact: true })).toHaveCount(0);
});
