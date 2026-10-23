import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

function editor() {
	const source = readFileSync(
		new URL('../../src/lib/components/ThumbnailEditor.svelte', import.meta.url),
		'utf8'
	).match(/<script lang="ts">([\s\S]*?)<\/script>/)[1];
	const images = [];
	const saved = [];
	const drawn = [];
	let mount;
	let frameId = 0;
	const frames = new Map();
	const context = new Proxy(
		{},
		{ get: (_target, key) => (key === 'drawImage' ? (image) => drawn.push(image.src) : () => {}) }
	);
	const script = ts.transpile(
		source.replace(/^\s*import[\s\S]*?;\s*$/gm, '') +
			'\nexports.editor = { loadImage, saveCrop, rotateRight90, state: () => ({ selectedImageIndex, loadedImage, isImageLoading, imageError }), mount: () => { canvas = { getContext: () => context }; return mount(); } };',
		{ target: ts.ScriptTarget.ES2022 }
	);
	const exports = {};
	runInNewContext(script, {
		exports,
		$state: (value) => value,
		$derived: (value) => value,
		$props: () => ({
			images: [{ dataUrl: 'first' }, { dataUrl: 'second' }],
			onSave: (...args) => saved.push(args),
		}),
		onMount: (callback) => {
			mount = callback;
		},
		mount: () => mount(),
		window: { innerWidth: 400 },
		context,
		requestAnimationFrame: (callback) => {
			frames.set(++frameId, callback);
			return frameId;
		},
		cancelAnimationFrame: (id) => frames.delete(id),
		Image: class {
			width = 100;
			height = 100;
			constructor() {
				images.push(this);
			}
		},
		document: {
			createElement: () => ({
				getContext: () => context,
				toDataURL: () => 'data:image/jpeg;saved',
			}),
		},
		CANVAS_COLORS: {},
	});
	return { ...exports.editor, images, saved, drawn, frames };
}

test('a pending source switch cannot save old pixels under the new source index', () => {
	const h = editor();
	h.loadImage(0);
	h.images[0].onload();
	h.loadImage(1);
	h.rotateRight90();
	h.saveCrop();
	assert.equal(h.saved.length, 0);
	h.images[1].onload();
	h.rotateRight90();
	h.saveCrop();
	assert.equal(h.saved.length, 1);
	assert.equal(h.drawn.at(-1), 'second');
	assert.equal(h.saved[0][1], 1);
	assert.equal(h.saved[0][2].rotation, 90);
});

test('failed and superseded source loads cannot restore old pixels and the selected image can retry', () => {
	const h = editor();
	h.loadImage(0);
	const staleLoad = h.images[0].onload;
	h.loadImage(1);
	staleLoad();
	assert.equal(h.state().loadedImage, null);
	h.images[1].onerror();
	assert.equal(h.state().isImageLoading, false);
	assert.match(h.state().imageError, /Unable to load/);
	h.saveCrop();
	assert.equal(h.saved.length, 0);
	h.loadImage(1);
	h.images[2].onload();
	h.saveCrop();
	assert.equal(h.drawn.at(-1), 'second');
	assert.equal(h.saved[0][1], 1);
});

test('the initial canvas frame does not replace a source chosen before that frame', () => {
	const h = editor();
	h.mount();
	const initialFrame = [...h.frames.values()][0];
	h.loadImage(1);
	h.images[0].onload();
	initialFrame();
	assert.equal(h.images.length, 1);
	assert.equal(h.state().selectedImageIndex, 1);
	h.saveCrop();
	assert.equal(h.drawn.at(-1), 'second');
});

test('teardown cancels frames and invalidates pending image callbacks', () => {
	const h = editor();
	const cleanup = h.mount();
	h.loadImage(0);
	const staleLoad = h.images[0].onload;
	const staleError = h.images[0].onerror;
	cleanup();
	staleLoad();
	staleError();
	h.saveCrop();
	assert.equal(h.frames.size, 0);
	assert.equal(h.state().loadedImage, null);
	assert.equal(h.state().imageError, null);
	assert.equal(h.saved.length, 0);
});
