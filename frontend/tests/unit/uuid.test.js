import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import { webcrypto } from 'node:crypto';
import ts from 'typescript';

const source = readFileSync(new URL('../../src/lib/utils/uuid.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
	compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});

function loadUuidWithCrypto(crypto) {
	const exports = {};
	runInNewContext(outputText, { exports, crypto, Uint8Array, Array });
	return exports.createUuidV4;
}

const uuidV4Pattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

test('prefers native crypto.randomUUID in secure contexts', () => {
	const nativeUuid = '17249a09-a18d-4456-93a3-4cb05a6357c4';
	const createUuidV4 = loadUuidWithCrypto({
		randomUUID: () => nativeUuid,
		getRandomValues: () => {
			throw new Error('Fallback must not run when native crypto.randomUUID exists');
		},
	});
	assert.equal(createUuidV4(), nativeUuid);
});

test('uses crypto.getRandomValues when crypto.randomUUID is missing on HTTP LAN', () => {
	const createUuidV4 = loadUuidWithCrypto({
		getRandomValues: (bytes) => webcrypto.getRandomValues(bytes),
	});
	const ids = new Set(Array.from({ length: 128 }, () => createUuidV4()));
	assert.equal(ids.size, 128);
	for (const id of ids) assert.match(id, uuidV4Pattern);
});

test('sets UUID version and variant bits correctly', () => {
	const createUuidV4 = loadUuidWithCrypto({
		getRandomValues: (bytes) => bytes.fill(0xff),
	});
	assert.equal(createUuidV4(), 'ffffffff-ffff-4fff-bfff-ffffffffffff');
});
