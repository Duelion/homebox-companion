import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { compile, parse } from 'svelte/compiler';
import { render } from 'svelte/server';

const source = await readFile(
	new URL('../../src/routes/capture/+page.svelte', import.meta.url),
	'utf8'
);

function findQuantityInput(node) {
	if (!node || typeof node !== 'object') return null;
	if (
		node.type === 'RegularElement' &&
		node.name === 'input' &&
		node.attributes.some(
			(attribute) =>
				attribute.name === 'value' &&
				attribute.value?.expression?.property?.name === 'quantityOverride'
		)
	) {
		return node;
	}
	return Object.values(node).flat().map(findQuantityInput).find(Boolean);
}

// Render the actual capture input, not a copy of its lock rule. The browser tests cover
// event handling, recovery, review and submission; this checks the rendered state without a browser.
const input = findQuantityInput(parse(source, { modern: true }).fragment);
assert.ok(input, 'Capture must expose the quantity override input');
const compiled = compile(
	`<script>let { image, isAnalyzing, status, imageStatuses, index } = $props();</script>
	${source.slice(input.start, input.end)}`,
	{ generate: 'server' }
);
const code = compiled.js.code.replaceAll(
	"'svelte/internal/server'",
	JSON.stringify(import.meta.resolve('svelte/internal/server'))
);
const { default: QuantityInput } = await import(`data:text/javascript,${encodeURIComponent(code)}`);

function isDisabled(status, imageStatuses = {}, index = 0) {
	const { body } = render(QuantityInput, {
		props: {
			image: { quantityOverride: 2 },
			isAnalyzing: status === 'analyzing',
			status,
			imageStatuses,
			index,
		},
	});
	assert.match(body, /value="2"/);
	return /\sdisabled(?:\s|>|=)/.test(body);
}

test('partial analysis locks only the successful photo group', () => {
	const statuses = { 0: 'success', 1: 'failed' };
	assert.equal(isDisabled('partial_analysis', statuses, 0), true);
	assert.equal(isDisabled('partial_analysis', statuses, 1), false);
});

test('quantity stays locked during analysis and the completed review transition', () => {
	assert.equal(isDisabled('analyzing', { 0: 'pending' }), true);
	assert.equal(isDisabled('analyzing', { 0: 'success' }), true);
	assert.equal(isDisabled('reviewing', { 0: 'success' }), true);
	assert.equal(isDisabled('reviewing'), true);
});

test('a fresh capture can edit quantity even with statuses left by interrupted recovery', () => {
	assert.equal(isDisabled('capturing'), false);
	assert.equal(isDisabled('capturing', { 0: 'success' }), false);
	assert.equal(isDisabled('capturing', { 0: 'failed' }), false);
});
