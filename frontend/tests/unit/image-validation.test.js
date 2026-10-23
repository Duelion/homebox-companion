import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

function harness(convert = async () => new Blob([new Uint8Array([0xff, 0xd8, 0xff, 1])])) {
	const source = readFileSync(
		new URL('../../src/lib/utils/validateCaptureImage.ts', import.meta.url),
		'utf8'
	);
	const { outputText } = ts.transpileModule(source, {
		compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
	});
	const exports = {};
	const decoded = [];
	let closed = 0;
	runInNewContext(outputText, {
		exports,
		File,
		Uint8Array,
		require: () => ({ __esModule: true, default: convert }),
		createImageBitmap: async (file) => {
			decoded.push(file);
			if (file.name.startsWith('corrupt')) throw new Error('decode failed');
			return { close: () => closed++ };
		},
	});
	return { validate: exports.validateCaptureImage, decoded, closed: () => closed };
}
const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 1]);
const heic = new Uint8Array([0, 0, 0, 24, ...Buffer.from('ftypheic'), 0, 0, 0, 0]);
test('rejects empty, oversized, unsupported and corrupt files before capture', async () => {
	const h = harness();
	await assert.rejects(h.validate(new File([], 'empty.jpg'), 10), /empty/);
	await assert.rejects(
		h.validate(new File([new Uint8Array(11)], 'large.jpg'), 0.00001),
		/too large/
	);
	await assert.rejects(
		h.validate(new File(['text'], 'fake.jpg', { type: 'image/jpeg' }), 10),
		/Invalid or unsupported/
	);
	await assert.rejects(h.validate(new File([jpeg], 'corrupt.jpg'), 10), /Unable to read/);
	assert.equal(h.decoded.length, 1);
});
test('recognizes supported signatures independently of declared MIME and releases decoded bitmaps', async () => {
	const h = harness();
	for (const [bytes, mime] of [
		[jpeg, 'image/jpeg'],
		[new Uint8Array([0x89, ...Buffer.from('PNG\r\n\x1a\n')]), 'image/png'],
		[Buffer.from('RIFF0000WEBP'), 'image/webp'],
		[Buffer.from('GIF89a'), 'image/gif'],
	]) {
		const validated = await h.validate(new File([bytes], 'photo.txt', { type: 'text/plain' }), 10);
		assert.equal(validated.type, mime);
	}
	assert.equal(h.closed(), 4);
});
test('HEIC/HEIF conversion validates the JPEG output and permits ordinary photos after failures', async () => {
	const h = harness();
	const converted = await h.validate(new File([heic], 'photo.heif', { type: 'image/heif' }), 10);
	assert.equal(converted.name, 'photo.jpg');
	assert.equal(converted.type, 'image/jpeg');
	assert.equal(h.closed(), 1);
	const broken = harness(async () => {
		throw new Error('bad HEIF');
	});
	await assert.rejects(
		broken.validate(new File([heic], 'broken.heic'), 10),
		/Unable to read this HEIC/
	);
	await broken.validate(new File([jpeg], 'working.jpg'), 10);
	assert.equal(broken.closed(), 1);
});
