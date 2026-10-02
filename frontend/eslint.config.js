import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import svelteParser from 'svelte-eslint-parser';
import tailwindcss from 'eslint-plugin-tailwindcss';
import globals from 'globals';
import homeboxRules from './eslint/design-tokens.js';

/** @type {import('eslint').Linter.Config[]} */
export default [
	// Base JS recommended rules
	js.configs.recommended,

	// TypeScript recommended rules
	...tseslint.configs.recommended,

	// Svelte recommended rules
	...svelte.configs['flat/recommended'],

	// Require shared app tokens in markup and class-oriented script values.
	{
		plugins: { homebox: homeboxRules },
		rules: { 'homebox/design-tokens': 'error' },
	},

	// Tailwind CSS plugin - flat config presets
	tailwindcss.configs.recommended,

	// Global config for JS/TS files
	{
		files: ['**/*.js', '**/*.ts'],
		languageOptions: {
			ecmaVersion: 2022,
			sourceType: 'module',
			globals: {
				...globals.browser,
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

	// Node globals belong to tooling and tests, not browser application code.
	{
		files: ['*.config.js', '*.config.ts', 'eslint/**/*.js', 'tests/**/*.{js,ts}'],
		languageOptions: { globals: globals.node },
	},
	// Start typed linting with promise safety in application TypeScript.
	{
		files: ['src/**/*.ts'],
		languageOptions: {
			parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
		},
		rules: {
			'@typescript-eslint/no-floating-promises': 'error',
			'@typescript-eslint/no-misused-promises': 'error',
		},
	},
	// Tailwind-specific settings
	{
		settings: {
			tailwindcss: {
				// Tailwind v4 configuration and custom utilities live in this stylesheet.
				cssConfigPath: './src/app.css',
				// Support class attributes in Svelte templates
				functions: ['classnames', 'clsx', 'cn'],
				// Validate classes in Svelte files
				attributes: ['class', 'className'],
			},
		},
		rules: {
			// Catch invalid/non-existent Tailwind classes
			'tailwindcss/no-custom-classname': [
				'warn',
				{
					// Allow these custom utility classes from app.css
					whitelist: [
						'card-surface',
						'scanner-video',
						'btn-icon',
						'btn-icon-touch',
						'input',
						'input-error',
						'input-sm',
						'input-expandable',
						'input-with-icon',
						'label',
						'label-sm',
						'label-chip',
						'label-chip-selected',
						'selectable-item',
						'selectable-item-selected',
						'chat-bubble',
						'chat-bubble-user',
						'chat-meta',
						'chat-tools-section',
						'chat-tools-summary',
						'chat-tools-grid',
						'chat-tool-badge',
						'chat-approval-badge',
						'animate-in',
						'glass',
						'pb-safe',
						'pt-safe',
						'bottom-nav-offset',
						'skeleton',
						'checkmark-draw',
						'success-scale',
						'page-content',
						'fixed-bottom-panel',
						'chat-input-keyboard-aware',
						'empty-state',
						'slider-primary',
						'complete-pop',
						'animation-delay-0',
						'animation-delay-100',
						'animation-delay-150',
						'animation-delay-160',
						'animation-delay-200',
						'animation-delay-300',
						'animation-delay-320',
						'animation-delay-400',
						'loading-spinner',
						'typing-ellipsis',
						'typing-dot',
						'tool-spinner',
						'streaming-glow',
						'tool-accordion',
						'approval-badge',
						'toast-enter',
						'toast-exit',
						'toast-progress',
						'vt-enabled',
						'markdown-content',
					],
				},
			],
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
			// Keep suppressions tied to diagnostics that still exist.
			'svelte/no-unused-svelte-ignore': 'error',
		},
	},

	// Ignore build output and dependencies
	{
		ignores: ['build/**', '.svelte-kit/**', 'node_modules/**'],
	},
];
