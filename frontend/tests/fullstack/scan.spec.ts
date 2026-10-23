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
	await expect(page.getByRole('button', { name: 'Smoke verified', exact: true })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	await page.getByRole('button', { name: 'AI Correction', exact: true }).click();
	await page.getByPlaceholder(/The brand is Sony/).fill('Review this lamp without changing tags');
	await page.getByRole('button', { name: 'Correct with AI', exact: true }).click();
	await expect(page.getByRole('button', { name: 'Confirm', exact: true })).toBeEnabled();
	await expect(page.getByRole('button', { name: 'Smoke verified', exact: true })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	await page.getByLabel('Name', { exact: true }).fill('Smoke desk lamp');
	await page.getByRole('button', { name: 'Extended Fields' }).click();
	await page.getByLabel('Manufacturer', { exact: true }).fill('Smoke Manufacturing');
	await page.getByRole('button', { name: 'Custom Fields', exact: true }).click();
	await page.getByLabel('Smoke Material', { exact: true }).fill('Steel — verified');
	await confirmItems(page, 1);
	await submitItems(page);
	await expect(page).toHaveURL(/\/success$/);
});
