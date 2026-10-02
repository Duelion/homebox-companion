import { parse } from 'svelte/compiler';

// Check declarations, not comments, URLs, selectors, or user-facing strings.
const literalColor = /#[\da-f]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab|lab|lch|color)\s*\(/i;

export function findCssTokenViolations(source, { stylesheet = false, theme = false } = {}) {
	const parsedSource = stylesheet ? `<style>${source}</style>` : source;
	const css = parse(parsedSource).css;
	const violations = [];
	function visit(node, inTheme = false) {
		if (node.type === 'Declaration') {
			if (theme && inTheme && node.property.startsWith('--color-')) return;
			const value = node.value
				.replace(/\/\*[\s\S]*?\*\//g, '')
				.replace(/url\([^)]*\)|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/gi, '');
			if (literalColor.test(value)) {
				violations.push({
					line: parsedSource.slice(0, node.start).split('\n').length,
					property: node.property,
				});
			}
		}
		const isTheme = inTheme || (node.type === 'Atrule' && node.name === 'theme');
		for (const child of node.children ?? node.block?.children ?? []) visit(child, isTheme);
	}
	if (css) visit(css);
	return violations;
}
