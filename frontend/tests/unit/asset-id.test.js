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
			{ name: 'Valid first', asset_id: '032-303' },
			{ name: 'Invalid second', asset_id: '032-REVIEW-3' },
		],
		'location',
		null
	);
	assert.equal(result.success, false);
	assert.equal(result.failCount, 2);
	assert.match(result.errors[0], /invalid asset ID/);
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
