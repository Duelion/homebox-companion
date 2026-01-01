import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import svelteParser from 'svelte-eslint-parser';
import tailwindcss from 'eslint-plugin-tailwindcss';
import globals from 'globals';

/** @type {import('eslint').Linter.Config[]} */
export default [
	// Base JS recommended rules
	js.configs.recommended,

	// TypeScript recommended rules
	...tseslint.configs.recommended,

	// Svelte recommended rules
	...svelte.configs['flat/recommended'],

	// Tailwind CSS plugin - flat config presets
	...tailwindcss.configs['flat/recommended'],

	// Global config for JS/TS files
	{
		files: ['**/*.js', '**/*.ts'],
		languageOptions: {
			ecmaVersion: 2022,
			sourceType: 'module',
			globals: {
				...globals.browser,
				...globals.node,
			},
			parser: tseslint.parser,
			parserOptions: {
				project: false,
			},
		},
	},

	// Svelte files config
	{
		files: ['**/*.svelte'],
		languageOptions: {
			parser: svelteParser,
			parserOptions: {
				parser: tseslint.parser,
			},
			globals: {
				...globals.browser,
				...globals.node,
				// DOM types used in TypeScript type annotations
				HTMLInputElement: 'readonly',
				HTMLTextAreaElement: 'readonly',
				HTMLDivElement: 'readonly',
				HTMLPreElement: 'readonly',
				HTMLVideoElement: 'readonly',
				HTMLCanvasElement: 'readonly',
				HTMLImageElement: 'readonly',
				MouseEvent: 'readonly',
				KeyboardEvent: 'readonly',
				TouchEvent: 'readonly',
				WheelEvent: 'readonly',
				TouchList: 'readonly',
				Event: 'readonly',
				File: 'readonly',
				Blob: 'readonly',
				Image: 'readonly',
				Document: 'readonly',
				CanvasRenderingContext2D: 'readonly',
			},
		},
	},

	// Tailwind-specific settings
	{
		settings: {
			tailwindcss: {
				// Path to your tailwind config (relative to eslint.config.js)
				config: 'tailwind.config.js',
				// Support class attributes in Svelte templates
				callees: ['classnames', 'clsx', 'cn'],
				// Validate classes in Svelte files
				classRegex: '^class(Name)?$',
			},
		},
		rules: {
			// Catch invalid/non-existent Tailwind classes
			'tailwindcss/no-custom-classname': ['warn', {
				// Allow these custom utility classes from app.css
				whitelist: [
					'btn-icon',
					'input',
					'input-error',
					'input-expandable',
					'label',
					'label-chip',
					'label-chip-selected',
					'animate-in',
					'glass',
					'pb-safe',
					'pt-safe',
					'bottom-nav-offset',
					'skeleton',
					'stagger-\\d+',
					'animate-stagger',
					'checkmark-draw',
					'success-scale',
					'success-badge',
					'page-content',
					'fixed-bottom-panel',
					'empty-state',
					'complete-pop',
					'vt-enabled',
				],
			}],
			// Enforce consistent class ordering - handled by prettier-plugin-tailwindcss
			'tailwindcss/classnames-order': 'off',
			// Warn about conflicting classes like "p-2 p-4"
			'tailwindcss/enforces-negative-arbitrary-values': 'warn',
			// Suggest shorthand like "mx-2" instead of "ml-2 mr-2"
			'tailwindcss/enforces-shorthand': 'warn',
			// Allow arbitrary values
			'tailwindcss/no-arbitrary-value': 'off',
			// Warn about contradicting classes
			'tailwindcss/no-contradicting-classname': 'error',
		},
	},

	// TypeScript rule adjustments
	{
		rules: {
			'@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
			'@typescript-eslint/no-explicit-any': 'off',
		},
	},

	// Svelte-specific rule overrides (only truly acceptable exceptions)
	{
		files: ['**/*.svelte', '**/*.svelte.ts'],
		rules: {
			// Unused svelte-ignore comments are harmless noise
			'svelte/no-unused-svelte-ignore': 'off',
		},
	},

	// Ignore build output and dependencies
	{
		ignores: [
			'build/**',
			'.svelte-kit/**',
			'node_modules/**',
		],
	},
];
