import { readFileSync } from 'node:fs';
import { test, expect } from '@playwright/test';
import { CANVAS_COLORS } from '../../src/lib/utils/canvas-colors';

test('canvas colors and alpha variants match the CSS design tokens', () => {
	const css = readFileSync('src/app.css', 'utf8');
	expect(css).not.toContain('@utility rounded-sm');
	function token(name: string): string {
		const value = css.match(new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6});`, 'i'))?.[1];
		expect(value, `Missing CSS color token ${name}`).toBeTruthy();
		return value!;
	}
	function alpha(hex: string, opacity: number): string {
		const channels = hex
			.slice(1)
			.match(/../g)!
			.map((channel) => parseInt(channel, 16));
		return `rgba(${channels.join(', ')}, ${opacity})`;
	}
	expect(CANVAS_COLORS.background).toBe(token('neutral-950'));
	expect(CANVAS_COLORS.primary).toBe(token('primary-500'));
	expect(CANVAS_COLORS.primaryOverlay).toBe(alpha(token('primary-500'), 0.8));
	expect(CANVAS_COLORS.dimOverlay).toBe(alpha(token('neutral-950'), 0.6));
});
