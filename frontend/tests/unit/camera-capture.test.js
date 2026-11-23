import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

const source = readFileSync(
	new URL('../../src/lib/utils/cameraCapture.ts', import.meta.url),
	'utf8'
);
const { outputText } = ts.transpileModule(source, {
	compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const camera = {};
runInNewContext(outputText, { exports: camera, Error, File, Date });

const chromeLinux =
	'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36';
const safariMac =
	'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15';
const chromeAndroid =
	'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36';
const safariIphone =
	'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';

const desktop = (userAgent, extra = {}) => ({
	isSecureContext: true,
	navigator: { userAgent, mediaDevices: { getUserMedia() {} }, ...extra },
});

test('mobile browsers keep the native capture input', () => {
	assert.equal(camera.hasNativeCameraCapture({ userAgent: chromeAndroid }), true);
	assert.equal(camera.hasNativeCameraCapture({ userAgent: safariIphone }), true);
	// An Android tablet asking for the desktop site still reports its platform.
	assert.equal(
		camera.hasNativeCameraCapture({
			userAgent: chromeLinux,
			userAgentData: { platform: 'Android' },
		}),
		true
	);
	// iPadOS Safari sends a Mac user agent; the touch screen tells them apart.
	assert.equal(camera.hasNativeCameraCapture({ userAgent: safariMac, maxTouchPoints: 5 }), true);
	assert.equal(camera.shouldUseInPageCamera(desktop(chromeAndroid)), false);
});

test('desktop browsers use the in-page camera when getUserMedia is available', () => {
	assert.equal(camera.hasNativeCameraCapture({ userAgent: chromeLinux }), false);
	assert.equal(camera.hasNativeCameraCapture({ userAgent: safariMac, maxTouchPoints: 0 }), false);
	// A touch-screen laptop is still a desktop browser.
	assert.equal(
		camera.hasNativeCameraCapture({ userAgent: chromeLinux, maxTouchPoints: 10 }),
		false
	);
	assert.equal(camera.shouldUseInPageCamera(desktop(chromeLinux)), true);
	assert.equal(camera.shouldUseInPageCamera(desktop(safariMac)), true);
});

test('desktop browsers without camera access fall back to the file input', () => {
	assert.equal(
		camera.shouldUseInPageCamera({ ...desktop(chromeLinux), isSecureContext: false }),
		false
	);
	assert.equal(
		camera.shouldUseInPageCamera({ isSecureContext: true, navigator: { userAgent: chromeLinux } }),
		false
	);
	assert.equal(camera.shouldUseInPageCamera(desktop(chromeLinux, { mediaDevices: {} })), false);
});

test('camera errors get a readable message and a short code', () => {
	const named = (name, message = '') => Object.assign(new Error(message), { name });
	assert.deepEqual(
		{ ...camera.describeCameraError(named('NotAllowedError')) },
		{ message: 'Camera permission denied. Check your browser settings.', code: 'NOTALLOWED' }
	);
	assert.equal(camera.describeCameraError(named('NotFoundError')).message, 'No camera detected.');
	assert.equal(camera.describeCameraError(named('NotReadableError')).code, 'NOTREADABL');
	assert.deepEqual(
		{ ...camera.describeCameraError(named('TypeError', 'boom')) },
		{ message: 'Camera error: boom.', code: 'TYPE' }
	);
	assert.deepEqual(
		{ ...camera.describeCameraError('nope') },
		{ message: 'Camera error: unknown error.', code: 'UNKNOWN' }
	);
});

test('photos get a sortable local-time file name', () => {
	assert.equal(
		camera.cameraFileName(new Date(2026, 0, 5, 9, 3, 7, 42)),
		'camera-20260105-090307-042.jpg'
	);
});
