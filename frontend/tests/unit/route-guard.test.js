import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

let moduleId = 0;
async function guards(status, authenticated = true) {
	const source = await readFile(
		new URL('../../src/lib/utils/routeGuard.ts', import.meta.url),
		'utf8'
	);
	const calls = [];
	const state = { status, locationId: 'loc-1', activeReviewDraft: { name: 'Keep edits' } };
	const id = `routeGuardTest${moduleId++}`;
	globalThis[id] = {
		goto: (...args) => calls.push(args),
		authStore: { isAuthenticated: authenticated, phase: 'signed_out' },
		scanWorkflow: { state },
		resolveNavHref: (path) => path,
	};
	const compiled = ts.transpile(source.replace(/^import[\s\S]*?;\s*$/gm, ''), {
		module: ts.ModuleKind.ES2022,
	});
	const module = await import(
		`data:text/javascript,${encodeURIComponent(`const { goto, authStore, scanWorkflow, resolveNavHref } = globalThis.${id};\n${compiled}`)}`
	);
	delete globalThis[id];
	return { ...module, calls, state };
}

test('Capture permits an existing review checkpoint without changing its state or redirecting', async () => {
	const h = await guards('reviewing');
	const before = structuredClone(h.state);
	assert.equal(h.routeGuards.capture(), true);
	assert.deepEqual(h.state, before);
	assert.deepEqual(h.calls, []);
});

test('corrective route and authentication redirects replace the invalid history entry', async () => {
	for (const [status, guard] of [
		['reviewing', 'location'],
		['capturing', 'review'],
		['reviewing', 'summary'],
	]) {
		const h = await guards(status);
		assert.equal(h.routeGuards[guard](), false);
		assert.equal(h.calls.length, 1);
		assert.deepEqual(h.calls[0][1], { replaceState: true });
	}
	const h = await guards('reviewing', false);
	assert.equal(h.applyRouteGuard({}), false);
	assert.deepEqual(h.calls, [['/', { replaceState: true }]]);
});
