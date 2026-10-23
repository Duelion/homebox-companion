import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(
	new URL('../../src/lib/utils/viewTransition.ts', import.meta.url),
	'utf8'
);
const { startNavigationTransition } = await import(
	`data:text/javascript,${encodeURIComponent(ts.transpile(source, { module: ts.ModuleKind.ES2022 }))}`
);

function deferred() {
	let resolve;
	let reject;
	const promise = new Promise((done, fail) => {
		resolve = done;
		reject = fail;
	});
	return { promise, resolve, reject };
}

function transitionHarness(complete) {
	const ready = deferred();
	let update;
	let observedReady;
	const navigation = startNavigationTransition((callback) => {
		update = callback;
		return {
			ready: {
				catch(handler) {
					observedReady = ready.promise.catch(handler);
					return observedReady;
				},
			},
		};
	}, complete);
	return { navigation, update, ready, observedReady };
}

test('a skipped transition handles AbortError and still completes the page update', async () => {
	const complete = deferred();
	const transition = transitionHarness(complete.promise);
	let updated = false;
	const update = transition.update().then(() => (updated = true));
	await transition.navigation;
	transition.ready.reject(new DOMException('New ViewTransition started', 'AbortError'));
	await transition.observedReady;
	assert.equal(updated, false);
	complete.resolve();
	await update;
	assert.equal(updated, true);
});

test('a superseded SvelteKit navigation does not reject its visual update callback', async () => {
	const complete = deferred();
	const transition = transitionHarness(complete.promise);
	const update = transition.update();
	await transition.navigation;
	complete.reject(new Error('navigation aborted'));
	transition.ready.resolve();
	await Promise.all([update, transition.observedReady]);
});

test('cancellation before the browser invokes its update callback is observed immediately', async () => {
	const complete = deferred();
	const transition = transitionHarness(complete.promise);
	complete.reject(new Error('navigation aborted'));
	// Cross an event-loop boundary before the browser's deferred update callback.
	// Node's test runner fails this test if the rejection is left unhandled.
	await new Promise(setImmediate);
	await transition.update();
	await transition.navigation;
	transition.ready.resolve();
	await transition.observedReady;
});

test('an unexpected failure before the update callback still rejects that callback', async () => {
	const complete = deferred();
	const transition = transitionHarness(complete.promise);
	const reason = new Error('Unexpected early navigation failure');
	complete.reject(reason);
	await new Promise(setImmediate);
	await assert.rejects(transition.update(), (error) => error === reason);
	await transition.navigation;
	transition.ready.resolve();
	await transition.observedReady;
});

test('unexpected ready and navigation failures remain observable', async () => {
	for (const reason of [
		new DOMException('Invalid transition', 'InvalidStateError'),
		new Error('AbortError'),
	]) {
		const transition = transitionHarness(Promise.resolve());
		const rejected = assert.rejects(transition.observedReady, (error) => error === reason);
		transition.ready.reject(reason);
		await rejected;
		await transition.update();
		await transition.navigation;
	}
	for (const reason of [new Error('Navigation failed'), new TypeError('navigation aborted')]) {
		const complete = deferred();
		const transition = transitionHarness(complete.promise);
		const rejected = assert.rejects(transition.update(), (error) => error === reason);
		complete.reject(reason);
		transition.ready.resolve();
		await Promise.all([rejected, transition.navigation, transition.observedReady]);
	}
});
