import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

let moduleId = 0;
async function loadModule(path, bindings = {}) {
	const source = await readFile(new URL(`../../src/lib/${path}`, import.meta.url), 'utf8');
	const id = `assetTest${moduleId++}`;
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
const validation = await loadModule('utils/assetId.ts');
const itemValidation = await loadModule('utils/itemValidation.ts', validation);

test('normalizes numeric IDs with optional hyphens without losing int64 precision or zero', () => {
	for (const [input, output] of [
		[null, null],
		[' ', null],
		['032-303', '032-303'],
		[' +000032303 ', '032-303'],
		['000-000', '0'],
		['-001', '000-001'],
		['12-34-567', '123-4567'],
		['9223372036854775807', '922-3372036854775807'],
	]) {
		assert.equal(validation.normalizeAssetId(input), output);
	}
	for (const invalid of [
		'032-REVIEW-3',
		'9223372036854775808',
		'１２３',
		'12 3',
		'1.2',
		'--',
		'+',
		'"123"',
	]) {
		assert.throws(() => validation.normalizeAssetId(invalid), /numeric Homebox/);
	}
});

test('analysis rejects an invalid typed or scanned draft before calling any provider', async () => {
	const module = await loadModule('workflows/analysis.svelte.ts', {
		...validation,
		...itemValidation,
		$state: (value) => value,
		vision: new Proxy(
			{},
			{
				get: () => {
					throw new Error('Provider must not be accessed');
				},
			}
		),
	});
	const result = await new module.AnalysisService().analyze([{ assetId: '032-REVIEW-3' }]);
	assert.equal(result.success, false);
	assert.match(result.error, /invalid asset ID/);
});

test('submission validates the entire recovered batch before any item creation', async () => {
	const module = await loadModule('workflows/submission.svelte.ts', {
		...validation,
		...itemValidation,
		$state: (value) => value,
		itemsApi: new Proxy(
			{},
			{
				get: () => {
					throw new Error('No item mutation allowed');
				},
			}
		),
	});
	const result = await new module.SubmissionService().submitAll(
		[
			{ name: 'Valid first', quantity: 1, asset_id: '032-303' },
			{ name: 'Invalid second', quantity: 1, asset_id: '032-REVIEW-3' },
		],
		'location',
		null
	);
	assert.equal(result.success, false);
	assert.equal(result.failCount, 2);
	assert.match(result.errors[0], /numeric Homebox/);
});

test('direct frontend item updates reject an invalid asset ID before transport', async () => {
	const module = await loadModule('api/items.ts', {
		...validation,
		request: () => {
			throw new Error('Transport must not be accessed');
		},
	});
	assert.throws(() => module.items.update('item', { assetId: '032-REVIEW-3' }), /numeric Homebox/);
});

for (const invalid of [
	{ quantity: 0 },
	{ quantity: 1.5 },
	{ quantity: undefined },
	{ quantity: NaN },
	{ name: '   ' },
	{ purchase_price: -1 },
	{ purchase_price: Infinity },
]) {
	test(`invalid recovered batch is rejected before transport: ${JSON.stringify(invalid)}`, async () => {
		const module = await loadModule('workflows/submission.svelte.ts', {
			...validation,
			...itemValidation,
			$state: (value) => value,
			itemsApi: new Proxy(
				{},
				{
					get: () => {
						throw new Error('No item mutation allowed');
					},
				}
			),
		});
		const result = await new module.SubmissionService().submitAll(
			[
				{ name: 'Valid first', quantity: 1 },
				{ name: 'Invalid second', quantity: 1, ...invalid },
			],
			'location',
			null
		);
		assert.equal(result.failCount, 2);
		assert.equal(result.success, false);
	});
}
test('item policy accepts zero price and rejects blank quantity without coercion', () => {
	assert.equal(
		itemValidation.itemValidationError({ name: 'Item', quantity: 1, purchase_price: 0 }),
		null
	);
	for (const quantity of ['', '1', null, undefined, 0, 1.5, NaN, Infinity]) {
		assert.ok(itemValidation.itemQuantityError(quantity));
	}
});

async function reviewHarness(item) {
	class Service {}
	class Review {
		currentItem = item;
		detectedItems = [item];
		currentReviewIndex = 0;
		confirmCurrentItem() {
			throw new Error('Invalid item must remain in review');
		}
		replaceConfirmedItem() {
			throw new Error('Invalid failed edit must not be saved');
		}
		confirmAllRemainingItems() {
			throw new Error('Invalid batch must remain in review');
		}
	}
	const { scanWorkflow } = await loadModule('workflows/scan.svelte.ts', {
		...itemValidation,
		$state: (value) => value,
		CaptureService: Service,
		AnalysisService: Service,
		ReviewService: Review,
		SubmissionService: Service,
		ScanPersistence: Service,
	});
	scanWorkflow._status = 'reviewing';
	return scanWorkflow;
}
for (const invalid of [
	{ quantity: 0 },
	{ quantity: 1.5 },
	{ quantity: undefined },
	{ name: ' ' },
	{ purchase_price: -1 },
]) {
	test(`review, failed edits and bulk confirmation reject invalid fields: ${JSON.stringify(invalid)}`, async () => {
		const item = { reviewId: 'item', name: 'Item', quantity: 1, ...invalid };
		const workflow = await reviewHarness(item);
		await workflow.confirmItem(item);
		assert.equal(workflow._status, 'reviewing');
		workflow.failedItemEditIndex = 0;
		await workflow.confirmItem(item);
		assert.equal(workflow._status, 'reviewing');
		assert.equal(workflow.failedItemEditIndex, 0);
		assert.equal(await workflow.confirmAllRemainingItems(item), 0);
	});
}
