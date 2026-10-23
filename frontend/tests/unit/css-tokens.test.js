import assert from 'node:assert/strict';
import test from 'node:test';
import { findCssTokenViolations } from '../../eslint/css-tokens.js';

test('raw colors are allowed only in the central theme color definitions', () => {
	const css = '@theme { --color-brand: #abcdef; --shadow-glow: 0 0 8px rgb(1 2 3); }';
	assert.deepEqual(
		findCssTokenViolations(css, { stylesheet: true, theme: true }).map((v) => v.property),
		['--shadow-glow']
	);
	assert.equal(findCssTokenViolations(css, { stylesheet: true }).length, 2);
});

test('checks component declarations and keyframes without flagging text or URL fragments', () => {
	const component = `<p>Example #ffffff</p><style>
	/* example: #fff */
	p { color: var(--color-primary); content: '#fff'; filter: url(#abc); }
	@keyframes glow { to { box-shadow: 0 0 8px rgba(1, 2, 3, .5); } }
	</style>`;
	assert.deepEqual(
		findCssTokenViolations(component).map((v) => v.property),
		['box-shadow']
	);
});
