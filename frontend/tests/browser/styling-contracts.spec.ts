import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { detectedItems } from './fixtures/data';
import { uploadPhoto, analyzePhotos } from './helpers/scan';

for (const mobile of [false, true]) {
	test(`design utilities and review layout remain consistent ${mobile ? '@mobile' : 'desktop'}`, async ({
		page,
		api,
	}, testInfo) => {
		await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1280, height: 900 });
		await page.goto('/location');
		const utilities = await page.evaluate(() => {
			const probe = document.createElement('div');
			document.body.append(probe);
			const read = (className: string) => {
				probe.className = className;
				const style = getComputedStyle(probe);
				return {
					radius: style.borderRadius,
					animationDelay: style.animationDelay,
					transitionDelay: style.transitionDelay,
				};
			};
			const values = { extraSmall: read('rounded-xs'), animation: read('animation-delay-100') };
			probe.remove();
			return values;
		});
		expect(utilities.extraSmall.radius).toBe('2px');
		expect(utilities.animation.animationDelay).toBe('0.1s');
		// Animation delays must not change Tailwind transition timing.
		expect(utilities.animation.transitionDelay).toBe('0s');
		// Read animation utilities with normal motion, then disable motion before scan navigation.
		await page.emulateMedia({ reducedMotion: 'reduce' });
		api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Desk tools'])));
		await page.getByRole('button', { name: /Storage/ }).click();
		await page.getByRole('button', { name: 'Select current location' }).click();
		await page.getByRole('button', { name: 'Continue to Capture' }).click();
		await expect(page).toHaveURL(/\/capture$/);
		await uploadPhoto(page);
		await analyzePhotos(page);
		await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Desk tools');
		expect(
			await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
		).toBe(true);
		await page.evaluate(async () => {
			await document.fonts.ready;
			await Promise.all(Array.from(document.images, (image) => image.decode().catch(() => {})));
		});
		await page.screenshot({
			path: testInfo.outputPath(`review-${mobile ? 'mobile' : 'desktop'}.png`),
			fullPage: true,
		});
	});
}
