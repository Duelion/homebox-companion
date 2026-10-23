import { expect, test } from './fixtures/test';
import { json } from './fixtures/api';
import { detectedItems } from './fixtures/data';
import { selectLocation, analyzePhotos } from './helpers/scan';

declare global {
	interface Window {
		thumbnailImageGate: {
			holdNext: boolean;
			release?: () => void;
			fail?: () => void;
		};
	}
}

test('thumbnail source loading blocks Save, supports retry, and exports the selected image', async ({
	page,
	api,
}) => {
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Lamp'])));
	await selectLocation(page);
	const photos = await page.evaluate(() => {
		return ['red', 'blue'].map((color) => {
			const canvas = document.createElement('canvas');
			canvas.width = canvas.height = 300;
			const ctx = canvas.getContext('2d')!;
			ctx.fillStyle = color;
			ctx.fillRect(0, 0, 300, 300);
			return canvas.toDataURL('image/png').split(',')[1];
		});
	});
	await page
		.locator('input[type="file"]')
		.first()
		.setInputFiles({
			name: 'first-red.png',
			mimeType: 'image/png',
			buffer: Buffer.from(photos[0], 'base64'),
		});
	await analyzePhotos(page);
	await page
		.locator('input[type="file"]')
		.first()
		.setInputFiles({
			name: 'second-blue.png',
			mimeType: 'image/png',
			buffer: Buffer.from(photos[1], 'base64'),
		});
	await page.evaluate(() => {
		const NativeImage = window.Image;
		window.thumbnailImageGate = { holdNext: false };
		Object.defineProperty(window, 'Image', {
			configurable: true,
			value: class extends NativeImage {
				get src() {
					return super.src;
				}
				set src(value: string) {
					const gate = window.thumbnailImageGate;
					if (!gate.holdNext) {
						super.src = value;
						return;
					}
					gate.holdNext = false;
					gate.release = () => {
						super.src = value;
					};
					gate.fail = () => this.dispatchEvent(new Event('error'));
				}
			},
		});
	});
	await page.getByRole('button', { name: 'Edit thumbnail image' }).click();
	const dialog = page.getByRole('dialog', { name: 'Edit Thumbnail', exact: true });
	const save = dialog.getByRole('button', { name: 'Save Thumbnail', exact: true });
	await expect(save).toBeEnabled();
	await page.evaluate(() => {
		window.thumbnailImageGate.holdNext = true;
	});
	await dialog.getByRole('button', { name: /Image 2/ }).click();
	await expect(dialog.getByRole('status')).toHaveText('Loading image...');
	await expect(save).toBeDisabled();
	await expect(dialog.getByRole('button', { name: 'Rotate 90° right' })).toBeDisabled();
	await page.evaluate(() => window.thumbnailImageGate.fail?.());
	await expect(dialog.getByRole('alert')).toContainText('Unable to load this image');
	await expect(save).toBeDisabled();
	await page.evaluate(() => {
		window.thumbnailImageGate.holdNext = true;
	});
	await dialog.getByRole('button', { name: 'Retry image', exact: true }).click();
	await expect(dialog.getByRole('status')).toHaveText('Loading image...');
	await page.evaluate(() => window.thumbnailImageGate.release?.());
	await expect(save).toBeEnabled();
	await dialog.getByRole('button', { name: 'Rotate 90° right' }).click();
	await save.click();
	await expect(dialog).toBeHidden();
	const pixel = await page
		.getByRole('img', { name: 'Lamp', exact: true })
		.evaluate(async (element) => {
			const image = element as HTMLImageElement;
			await image.decode();
			const canvas = document.createElement('canvas');
			canvas.width = canvas.height = 1;
			const ctx = canvas.getContext('2d')!;
			ctx.drawImage(image, 0, 0, 1, 1);
			return [...ctx.getImageData(0, 0, 1, 1).data];
		});
	expect(pixel[2]).toBeGreaterThan(240);
	expect(pixel[0]).toBeLessThan(15);
});
