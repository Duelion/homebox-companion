import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

function load(filename, imports = {}) {
	const source = readFileSync(
		new URL(`../../src/lib/services/${filename}`, import.meta.url),
		'utf8'
	);
	const { outputText } = ts.transpileModule(source, {
		compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
	});
	const exports = {};
	runInNewContext(outputText, {
		exports,
		require: (name) => imports[name],
		crypto: globalThis.crypto,
	});
	return exports;
}
const serialize = load('serialize.ts');
function draft(name = 'Original') {
	return {
		status: 'reviewing',
		locationId: null,
		locationName: null,
		locationPath: null,
		parentItemId: null,
		parentItemName: null,
		currentReviewIndex: 0,
		images: [{ file: {}, extraInstructions: name }],
		detectedItems: [{ name, quantity: 1, sourceImageIndex: 0, custom_fields: { Color: 'Blue' } }],
		confirmedItems: [],
		submission: { itemStatuses: { 0: 'pending' }, createdItemIds: {}, lastErrors: [] },
	};
}
function harness() {
	const pending = [];
	const writes = [];
	const { ScanPersistence } = load('scanPersistence.ts', {
		'./serialize': {
			...serialize,
			serializeImage: (image) => new Promise((resolve) => pending.push({ image, resolve })),
		},
		'./sessionPersistence': {
			captureSessionScope: () => ({ contextId: 'user', groupId: 'collection' }),
			save: async (session) => {
				writes.push(session);
			},
		},
		'$lib/utils/logger': {
			workflowLogger: {
				error: (error) => {
					throw error;
				},
			},
		},
	});
	return { persistence: new ScanPersistence(), pending, writes };
}
test('custom fields survive serialized review and confirmed reloads', async () => {
	const item = draft().detectedItems[0];
	for (const confirmed of [false, true]) {
		const stored = confirmed
			? serialize.serializeConfirmedItem(item)
			: serialize.serializeReviewItem(item);
		const reloaded = JSON.parse(JSON.stringify(stored));
		const recovered = confirmed
			? await serialize.deserializeConfirmedItem(reloaded)
			: await serialize.deserializeReviewItem(reloaded);
		assert.equal(JSON.stringify(recovered.custom_fields), JSON.stringify(item.custom_fields));
	}
});
test('deferred serialization uses one detached draft snapshot', async () => {
	const { persistence, pending, writes } = harness();
	const live = draft();
	let reads = 0;
	const saving = persistence.save(
		() => {
			reads++;
			return live;
		},
		() => true
	);
	live.detectedItems[0].name = 'Changed';
	live.detectedItems[0].custom_fields.Color = 'Red';
	live.images[0].extraInstructions = 'Changed';
	live.submission.itemStatuses[0] = 'success';
	pending[0].resolve({ extraInstructions: pending[0].image.extraInstructions });
	await saving;
	assert.equal(reads, 1);
	assert.equal(writes[0].detectedItems[0].name, 'Original');
	assert.equal(writes[0].detectedItems[0].custom_fields.Color, 'Blue');
	assert.equal(writes[0].images[0].extraInstructions, 'Original');
	assert.equal(writes[0].submission.itemStatuses[0], 'pending');
});
test('older serialization finishing last cannot overwrite newer state', async () => {
	const { persistence, pending, writes } = harness();
	const older = persistence.save(
		() => draft('Older'),
		() => true
	);
	const newer = persistence.save(
		() => draft('Newer'),
		() => true
	);
	pending[1].resolve({});
	await newer;
	pending[0].resolve({});
	await older;
	assert.equal(writes.length, 1);
	assert.equal(writes[0].detectedItems[0].name, 'Newer');
});
test('reset invalidates pending saves', async () => {
	const { persistence, pending, writes } = harness();
	const saving = persistence.save(
		() => draft(),
		() => true
	);
	persistence.resetMetadata();
	pending[0].resolve({});
	await saving;
	assert.equal(writes.length, 0);
});
