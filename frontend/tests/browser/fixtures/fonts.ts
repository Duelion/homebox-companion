import { readFileSync } from 'node:fs';

// Latin subsets of the app's Google Fonts, pinned locally for offline, repeatable rendering.
// Sources and OFL licenses live alongside the files in ../assets/fonts.
export const fontCss = [
	['Inter', 'inter', '100 900'],
	['Outfit', 'outfit', '100 900'],
	['JetBrains Mono', 'jetbrainsmono', '100 800'],
]
	.map(([family, file, weight]) => {
		const data = readFileSync(new URL(`../assets/fonts/${file}-latin.woff2`, import.meta.url));
		return `@font-face { font-family: '${family}'; font-style: normal; font-weight: ${weight}; font-display: block; src: url(data:font/woff2;base64,${data.toString('base64')}) format('woff2'); }`;
	})
	.join('\n');
