import assert from 'node:assert/strict';
import test from 'node:test';
import { ESLint } from 'eslint';
import tsParser from 'typescript-eslint';
import svelteParser from 'svelte-eslint-parser';
import homeboxRules from '../../eslint/design-tokens.js';

const eslint = new ESLint({
	overrideConfigFile: true,
	overrideConfig: [
		{
			files: ['**/*.svelte'],
			languageOptions: { parser: svelteParser, parserOptions: { parser: tsParser.parser } },
			plugins: { homebox: homeboxRules },
			rules: { 'homebox/design-tokens': 'error' },
		},
		{
			files: ['**/*.ts', '**/*.js'],
			languageOptions: { parser: tsParser.parser },
			plugins: { homebox: homeboxRules },
			rules: { 'homebox/design-tokens': 'error' },
		},
	],
});

async function messages(source, filePath = 'Component.svelte') {
	const [result] = await eslint.lintText(source, { filePath });
	assert.equal(result.fatalErrorCount, 0, result.messages.map(({ message }) => message).join('\n'));
	return result.messages.filter(({ ruleId }) => ruleId === 'homebox/design-tokens');
}

test('flags discouraged utilities in Svelte class attributes and class directives', async () => {
	const found = await messages(
		`<div class="text-xs hover:!text-white/80 bg-black/60" class:text-sm={enabled} />\n` +
			`<span class={enabled ? 'bg-red-500' : 'bg-neutral-900'} />`
	);
	assert.deepEqual(
		found.map(({ message }) => message),
		[
			"Use 'text-caption' instead of 'text-xs'.",
			"Use 'text-neutral-*' instead of 'hover:!text-white/80'.",
			"Use 'bg-neutral-950/*' instead of 'bg-black/60'.",
			"Use 'text-body-sm' instead of 'text-sm'.",
			"Use 'error-*' instead of 'bg-red-500'.",
		]
	);
});

test('checks conditional and template strings in class helpers and named variant/style maps', async () => {
	const found = await messages(
		`const variants = { active: enabled ? 'bg-blue-500' : 'bg-neutral-900' };\n` +
			`const styles = { surface: \`text-sm \${active ? 'border-red-500' : ''}\` };\n` +
			`const result = clsx(enabled && 'min-h-[44px]', { 'text-xs': compact });\n` +
			`const prose = 'This red text-sm is documentation, not a class.';`,
		'Component.ts'
	);
	assert.deepEqual(
		found.map(({ message }) => message),
		[
			"Use 'accent or primary-*' instead of 'bg-blue-500'.",
			"Use 'text-body-sm' instead of 'text-sm'.",
			"Use 'error-*' instead of 'border-red-500'.",
			"Use 'min-h-touch or min-w-touch' instead of 'min-h-[44px]'.",
			"Use 'text-caption' instead of 'text-xs'.",
		]
	);
});

test('accepts token utilities, arbitrary values, variants, and unrelated attributes', async () => {
	const found = await messages(
		`<div title="text-xs and bg-black" class="md:text-body-sm !text-neutral-100 bg-neutral-950/60 min-h-touch text-[13px]" />`
	);
	assert.deepEqual(found, []);
});
