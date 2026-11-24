// Exercise the real store and navigator; only runes and external services are substituted.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

let moduleId = 0;
async function loadModule(path, bindings) {
	const source = await readFile(new URL(`../../src/lib/${path}`, import.meta.url), 'utf8');
	const id = `locationRefreshTest${moduleId++}`;
	globalThis[id] = bindings;
	const compiled = ts.transpile(source.replace(/^import[\s\S]*?;\s*$/gm, ''), {
		target: ts.ScriptTarget.ES2022,
		module: ts.ModuleKind.ES2022,
	});
	try {
		return await import(
			`data:text/javascript,${encodeURIComponent(`const { ${Object.keys(bindings).join(', ')} } = globalThis.${id};\n${compiled}`)}`
		);
	} finally {
		delete globalThis[id];
	}
}
const location = (id, children = [], totalItemQuantity = 0) => ({
	id,
	name: id,
	type: 'location',
	children,
	totalItemQuantity,
});
function deferred() {
	let resolve;
	const promise = new Promise((done) => (resolve = done));
	return { promise, resolve };
}
async function setup() {
	const { locationStore } = await loadModule('stores/locations.svelte.ts', {
		$state: (value) => value,
		SvelteMap: Map,
	});
	const locationsApi = { tree: async () => [], get: async (id) => location(id) };
	const authStore = {
		sessionGeneration: 1,
		connection: {},
		verifiedScope: { contextId: 'home', groupId: 'a' },
	};
	const scanWorkflow = {
		state: {},
		setLocation(id, name, path) {
			this.state = { locationId: id, locationName: name, locationPath: path };
		},
		clearLocation() {
			this.state = {};
		},
	};
	const toasts = [];
	const { locationNavigator } = await loadModule('services/locationNavigator.svelte.ts', {
		$state: (value) => value,
		locationStore,
		locationsApi,
		authStore,
		scanWorkflow,
		createLogger: () => ({ debug() {}, warn() {}, error() {} }),
		showToast: (...args) => toasts.push(args),
	});
	return { locationStore, locationNavigator, locationsApi, authStore, scanWorkflow, toasts };
}

test('every tree replacement updates the searchable quantities and paths', async () => {
	const { locationStore } = await setup();
	locationStore.setTree([location('Storage', [location('Box')], 15)]);
	assert.equal(locationStore.flatList[0].location.totalItemQuantity, 15);
	locationStore.setTree([location('Other', [location('Box')], 27)]);
	assert.equal(locationStore.flatList[0].location.totalItemQuantity, 27);
	assert.equal(locationStore.flatList[1].path, 'Other › Box');
	assert.equal(
		locationStore.flatList.some(({ location }) => location.id === 'Storage'),
		false
	);
});

test('All breadcrumb refresh updates browsing and search totals together', async () => {
	const { locationNavigator, locationStore, locationsApi } = await setup();
	locationsApi.tree = async () => [location('Storage', [], 15)];
	await locationNavigator.loadTree();
	await locationNavigator.navigateInto(location('Storage'));
	locationsApi.tree = async () => [location('Storage', [], 27)];
	await locationNavigator.navigateToPath(-1);
	assert.equal(locationStore.currentLevel[0].totalItemQuantity, 27);
	assert.equal(locationStore.flatList[0].location.totalItemQuantity, 27);
	assert.deepEqual(locationStore.path, []);
});

test('selected refresh removes old containers and gives added/moved children their new paths', async () => {
	const { locationNavigator, locationStore, locationsApi, scanWorkflow } = await setup();
	const oldBox = location('Old box');
	const movedBox = location('Moved box');
	const newBox = location('New box');
	const oldStorage = location('Storage', [oldBox]);
	locationsApi.tree = async () => [oldStorage, location('Other', [movedBox])];
	await locationNavigator.loadTree();
	locationStore.setPath([{ id: 'Storage', name: 'Storage' }]);
	locationNavigator.selectLocation(oldStorage, 'Storage');
	const freshStorage = location('Storage', [newBox, movedBox], 27);
	locationsApi.tree = async () => [freshStorage, location('Other', [oldBox])];
	locationsApi.get = async () => freshStorage;
	await locationNavigator.refreshSelected();
	const candidates = locationStore.flatList.find(
		({ location }) => location.id === locationStore.selected.id
	).location.children;
	assert.deepEqual(
		candidates.map(({ id }) => id),
		['New box', 'Moved box']
	);
	for (const child of candidates) {
		const path = locationStore.getPathTo(child.id);
		locationStore.setPath(path);
		locationNavigator.selectLocation(child, path.map(({ name }) => name).join(' / '));
		assert.equal(scanWorkflow.state.locationId, child.id);
		assert.equal(scanWorkflow.state.locationPath, `Storage / ${child.name}`);
	}
});

for (const replacement of ['navigation', 'scope']) {
	test(`pending selected refresh cannot overwrite a newer ${replacement}`, async () => {
		const { locationNavigator, locationStore, locationsApi, authStore, toasts } = await setup();
		const stale = location('Storage', [location('Old box')], 15);
		locationsApi.tree = async () => [stale];
		await locationNavigator.loadTree();
		locationNavigator.selectLocation(stale, 'Storage');
		const gate = deferred();
		let trees = 0;
		locationsApi.get = async () => stale;
		locationsApi.tree = () => {
			trees++;
			return gate.promise;
		};
		const pending = locationNavigator.refreshSelected();
		await Promise.resolve();
		assert.equal(trees, 1);
		const fresh = location('Current', [location('New box')], 27);
		locationsApi.tree = async () => [fresh];
		if (replacement === 'scope') {
			locationNavigator.reset();
			locationStore.clear();
			authStore.verifiedScope = { contextId: 'home', groupId: 'b' };
			await locationNavigator.loadTree();
		} else {
			await locationNavigator.clearSelection();
		}
		gate.resolve([stale]);
		await pending;
		assert.equal(locationStore.selected, null);
		assert.deepEqual(locationStore.tree, [fresh]);
		assert.equal(locationStore.flatList[0].location.totalItemQuantity, 27);
		assert.deepEqual(locationStore.currentLevel, [fresh]);
		assert.equal(locationNavigator.isLoading, false);
		assert.deepEqual(toasts, []);
	});
}

test('a failed tree refresh keeps selected details and the cached tree on the same version', async () => {
	const { locationNavigator, locationStore, locationsApi, toasts } = await setup();
	const stale = location('Storage', [location('Old box')]);
	locationsApi.tree = async () => [stale];
	await locationNavigator.loadTree();
	locationNavigator.selectLocation(stale, 'Storage');
	locationsApi.get = async () => location('Storage', [location('New box')]);
	locationsApi.tree = async () => {
		throw new Error('Temporary tree failure');
	};
	await locationNavigator.refreshSelected();
	assert.deepEqual(locationStore.selected, stale);
	assert.deepEqual(locationStore.tree, [stale]);
	assert.equal(locationNavigator.isLoading, false);
	assert.deepEqual(toasts, [['Failed to refresh location', 'error']]);
});
