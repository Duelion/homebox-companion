/**
 * Theme Color Utilities
 *
 * Dynamically extracts theme colors from DaisyUI themes at runtime.
 * Temporarily applies each theme to the document root to read actual
 * computed colors, ensuring accuracy regardless of DaisyUI version.
 */

import { AVAILABLE_THEMES, type ThemeName } from '$lib/stores/theme.svelte';

export interface ThemeColorSet {
	primary: string;
	secondary: string;
	accent: string;
}

export type ThemeColorMap = Record<ThemeName, ThemeColorSet>;

/**
 * Extracts theme colors by temporarily applying each theme to document root.
 *
 * DaisyUI themes only work when applied to the root element (html),
 * so we temporarily switch themes, read the colors, then restore.
 *
 * @returns Map of theme names to their primary/secondary/accent colors
 */
export function probeThemeColors(): ThemeColorMap {
	const root = document.documentElement;
	const originalTheme = root.getAttribute('data-theme');

	// Create probe elements that will inherit from root theme
	const container = document.createElement('div');
	container.style.cssText = 'position:absolute;visibility:hidden;pointer-events:none;';

	const primaryEl = document.createElement('div');
	primaryEl.className = 'bg-primary';
	const secondaryEl = document.createElement('div');
	secondaryEl.className = 'bg-secondary';
	const accentEl = document.createElement('div');
	accentEl.className = 'bg-accent';

	container.appendChild(primaryEl);
	container.appendChild(secondaryEl);
	container.appendChild(accentEl);
	document.body.appendChild(container);

	const colors = {} as ThemeColorMap;

	try {
		for (const themeName of AVAILABLE_THEMES) {
			// Temporarily apply theme to root
			root.setAttribute('data-theme', themeName);

			// Force style recalculation
			void primaryEl.offsetHeight;

			// Read computed colors
			colors[themeName] = {
				primary: getComputedStyle(primaryEl).backgroundColor,
				secondary: getComputedStyle(secondaryEl).backgroundColor,
				accent: getComputedStyle(accentEl).backgroundColor,
			};
		}
	} finally {
		// Restore original theme
		if (originalTheme) {
			root.setAttribute('data-theme', originalTheme);
		} else {
			root.removeAttribute('data-theme');
		}

		// Clean up probe elements
		document.body.removeChild(container);
	}

	return colors;
}

/**
 * Check if colors have been successfully loaded.
 */
export function hasValidColors(colors: ThemeColorMap): boolean {
	const entries = Object.entries(colors);
	if (entries.length === 0) return false;

	return entries.some(([, colorSet]) => {
		return (
			colorSet.primary !== 'rgba(0, 0, 0, 0)' &&
			colorSet.primary !== 'transparent' &&
			colorSet.primary !== ''
		);
	});
}
