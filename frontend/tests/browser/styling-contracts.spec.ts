import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { detectedItems } from './fixtures/data';
import { selectLocation, uploadPhoto, analyzePhotos } from './helpers/scan';

for (const mobile of [false, true]) {
	test(`design utilities and review layout remain consistent ${mobile ? '@mobile' : 'desktop'}`, async ({
		page,
		api,
	}, testInfo) => {
		await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1280, height: 900 });
		api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Desk tools'])));
		await selectLocation(page);
		await uploadPhoto(page);
		await analyzePhotos(page);
		await expect(page.getByLabel('Name', { exact: true })).toHaveValue('Desk tools');
		expect(
			await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
		).toBe(true);
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
		// Finish navigation snapshots before changing motion preferences mid-transition.
		await page.evaluate(async () => {
			await Promise.all(
				document
					.getAnimations()
					.filter((animation) => animation.effect?.getComputedTiming().iterations !== Infinity)
					.map((animation) => animation.finished.catch(() => {}))
			);
		});
		await page.emulateMedia({ reducedMotion: 'reduce' });
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
