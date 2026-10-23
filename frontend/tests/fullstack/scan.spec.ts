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
	await page.getByLabel('Quantity', { exact: true }).fill('7');
	await page.getByLabel('Description', { exact: true }).fill('Recovered description — verified');
	await page.getByLabel('Asset ID', { exact: true }).fill('032-001');
	await page.getByRole('button', { name: 'Extended Fields' }).click();
	await page.getByLabel('Manufacturer', { exact: true }).fill('Smoke Manufacturing');
	await page.getByLabel('Model Number', { exact: true }).fill('Smoke Model');
	await page.getByLabel('Serial Number', { exact: true }).fill('Smoke Serial');
	await page.getByLabel('Purchase Price', { exact: true }).fill('12.34');
	await page.getByLabel('Purchased From', { exact: true }).fill('Smoke Shop');
	await page.getByLabel('Notes', { exact: true }).fill('Recovered notes — 日本語');
	await page.getByRole('button', { name: /Custom Fields/ }).click();
	await page.getByLabel('Smoke Material', { exact: true }).fill('Steel — verified');
	await expect(page.getByRole('status').filter({ hasText: /^Saved$/ })).toBeVisible();
	await page.reload();
	await page.getByRole('button', { name: 'Resume Session', exact: true }).click();
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Smoke desk lamp');
	await expect(page.getByLabel('Quantity', { exact: true })).toHaveValue('7');
	await expect(page.getByLabel('Asset ID', { exact: true })).toHaveValue('032-001');
	await expect(page.getByLabel('Notes', { exact: true })).toHaveValue('Recovered notes — 日本語');
	await confirmItems(page, 1);
	await page.getByRole('button', { name: 'Edit item', exact: true }).click();
	await page.getByLabel('Name', { exact: true }).fill('Smoke desk lamp recovered');
	await expect(page.getByRole('status').filter({ hasText: /^Saved$/ })).toBeVisible();
	await page.reload();
	await page.getByRole('button', { name: 'Resume Session', exact: true }).click();
	await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Smoke desk lamp recovered');
	await confirmItems(page, 1);
	await submitItems(page);
	await expect(page).toHaveURL(/\/success$/);
});
