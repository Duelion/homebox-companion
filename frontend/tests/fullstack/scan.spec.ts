import { test, expect } from '@playwright/test';
import {
	analyzePhotos,
	confirmItems,
	selectLocation,
	submitItems,
	uploadPhoto,
} from '../browser/helpers/scan';

test('saves a reviewed photo through Companion to Homebox', async ({ page }) => {
	await selectLocation(page, 'Smoke storage');
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByLabel('Name', { exact: true }).fill('Smoke desk lamp');
	await page.getByRole('button', { name: 'Extended Fields' }).click();
	await page.getByLabel('Manufacturer', { exact: true }).fill('Smoke Manufacturing');
	await confirmItems(page, 1);
	await submitItems(page);
	await expect(page).toHaveURL(/\/success$/);
});
