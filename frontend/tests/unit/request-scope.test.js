// The harness injects runtime mocks into transpiled source modules.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

let moduleId = 0;
async function loadModule(path, bindings) {
	const source = await readFile(new URL(`../../src/lib/${path}`, import.meta.url), 'utf8');
	const id = `scopeTest${moduleId++}`;
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
function deferred() {
	let resolve;
	const promise = new Promise((done) => {
		resolve = done;
	});
	return { promise, resolve };
}
function auth() {
	return {
		sessionGeneration: 1,
		mode: 'legacy',
		contextId: 'home',
		token: 'old',
		isLegacy: true,
		connection: {},
		verifiedScope: { contextId: 'home', groupId: 'a' },
	};
}
async function client(authStore, refreshToken = async () => true) {
	return loadModule('api/client.ts', {
		authStore,
		log,
		refreshToken,
		registerRefreshTransport() {},
		abortSignalAny() {},
		abortSignalTimeout() {},
	});
}

test('JSON, form and blob responses reject bodies completed after a collection switch', async () => {
	const original = globalThis.fetch;
	try {
		for (const kind of ['json', 'form', 'blob']) {
			const api = await client(auth());
			api.setActiveGroupId('a');
			const body = deferred();
			const started = deferred();
			globalThis.fetch = async () => ({
				ok: true,
				status: 200,
				headers: new Headers({ 'content-type': 'application/json' }),
				json() {
					started.resolve();
					return body.promise;
				},
				blob() {
					started.resolve();
					return body.promise;
				},
			});
			const pending =
				kind === 'json'
					? api.request('/items', { timeout: 0 })
					: kind === 'form'
						? api.requestFormData('/items', new FormData(), { timeout: 0 })
						: api.requestBlobUrl('/photo', { timeout: 0 });
			const rejected = assert.rejects(pending, { name: 'AbortError' });
			await started.promise;
			api.setActiveGroupId('b');
			body.resolve(kind === 'blob' ? new Blob(['old']) : { name: 'old' });
			await rejected;
		}
	} finally {
		globalThis.fetch = original;
	}
});

test('a mutation is never retried with the new collection after a pending refresh', async () => {
	const original = globalThis.fetch;
	try {
		const gate = deferred();
		const started = deferred();
		const api = await client(auth(), () => {
			started.resolve();
			return gate.promise;
		});
		api.setActiveGroupId('a');
		let requests = 0;
		globalThis.fetch = async () => {
			requests++;
			return { ok: false, status: 401 };
		};
		const pending = api.request('/items', { method: 'POST', body: '{}', timeout: 0 });
		const rejected = assert.rejects(pending, { name: 'AbortError' });
		await started.promise;
		api.setActiveGroupId('b');
		gate.resolve(true);
		await rejected;
		assert.equal(requests, 1);
	} finally {
		globalThis.fetch = original;
	}
});

test('old navigation failures cannot restore a location after context reset', async () => {
	const gate = deferred();
	const authStore = auth();
	const locationStore = {
		path: [],
		currentLevel: [],
		pushPath(part) {
			this.path.push(part);
		},
		setCurrentLevel(level) {
			this.currentLevel = level;
		},
	};
	const { locationNavigator } = await loadModule('services/locationNavigator.svelte.ts', {
		authStore,
		locationStore,
		locationsApi: { get: () => gate.promise },
		scanWorkflow: {},
		showToast() {
			assert.fail('stale toast');
		},
		createLogger: () => log,
		$state: (value) => value,
	});
	const pending = locationNavigator.navigateInto({
		id: 'old',
		name: 'Old',
		children: [{ id: 'child' }],
	});
	locationNavigator.reset();
	authStore.verifiedScope = { contextId: 'home', groupId: 'b' };
	gate.resolve(Promise.reject(new DOMException('changed', 'AbortError')));
	await pending;
	assert.deepEqual(locationStore.path, []);
	assert.deepEqual(locationStore.currentLevel, []);
	assert.equal(locationNavigator.currentLocation, null);
	assert.equal(locationNavigator.isLoading, false);
});

test('refresh completion cannot install credentials from a previous session', async () => {
	const authStore = auth();
	let installed = false;
	authStore.setAuthenticatedState = () => {
		installed = true;
	};
	const { refreshToken, registerRefreshTransport } = await loadModule('services/tokenRefresh.ts', {
		authStore,
		registerAuthLifecycle() {},
		log,
	});
	const gate = deferred();
	registerRefreshTransport(() => gate.promise);
	const pending = refreshToken();
	// Logging out and back in as the same identity changes the generation.
	authStore.sessionGeneration++;
	gate.resolve({ token: 'stale', expires_at: '2030-01-01T00:00:00Z' });
	assert.equal(await pending, false);
	assert.equal(installed, false);
});
