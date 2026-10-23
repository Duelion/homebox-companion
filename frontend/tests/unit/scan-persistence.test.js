import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

function load(filename, imports = {}, globals = {}) {
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
		...globals,
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
				return true;
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

test('unconfirmed overlay snapshots edits independently of canonical detections', async () => {
	const { persistence, pending, writes } = harness();
	const live = draft();
	live.activeReviewDraft = {
		...live.detectedItems[0],
		reviewId: 'item-1',
		name: 'Unconfirmed',
		tag_ids: ['chosen'],
		custom_fields: { Color: '紫' },
	};
	const saving = persistence.save(
		() => live,
		() => true
	);
	live.activeReviewDraft.name = 'Later';
	live.activeReviewDraft.tag_ids.push('later');
	pending[0].resolve({});
	assert.equal(await saving, true);
	assert.equal(writes[0].activeReviewDraft.name, 'Unconfirmed');
	assert.equal(JSON.stringify(writes[0].activeReviewDraft.tag_ids), '["chosen"]');
	assert.equal(writes[0].detectedItems[0].name, 'Original');
	assert.equal(writes[0].confirmedItems.length, 0);
});

test('raw photo serialization reuses immutable Files and invalidates replacements', async () => {
	let reads = 0;
	const cached = load(
		'serialize.ts',
		{},
		{
			FileReader: class {
				readAsDataURL(file) {
					reads++;
					this.result = `data:image/jpeg;base64,${file.bytes}`;
					this.onload();
				}
			},
		}
	);
	const first = { name: 'one.jpg', type: 'image/jpeg', bytes: 'YQ==' };
	const replacement = { ...first, bytes: 'Yg==' };
	const item = { originalFile: first, additionalImages: [first] };
	const photos = await cached.serializeReviewPhotos(item);
	await cached.serializeReviewPhotos(item);
	assert.equal(reads, 1);
	assert.equal(photos.length, 2);
	const changed = await cached.serializeReviewPhotos({ originalFile: replacement });
	assert.equal(reads, 2);
	assert.equal(changed[0].dataUrl, 'data:image/jpeg;base64,Yg==');
	assert.equal((await cached.serializeReviewPhotos({})).length, 0);
});

test('failed storage transaction cannot report a saved checkpoint', async () => {
	const { ScanPersistence } = load('scanPersistence.ts', {
		'./serialize': serialize,
		'./sessionPersistence': {
			captureSessionScope: () => ({ contextId: 'u', groupId: 'g' }),
			save: async () => false,
		},
		'$lib/utils/logger': { workflowLogger: { error() {} } },
	});
	const live = { ...draft(), images: [] };
	assert.equal(
		await new ScanPersistence().save(
			() => live,
			() => true
		),
		false
	);
});

test('collection changes invalidate pending writes even before a workflow reset', async () => {
	let scope = { contextId: 'u', groupId: 'old' };
	let resolve;
	let writes = 0;
	const { ScanPersistence } = load('scanPersistence.ts', {
		'./serialize': {
			...serialize,
			serializeImage: () =>
				new Promise((done) => {
					resolve = done;
				}),
		},
		'./sessionPersistence': {
			captureSessionScope: () => scope,
			save: async () => {
				writes++;
				return true;
			},
		},
		'$lib/utils/logger': { workflowLogger: { error() {} } },
	});
	const saving = new ScanPersistence().save(
		() => draft(),
		() => true
	);
	scope = { contextId: 'u', groupId: 'new' };
	resolve({});
	assert.equal(await saving, false);
	assert.equal(writes, 0);
});

test('legacy recovery normalizes identities, keeps source photos and ignores mismatched overlay', async () => {
	const live = draft();
	const stored = {
		...live,
		id: 'old-session',
		createdAt: 1,
		updatedAt: 2,
		detectedItems: [
			{ name: 'A', quantity: 1, sourceImageIndex: 0 },
			{ name: 'B', quantity: 1, sourceImageIndex: 0 },
		],
		activeReviewDraft: {
			name: 'Unrelated',
			quantity: 1,
			sourceImageIndex: 0,
			reviewId: 'wrong-item',
		},
	};
	const file = { name: 'source.jpg' };
	const { ScanPersistence } = load('scanPersistence.ts', {
		'./serialize': {
			...serialize,
			deserializeImage: async () => ({ file }),
			revokeImageObjectUrls() {},
		},
		'./sessionPersistence': {
			captureSessionScope: () => ({ contextId: 'u', groupId: 'g' }),
			load: async () => stored,
		},
	});
	const recovered = await new ScanPersistence().recover(
		{ contextId: 'u', groupId: 'g' },
		() => true
	);
	assert.equal(recovered.id, 'old-session');
	assert.equal(recovered.activeReviewDraft, undefined);
	assert.equal(recovered.detectedItems[0].originalFile, file);
	assert.notEqual(recovered.detectedItems[0].reviewId, recovered.detectedItems[1].reviewId);
});

test('review confirmation consumes an identity once and rejects stale same-photo items', () => {
	const { ReviewService } = load(
		'../workflows/review.svelte.ts',
		{
			'$lib/services/reviewEditor.svelte': { copyReviewItem: (item) => ({ ...item }) },
		},
		{ $state: (value) => value }
	);
	const review = new ReviewService();
	review.setDetectedItems([
		{ name: 'A', quantity: 1, sourceImageIndex: 0 },
		{ name: 'B', quantity: 1, sourceImageIndex: 0 },
	]);
	const first = review.currentItem;
	review.beginDraft();
	review.confirmCurrentItem(review.activeDraft);
	review.confirmCurrentItem(first);
	assert.equal(review.confirmedCount, 1);
	assert.equal(review.currentItem.name, 'B');
	review.beginDraft();
	const last = review.activeDraft;
	review.confirmCurrentItem(last);
	review.confirmCurrentItem(last);
	assert.equal(review.confirmedCount, 2);
	assert.equal(review.activeDraft, null);
});

test('photo replacement and ordering invalidate compressed data while unchanged selections reuse it', () => {
	const { prepareReviewItem } = load('../workflows/prepare-review-item.ts');
	const first = { name: 'first.jpg' };
	const second = { name: 'second.jpg' };
	const item = {
		name: 'A',
		quantity: 1,
		sourceImageIndex: 0,
		originalFile: first,
		additionalImages: [second],
		compressedDataUrl: 'primary-cache',
		compressedAdditionalDataUrls: ['secondary-cache'],
	};
	assert.equal(
		prepareReviewItem(item, [first, second], [first, second]).compressedDataUrl,
		'primary-cache'
	);
	const reordered = prepareReviewItem(item, [second, first], [first, second]);
	assert.equal(reordered.originalFile, second);
	assert.equal(reordered.compressedDataUrl, undefined);
	assert.equal(reordered.compressedAdditionalDataUrls, undefined);
	const replaced = prepareReviewItem(item, [{ name: 'replacement.jpg' }], [first, second]);
	assert.equal(replaced.compressedDataUrl, undefined);
	assert.equal(replaced.additionalImages.length, 0);
});

test('an obsolete autosave cannot replace the latest completed Saved indicator', async () => {
	const saves = [];
	const EmptyService = class {};
	const { scanWorkflow } = load(
		'../workflows/scan.svelte.ts',
		{
			'./capture.svelte': { CaptureService: EmptyService },
			'./analysis.svelte': { AnalysisService: EmptyService },
			'./review.svelte': { ReviewService: EmptyService },
			'./submission.svelte': { SubmissionService: EmptyService },
			'$lib/services/scanPersistence': {
				ScanPersistence: class {
					save() {
						return new Promise((resolve) => saves.push(resolve));
					}
				},
			},
		},
		{ $state: (value) => value }
	);
	scanWorkflow.setLocation('location', 'Storage', 'Storage');
	const older = scanWorkflow.persistAsync();
	const newer = scanWorkflow.persistAsync();
	assert.equal(scanWorkflow.saveState, 'saving');
	saves[1](true);
	await newer;
	assert.equal(scanWorkflow.saveState, 'saved');
	saves[0](false);
	await older;
	assert.equal(scanWorkflow.saveState, 'saved');
});
