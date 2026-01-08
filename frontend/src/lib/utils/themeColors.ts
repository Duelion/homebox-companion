/**
 * Theme Color Utilities
 *
 * Dynamically extracts theme colors from DaisyUI themes at runtime.
 * Uses getComputedStyle to read actual CSS values, ensuring accuracy
 * regardless of DaisyUI version or configuration.
 */

import { AVAILABLE_THEMES, type ThemeName } from '$lib/stores/theme.svelte';

export interface ThemeColorSet {
	primary: string;
	secondary: string;
	accent: string;
}

export type ThemeColorMap = Record<ThemeName, ThemeColorSet>;

/**
 * Probes the DOM to extract actual theme colors from DaisyUI CSS.
 *
 * Creates hidden elements with data-theme attributes and reads
 * their computed background colors. This works regardless of
 * how DaisyUI defines its theme variables internally.
 *
 * @returns Map of theme names to their primary/secondary/accent colors
 */
export function probeThemeColors(): ThemeColorMap {
	// Create a hidden container for probing
	const container = document.createElement('div');
	container.style.cssText = 'position:absolute;visibility:hidden;pointer-events:none;width:0;height:0;overflow:hidden;';
	document.body.appendChild(container);

	const colors = {} as ThemeColorMap;

	try {
		for (const themeName of AVAILABLE_THEMES) {
			// Create a themed container
			const themeContainer = document.createElement('div');
			themeContainer.setAttribute('data-theme', themeName);

			// Create probe elements for each color
			const primaryEl = document.createElement('div');
			primaryEl.className = 'bg-primary';

			const secondaryEl = document.createElement('div');
			secondaryEl.className = 'bg-secondary';

			const accentEl = document.createElement('div');
			accentEl.className = 'bg-accent';

			// Assemble and attach to DOM
			themeContainer.appendChild(primaryEl);
			themeContainer.appendChild(secondaryEl);
			themeContainer.appendChild(accentEl);
			container.appendChild(themeContainer);

			// Read computed styles
			colors[themeName] = {
				primary: getComputedStyle(primaryEl).backgroundColor,
				secondary: getComputedStyle(secondaryEl).backgroundColor,
				accent: getComputedStyle(accentEl).backgroundColor,
			};
		}
	} finally {
		// Always clean up
		document.body.removeChild(container);
	}

	return colors;
}

/**
 * Check if colors have been successfully loaded.
 * Returns false if the map is empty or all colors are transparent/empty.
 */
export function hasValidColors(colors: ThemeColorMap): boolean {
	const entries = Object.entries(colors);
	if (entries.length === 0) return false;

	// Check if at least one theme has non-transparent colors
	return entries.some(([, colorSet]) => {
		return (
			colorSet.primary !== 'rgba(0, 0, 0, 0)' &&
			colorSet.primary !== 'transparent' &&
			colorSet.primary !== ''
		);
	});
}
