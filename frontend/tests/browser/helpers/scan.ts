import { expect, type Page } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const image = fileURLToPath(
	new URL('../../../../tests/assets/multi_item_single_image.jpg', import.meta.url)
);

export async function selectLocation(page: Page, name = 'Storage') {
	await page.goto('/location');
	await page.getByRole('button', { name: new RegExp(name) }).click();
	await page.getByRole('button', { name: 'Select current location' }).click();
	await page.getByRole('button', { name: 'Continue to Capture' }).click();
	await expect(page).toHaveURL(/\/capture$/);
}

export async function uploadPhoto(page: Page) {
	await page.locator('input[type="file"]').first().setInputFiles(image);
}

export async function analyzePhotos(page: Page) {
	await page.getByRole('button', { name: /Analyze with AI/ }).click();
	await expect(page).toHaveURL(/\/review$/);
}

export async function confirmItems(page: Page, count: number) {
	for (let index = 0; index < count; index++) {
		await page.getByRole('button', { name: 'Confirm' }).click();
	}
	await expect(page).toHaveURL(/\/summary$/);
}

export async function submitItems(page: Page) {
	await page.getByRole('button', { name: /Submit All Items/ }).click();
}
