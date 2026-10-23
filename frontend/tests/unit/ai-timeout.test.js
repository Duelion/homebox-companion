// Exercise the real vision and transport modules with a deterministic timer clock.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

let moduleId = 0;
async function loadModule(path, bindings = {}) {
	const source = await readFile(new URL(`../../src/lib/${path}`, import.meta.url), 'utf8');
	const id = `aiTimeoutTest${moduleId++}`;
	globalThis[id] = bindings;
	const compiled = ts.transpile(source.replace(/^import[\s\S]*?;\s*$/gm, ''), {
		target: ts.ScriptTarget.ES2022,
		module: ts.ModuleKind.ES2022,
	});
	return import(
		`data:text/javascript,${encodeURIComponent(`const { ${Object.keys(bindings).join(', ')} } = globalThis.${id};\n${compiled}`)}`
	);
}
const log = { debug() {}, info() {}, warn() {}, error() {} };
const image = new File(['photo'], 'photo.jpg', { type: 'image/jpeg' });
const operations = {
	detect: (vision, signal) => vision.detect(image, { signal }),
	analyze: (vision, signal) => vision.analyze([image], 'Camera', undefined, { signal }),
	merge: (vision, signal) => vision.merge([{ name: 'Camera' }], { signal }),
	correct: (vision, signal) => vision.correct(image, { name: 'Camera' }, 'Fix name', { signal }),
};
async function setup(t) {
	t.mock.timers.enable({ apis: ['setTimeout'] });
	// Use the shipped fallback so the test clock controls deadlines on every Node version.
	const nativeTimeout = AbortSignal.timeout;
	AbortSignal.timeout = undefined;
	t.after(() => {
		AbortSignal.timeout = nativeTimeout;
	});
	const signals = await loadModule('utils/abortSignal.ts');
	const timeout = await loadModule('api/aiTimeout.ts');
	timeout.setAiRequestTimeoutSeconds(90);
	const client = await loadModule('api/client.ts', {
		...signals,
		authStore: { sessionGeneration: 1, mode: 'legacy', isLegacy: true, token: 'token' },
		log,
		refreshToken: async () => true,
		registerRefreshTransport() {},
	});
	const { vision } = await loadModule('api/vision.ts', {
		...client,
		...timeout,
		log,
		getIsDemoMode: () => false,
		fieldPreferences: {},
	});
	return { ...client, ...timeout, vision };
}
function delayedReply(signal, milliseconds, body = { name: 'Camera' }) {
	return new Promise((resolve, reject) => {
		const aborted = () => reject(signal.reason);
		if (signal.aborted) return aborted();
		signal.addEventListener('abort', aborted, { once: true });
		setTimeout(() => {
			signal.removeEventListener('abort', aborted);
			resolve(
				new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } })
			);
		}, milliseconds);
	});
}
async function flush() {
	for (let count = 0; count < 10; count++) await Promise.resolve();
}
for (const [name, invoke] of Object.entries(operations)) {
	test(`${name} survives 60 seconds and propagates its configured deadline and caller cancellation`, async (t) => {
		const api = await setup(t);
		t.mock.method(globalThis, 'fetch', async (url, options) => {
			assert.equal(url, `/api/tools/vision/${name}`);
			assert.equal(options.body instanceof FormData, name !== 'merge');
			return delayedReply(options.signal, 61_000);
		});
		const success = invoke(api.vision);
		await flush();
		t.mock.timers.tick(61_000);
		assert.deepEqual(await success, { name: 'Camera' });

		api.setAiRequestTimeoutSeconds(75);
		t.mock.method(globalThis, 'fetch', (url, options) => delayedReply(options.signal, 100_000));
		const expiry = invoke(api.vision);
		const expired = assert.rejects(expiry, { name: 'NetworkError', isTimeout: true });
		await flush();
		// Keep this response pending beyond its configured deadline.
		t.mock.timers.tick(75_000);
		await expired;

		const controller = new AbortController();
		const cancelled = invoke(api.vision, controller.signal);
		const cancellation = assert.rejects(cancelled, { name: 'AbortError' });
		await flush();
		controller.abort();
		await cancellation;
	});
}

test('ordinary requests retain 60 seconds while vision retries receive a fresh configured deadline', async (t) => {
	const api = await setup(t);
	t.mock.method(globalThis, 'fetch', (url, options) => delayedReply(options.signal, 100_000));
	const ordinary = assert.rejects(api.request('/items'), { name: 'NetworkError', isTimeout: true });
	t.mock.timers.tick(60_000);
	await ordinary;

	let attempts = 0;
	t.mock.method(globalThis, 'fetch', async (url, options) => {
		attempts++;
		return delayedReply(options.signal, attempts === 1 ? 70_000 : 80_000).then((response) =>
			attempts === 1 ? new Response('', { status: 401 }) : response
		);
	});
	const retried = api.vision.merge([{ name: 'Camera' }]);
	await flush();
	t.mock.timers.tick(70_000);
	await flush();
	assert.equal(attempts, 2);
	t.mock.timers.tick(80_000);
	assert.deepEqual(await retried, { name: 'Camera' });
});

test('vision deadline remains active while the response body is being read', async (t) => {
	const api = await setup(t);
	t.mock.method(globalThis, 'fetch', async (url, options) => ({
		ok: true,
		status: 200,
		headers: new Headers({ 'content-type': 'application/json' }),
		json: () => delayedReply(options.signal, 100_000),
	}));
	const pending = assert.rejects(api.vision.merge([{ name: 'Camera' }]), { name: 'TimeoutError' });
	await flush();
	t.mock.timers.tick(90_000);
	await pending;
});
