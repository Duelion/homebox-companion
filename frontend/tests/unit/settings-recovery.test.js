import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

let moduleId = 0;
async function service(overrides = {}) {
	const source = await readFile(
		new URL('../../src/lib/workflows/settings.svelte.ts', import.meta.url),
		'utf8'
	);
	const state = (value) => value;
	state.snapshot = structuredClone;
	const bindings = {
		$state: state,
		getEmptyPreferences: () => ({ name: null }),
		log: { error() {} },
		getLogs: async () => ({ logs: '', filename: null }),
		getLLMDebugLogs: async () => ({ logs: '', filename: null }),
		fieldPreferences: {},
		customFields: {},
		window: { setTimeout: () => 1, clearTimeout() {} },
		...overrides,
	};
	const id = `settingsTest${moduleId++}`;
	globalThis[id] = bindings;
	const compiled = ts.transpile(source.replace(/^import[\s\S]*?;\s*$/gm, ''), {
		target: ts.ScriptTarget.ES2022,
		module: ts.ModuleKind.ES2022,
	});
	const module = await import(
		`data:text/javascript,${encodeURIComponent(`const { ${Object.keys(bindings).join(', ')} } = globalThis.${id};\n${compiled}`)}`
	);
	delete globalThis[id];
	module.settingsService.setLogAccessKey('operator-test-key');
	return module.settingsService;
}

function deferred() {
	let resolve;
	const promise = new Promise((done) => (resolve = done));
	return { promise, resolve };
}

for (const panel of [
	{
		api: 'getLogs',
		toggle: 'toggleServerLogs',
		refresh: 'refreshServerLogs',
		data: 'serverLogs',
		visible: 'showServerLogs',
	},
	{
		api: 'getLLMDebugLogs',
		toggle: 'toggleLLMDebugLog',
		refresh: 'refreshLLMDebugLog',
		data: 'llmDebugLog',
		visible: 'showLLMDebugLog',
	},
]) {
	test(`${panel.data} failure stays expanded and refresh retains cached diagnostics`, async () => {
		let fail = true;
		const cached = { logs: 'diagnostic', filename: 'test.log' };
		const settings = await service({
			[panel.api]: async () => {
				if (fail) throw new Error('Temporary failure');
				return cached;
			},
		});
		await settings[panel.toggle]();
		assert.equal(settings[panel.visible], true);
		assert.equal(settings.errors[panel.data], 'Temporary failure');
		fail = false;
		await settings[panel.refresh]();
		assert.equal(settings.errors[panel.data], null);
		assert.deepEqual(settings[panel.data], cached);
		fail = true;
		await settings[panel.refresh]();
		assert.deepEqual(settings[panel.data], cached);
		assert.equal(settings.errors[panel.data], 'Temporary failure');
	});

	test(`${panel.data} reset ignores pending completions and permits a new request`, async () => {
		const old = deferred();
		let calls = 0;
		const settings = await service({
			[panel.api]: () =>
				++calls === 1 ? old.promise : Promise.resolve({ logs: 'current', filename: 'new.log' }),
		});
		const pending = settings[panel.toggle]();
		settings.reset();
		settings.setLogAccessKey('new-test-key');
		await settings[panel.toggle]();
		old.resolve({ logs: 'stale', filename: 'old.log' });
		await pending;
		assert.equal(settings[panel.data].logs, 'current');
		assert.equal(settings.isLoading[panel.data], false);
	});

	test(`${panel.data} clears its credential and ignores pending responses on teardown`, async () => {
		const old = deferred();
		let signal;
		const settings = await service({
			[panel.api]: (_lines, token, requestSignal) => {
				assert.equal(token, 'operator-test-key');
				signal = requestSignal;
				return old.promise;
			},
		});
		const pending = settings[panel.toggle]();
		settings.cleanup();
		assert.equal(signal.aborted, true);
		old.resolve({ logs: 'stale', filename: 'old.log' });
		await pending;
		assert.equal(settings.logAccessKey, '');
		assert.equal(settings[panel.data], null);
		assert.equal(settings[panel.visible], false);
		assert.equal(settings.errors[panel.data], null);
	});
}

test('changing the operator key clears remote diagnostics and errors while preserving settings drafts', async () => {
	const settings = await service();
	settings.updateFieldPref('name', 'Keep draft');
	settings.serverLogs = { logs: 'private server diagnostic' };
	settings.llmDebugLog = { logs: 'private LLM diagnostic' };
	settings.errors.serverLogs = 'Denied';
	settings.errors.llmDebugLog = 'Denied';
	settings.setLogAccessKey('replacement-key');
	assert.equal(settings.logAccessKey, 'replacement-key');
	assert.equal(settings.serverLogs, null);
	assert.equal(settings.llmDebugLog, null);
	assert.equal(settings.errors.serverLogs, null);
	assert.equal(settings.errors.llmDebugLog, null);
	assert.equal(settings.fieldPrefs.name, 'Keep draft');
});

test('every prompt draft mutation closes the old preview and one click loads the current draft', async () => {
	let calls = 0;
	const settings = await service({
		fieldPreferences: { getPromptPreview: async () => ({ prompt: `preview ${++calls}` }) },
	});
	for (const change of [
		() => settings.updateFieldPref('name', 'new instruction'),
		() => settings.resetSingleFieldPref('name'),
		() => settings.addCustomField(),
		() => settings.updateCustomFieldProp(0, 'name', 'Location'),
		() => settings.removeCustomField(0),
	]) {
		await settings.togglePromptPreview();
		assert.equal(settings.showPromptPreview, true);
		change();
		assert.equal(settings.promptPreview, null);
		assert.equal(settings.showPromptPreview, false);
		await settings.togglePromptPreview();
		assert.equal(settings.showPromptPreview, true);
		assert.equal(settings.promptPreview, `preview ${calls}`);
		await settings.togglePromptPreview();
	}
	assert.equal(calls, 6);
});

test('prompt responses for a previous draft cannot replace the current preview', async () => {
	const old = deferred();
	let calls = 0;
	const settings = await service({
		fieldPreferences: {
			getPromptPreview: () =>
				++calls === 1 ? old.promise : Promise.resolve({ prompt: 'current' }),
		},
	});
	const pending = settings.togglePromptPreview();
	settings.updateFieldPref('name', 'current');
	await settings.togglePromptPreview();
	old.resolve({ prompt: 'stale' });
	await pending;
	assert.equal(settings.promptPreview, 'current');
	assert.equal(settings.showPromptPreview, true);
	assert.equal(settings.isLoading.promptPreview, false);
});

test('saving settings invalidates the visible preview and one click reloads it', async () => {
	let calls = 0;
	const settings = await service({
		fieldPreferences: {
			getPromptPreview: async () => ({ prompt: `preview ${++calls}` }),
			update: async (preferences) => preferences,
		},
		customFields: { update: async (fields) => fields },
	});
	await settings.togglePromptPreview();
	await settings.saveFieldPrefs();
	assert.equal(settings.saveState, 'success');
	assert.equal(settings.showPromptPreview, false);
	await settings.togglePromptPreview();
	assert.equal(settings.promptPreview, 'preview 2');
	assert.equal(settings.showPromptPreview, true);
});

test('unknown latest release never reports up to date', async () => {
	const settings = await service({
		getVersion: async () => ({ latest_version: null, update_available: false }),
	});
	await settings.checkForUpdates();
	assert.equal(settings.updateCheckDone, false);
	assert.match(settings.errors.updateCheck, /Unable to check for updates/);
});
