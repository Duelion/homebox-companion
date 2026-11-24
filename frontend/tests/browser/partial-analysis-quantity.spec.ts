import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { createdItem, detectedItems } from './fixtures/data';
import { readDrafts } from './helpers/recovery';
import { selectLocation } from './helpers/scan';

const photo = (name: string) => ({
	name,
	mimeType: 'image/png',
	buffer: Buffer.from(
		'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC',
		'base64'
	),
});

for (const action of ['Continue with Successful', 'Remove Failed', 'Retry Failed Images']) {
	test(`partial analysis locks successful quantities through ${action}`, async ({ page, api }) => {
		const creations: unknown[] = [];
		const detectionGate = api.gate();
		let successfulDetections = 0;
		let failedDetections = 0;
		api.on('POST', '/api/tools/vision/detect', async (request) => {
			await detectionGate.promise;
			if (request.postDataBuffer()?.includes(Buffer.from('failed.png'))) {
				failedDetections++;
				if (failedDetections === 1) return json({ detail: 'Detection failed' }, 500);
				return json(detectedItems(['Retried item']));
			}
			successfulDetections++;
			return json(detectedItems(['Saved item']));
		});
		api.on('POST', '/api/items', (request) => {
			creations.push(request.postDataJSON());
			return json(createdItem(`item-${creations.length}`));
		});
		api.on('POST', /^\/api\/items\/item-\d+\/attachments$/, () => json({}));

		await selectLocation(page);
		await page.locator('input[type="file"]').first().setInputFiles(photo('failed.png'));
		const quantities = page.getByLabel('Quantity of identical items');
		await quantities.first().fill('3');
		// New photo groups are prepended, so the successful group will be first.
		await page.locator('input[type="file"]').first().setInputFiles(photo('successful.png'));
		await expect(quantities).toHaveCount(2);
		await quantities.first().fill('2');
		await page.getByRole('button', { name: /Analyze with AI/ }).click();
		await expect(quantities.first()).toBeDisabled();
		await expect(quantities.nth(1)).toBeDisabled();
		detectionGate.release();
		await expect(page.getByRole('button', { name: action, exact: true })).toBeVisible();
		await expect(quantities.first()).toBeDisabled();
		await expect(quantities.first()).toHaveValue('2');
		await expect(quantities.nth(1)).toBeEnabled();
		await quantities.nth(1).fill('5');

		if (action === 'Retry Failed Images') {
			// Recovery must preserve both the lock and the failed group's edited override.
			await expect
				.poll(() => readDrafts(page, 'deployment:user:g1'))
				.toMatchObject([
					{
						status: 'partial_analysis',
						images: [{ quantityOverride: 2 }, { quantityOverride: 5 }],
					},
				]);
			await page.reload();
			await page.getByRole('button', { name: 'Resume Session' }).click();
			await expect(page).toHaveURL(/\/capture$/);
			await expect(quantities.first()).toBeDisabled();
			await expect(quantities.first()).toHaveValue('2');
			await expect(quantities.nth(1)).toBeEnabled();
			await expect(quantities.nth(1)).toHaveValue('5');
		}

		await page.getByRole('button', { name: action, exact: true }).click();
		await expect(page).toHaveURL(/\/review$/);
		await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Saved item');
		const reviewQuantity = page.getByRole('spinbutton', { name: 'Quantity', exact: true });
		await expect(reviewQuantity).toHaveValue('2');
		// The locked capture field does not prevent corrections in the item editor.
		await reviewQuantity.fill('7');
		await page.getByRole('button', { name: 'Confirm', exact: true }).click();
		if (action === 'Retry Failed Images') {
			await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Retried item');
			await expect(reviewQuantity).toHaveValue('5');
			await page.getByRole('button', { name: 'Confirm', exact: true }).click();
		}
		await page.getByRole('button', { name: /Submit All Items/ }).click();
		await expect(page).toHaveURL(/\/success$/);
		expect(successfulDetections).toBe(1);
		expect(failedDetections).toBe(action === 'Retry Failed Images' ? 2 : 1);
		expect(creations).toEqual([
			expect.objectContaining({
				items: [expect.objectContaining({ name: 'Saved item', quantity: 7 })],
			}),
			...(action === 'Retry Failed Images'
				? [
						expect.objectContaining({
							items: [expect.objectContaining({ name: 'Retried item', quantity: 5 })],
						}),
					]
				: []),
		]);
	});
}
