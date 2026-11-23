import type { Page } from '@playwright/test';
import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { config, detectedItems } from './fixtures/data';
import { analyzePhotos, selectLocation, uploadPhoto } from './helpers/scan';

type CameraWindow = Window & {
	cameraRequests: MediaStreamConstraints[];
	cameraTracks: MediaStreamTrack[];
};

/** Replace the webcam with a repainted canvas, recording each request and the tracks handed out. */
async function fakeCamera(page: Page, options: { deny?: boolean; cameras?: number } = {}) {
	await page.addInitScript(
		({ deny, cameras }) => {
			const state = Object.assign(window as unknown as CameraWindow, {
				cameraRequests: [] as MediaStreamConstraints[],
				cameraTracks: [] as MediaStreamTrack[],
			});
			navigator.mediaDevices.getUserMedia = async (constraints) => {
				state.cameraRequests.push(constraints ?? {});
				if (deny) throw new DOMException('Permission denied', 'NotAllowedError');
				const canvas = document.createElement('canvas');
				canvas.width = 640;
				canvas.height = 480;
				const context = canvas.getContext('2d')!;
				let frame = 0;
				const paint = () => {
					context.clearRect(0, 0, canvas.width, canvas.height);
					context.fillRect(frame++ % 320, 100, 320, 240);
				};
				paint();
				setInterval(paint, 50);
				const stream = canvas.captureStream(20);
				state.cameraTracks.push(...stream.getTracks());
				return stream;
			};
			navigator.mediaDevices.enumerateDevices = async () =>
				Array.from(
					{ length: cameras },
					(_, index) =>
						({
							kind: 'videoinput',
							deviceId: `camera-${index}`,
							groupId: '',
							label: `Camera ${index}`,
							toJSON: () => ({}),
						}) as MediaDeviceInfo
				);
		},
		{ deny: options.deny ?? false, cameras: options.cameras ?? 1 }
	);
}

const cameraDialog = (page: Page) => page.getByRole('dialog', { name: 'Take a photo' });
const cameraButton = (page: Page) => page.getByRole('button', { name: 'Camera', exact: true });
const liveTracks = (page: Page) =>
	page.evaluate(
		() =>
			(window as unknown as CameraWindow).cameraTracks.filter(
				(track) => track.readyState === 'live'
			).length
	);

test('a desktop Camera button opens the in-page camera and adds each photo taken', async ({
	page,
}) => {
	await fakeCamera(page);
	await selectLocation(page);
	await cameraButton(page).click();
	const dialog = cameraDialog(page);
	await expect(dialog).toBeVisible();
	const shutter = dialog.getByRole('button', { name: 'Take photo' });
	await expect(shutter).toBeFocused();
	await expect(dialog.getByRole('button', { name: 'Switch camera' })).toHaveCount(0);
	const shots = dialog.getByRole('list', { name: 'Photos taken' }).getByRole('img');
	await expect(shots).toHaveCount(0);
	await page.keyboard.press('Enter');
	await expect(shots).toHaveCount(1);
	await shutter.click();
	await expect(shots).toHaveCount(2);
	await expect(dialog.getByRole('img', { name: 'Photo taken 2', exact: true })).toBeVisible();
	expect(
		await shots.evaluateAll((images) =>
			(images as HTMLImageElement[]).every((image) => image.complete && image.naturalWidth > 0)
		)
	).toBe(true);
	await expect(dialog.getByText('2 photos added', { exact: true })).toHaveCount(1);
	// The keyboard keeps working after the first photo.
	await expect(shutter).toBeFocused();
	await page.keyboard.press('Space');
	await expect(shots).toHaveCount(3);
	await dialog.getByRole('button', { name: 'Delete photo 2', exact: true }).click();
	await expect(shots).toHaveCount(2);
	await expect(shutter).toBeFocused();
	expect(await liveTracks(page)).toBe(1);
	await dialog.getByRole('button', { name: 'Done' }).click();
	await expect(dialog).toHaveCount(0);
	await expect(page.getByAltText('Captured 1', { exact: true })).toBeVisible();
	await expect(page.getByAltText('Captured 2', { exact: true })).toBeVisible();
	await expect(page.getByAltText('Captured 3', { exact: true })).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Analyze with AI' })).toBeEnabled();
	expect(await liveTracks(page)).toBe(0);
});

test('the in-page camera adds additional photos to the chosen image', async ({ page }) => {
	await fakeCamera(page);
	await selectLocation(page);
	await uploadPhoto(page);
	await expect(page.getByAltText('Captured 1', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Expand options' }).click();
	await cameraButton(page).nth(1).click();
	const dialog = cameraDialog(page);
	const shutter = dialog.getByRole('button', { name: 'Take photo' });
	await shutter.click();
	await expect(dialog.getByRole('img', { name: 'Photo taken 1', exact: true })).toBeVisible();
	await shutter.click();
	await expect(dialog.getByRole('img', { name: 'Photo taken 2', exact: true })).toBeVisible();
	await dialog.getByRole('button', { name: 'Delete photo 1', exact: true }).click();
	await expect(dialog.getByRole('img', { name: 'Photo taken 2', exact: true })).toHaveCount(0);
	await page.keyboard.press('Escape');
	await expect(dialog).toHaveCount(0);
	await expect(page.getByText('Image Count: 2', { exact: true })).toBeVisible();
	await expect(page.getByAltText('Captured 2', { exact: true })).toHaveCount(0);
	expect(await liveTracks(page)).toBe(0);
});

test('the in-page camera closes when the image limit is reached', async ({ page, api }) => {
	api.on('GET', '/api/config', () => json({ ...config(), capture_max_images: 2 }));
	await fakeCamera(page);
	await selectLocation(page);
	await uploadPhoto(page);
	await expect(page.getByAltText('Captured 1', { exact: true })).toBeVisible();
	await cameraButton(page).first().click();
	const dialog = cameraDialog(page);
	await dialog.getByRole('button', { name: 'Take photo' }).click();
	await expect(dialog).toHaveCount(0);
	await expect(page.getByAltText('Captured 2', { exact: true })).toBeVisible();
	expect(await liveTracks(page)).toBe(0);
});

test('switching cameras requests the next device and releases the previous one', async ({
	page,
}) => {
	await fakeCamera(page, { cameras: 2 });
	await selectLocation(page);
	await cameraButton(page).click();
	const dialog = cameraDialog(page);
	await dialog.getByRole('button', { name: 'Switch camera' }).click();
	await expect(dialog.getByRole('button', { name: 'Take photo' })).toBeEnabled();
	const requests = await page.evaluate(() => (window as unknown as CameraWindow).cameraRequests);
	expect(requests).toHaveLength(2);
	expect(requests[0].video).toMatchObject({ facingMode: { ideal: 'environment' } });
	expect(requests[1].video).toMatchObject({ deviceId: { exact: 'camera-0' } });
	expect(await liveTracks(page)).toBe(1);
});

test('a blocked camera explains why and offers the file chooser', async ({ page }) => {
	await fakeCamera(page, { deny: true });
	await selectLocation(page);
	await cameraButton(page).click();
	const dialog = cameraDialog(page);
	await expect(dialog.getByRole('alert')).toHaveText(
		'Camera permission denied. Check your browser settings.'
	);
	await expect(dialog.getByText('Error code: NOTALLOWED', { exact: true })).toBeVisible();
	await expect(dialog.getByRole('button', { name: 'Take photo' })).toHaveCount(0);
	await dialog.getByRole('button', { name: 'Try Camera Again' }).click();
	await expect
		.poll(() => page.evaluate(() => (window as unknown as CameraWindow).cameraRequests.length))
		.toBe(2);
	const chooser = page.waitForEvent('filechooser');
	await dialog.getByRole('button', { name: 'Choose a photo instead' }).click();
	expect((await chooser).isMultiple()).toBe(true);
	await expect(dialog).toHaveCount(0);
});

test('the review page adds photos from the in-page camera', async ({ page, api }) => {
	api.on('POST', '/api/tools/vision/detect', () => json(detectedItems(['Desk lamp'])));
	await fakeCamera(page);
	await selectLocation(page);
	await uploadPhoto(page);
	await analyzePhotos(page);
	await page.getByRole('button', { name: /Attached Photos/ }).click();
	const thumbnails = page.getByRole('img', { name: /^Photo \d+$/ });
	const before = await thumbnails.count();
	await cameraButton(page).click();
	const dialog = cameraDialog(page);
	const shots = dialog.getByRole('list', { name: 'Photos taken' }).getByRole('img');
	await dialog.getByRole('button', { name: 'Take photo' }).click();
	await expect(shots).toHaveCount(1);
	await dialog.getByRole('button', { name: 'Take photo' }).click();
	await expect(shots).toHaveCount(2);
	await dialog.getByRole('button', { name: 'Delete photo 2', exact: true }).click();
	await expect(shots).toHaveCount(1);
	await dialog.getByRole('button', { name: 'Done' }).click();
	await expect(dialog).toHaveCount(0);
	await expect(thumbnails).toHaveCount(before + 1);
	expect(await liveTracks(page)).toBe(0);
});

test('mobile browsers keep opening the device camera from the capture input @mobile', async ({
	page,
}) => {
	await fakeCamera(page);
	await selectLocation(page);
	const chooser = page.waitForEvent('filechooser');
	await cameraButton(page).click();
	expect((await chooser).isMultiple()).toBe(false);
	await expect(cameraDialog(page)).toHaveCount(0);
	expect(await page.evaluate(() => (window as unknown as CameraWindow).cameraRequests)).toEqual([]);
});
