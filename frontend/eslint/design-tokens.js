const CLASS_HELPERS = new Set(['classnames', 'clsx', 'cn']);
const CLASS_CONTEXT_NAMES = /(?:class|classes|classnames|classname|styles?|variants?)/i;

const discouraged = [
	[/^text-sm$/, 'text-body-sm'],
	[/^text-xs$/, 'text-caption'],
	[/^text-white(?:\/.*)?$/, 'text-neutral-*'],
	[/^bg-black(?:\/.*)?$/, 'bg-neutral-950/*'],
	[
		/^(?:bg|text|border|ring|fill|stroke|outline|divide|decoration|placeholder)-(?:amber|yellow)(?:-|\/|$)/,
		'warning-*',
	],
	[
		/^(?:bg|text|border|ring|fill|stroke|outline|divide|decoration|placeholder)-red(?:-|\/|$)/,
		'error-*',
	],
	[
		/^(?:bg|text|border|ring|fill|stroke|outline|divide|decoration|placeholder)-(?:green|emerald)(?:-|\/|$)/,
		'success-*',
	],
	[
		/^(?:bg|text|border|ring|fill|stroke|outline|divide|decoration|placeholder)-(?:cyan|blue)(?:-|\/|$)/,
		'accent or primary-*',
	],
	[/^min-[hw]-\[44px\]$/, 'min-h-touch or min-w-touch'],
];

function baseUtility(token) {
	// Tailwind variants may contain colons inside arbitrary selectors/values.
	let depth = 0;
	let segmentStart = 0;
	for (let index = 0; index < token.length; index += 1) {
		if (token[index] === '[') depth += 1;
		else if (token[index] === ']') depth = Math.max(0, depth - 1);
		else if (token[index] === ':' && depth === 0) segmentStart = index + 1;
	}
	return token.slice(segmentStart).replace(/^!/, '').replace(/!$/, '');
}

function splitClasses(value) {
	return value.match(/[^\s]+/g) ?? [];
}

function inspectString(value, report, node) {
	for (const token of splitClasses(value)) {
		const utility = baseUtility(token);
		const match = discouraged.find(([pattern]) => pattern.test(utility));
		if (match) {
			report({ node, token, replacement: match[1] });
		}
	}
}

function inspectExpression(expression, report) {
	if (!expression || typeof expression !== 'object') return;
	if (expression.type === 'Literal' && typeof expression.value === 'string') {
		inspectString(expression.value, report, expression);
		return;
	}
	if (expression.type === 'TemplateLiteral') {
		for (const quasi of expression.quasis ?? [])
			inspectString(quasi.value?.cooked ?? '', report, quasi);
		for (const item of expression.expressions ?? []) inspectExpression(item, report);
		return;
	}
	if (expression.type === 'ObjectExpression') {
		for (const property of expression.properties ?? []) {
			if (property.type === 'SpreadElement') {
				inspectExpression(property.argument, report);
				continue;
			}
			if (property.computed) inspectExpression(property.key, report);
			else if (property.key?.type === 'Literal' && typeof property.key.value === 'string') {
				inspectString(property.key.value, report, property.key);
			}
			inspectExpression(property.value, report);
		}
		return;
	}
	if (expression.type === 'ArrayExpression') {
		for (const element of expression.elements ?? []) inspectExpression(element, report);
		return;
	}
	if (expression.type === 'ConditionalExpression') {
		inspectExpression(expression.consequent, report);
		inspectExpression(expression.alternate, report);
		return;
	}
	if (expression.type === 'LogicalExpression' || expression.type === 'BinaryExpression') {
		inspectExpression(expression.left, report);
		inspectExpression(expression.right, report);
	}
}

function propertyName(node) {
	if (node?.type === 'Identifier') return node.name;
	if (node?.type === 'Literal') return String(node.value);
	if (typeof node?.name === 'string') return node.name;
	if (typeof node?.name?.name === 'string') return node.name.name;
	return '';
}

const designTokens = {
	meta: {
		type: 'problem',
		docs: { description: 'Require the frontend design-system utility tokens' },
		schema: [],
		messages: { discouraged: "Use '{{replacement}}' instead of '{{token}}'." },
	},
	create(context) {
		const report = ({ node, token, replacement }) =>
			context.report({ node, messageId: 'discouraged', data: { token, replacement } });

		function inspectSvelteAttribute(node) {
			const name = propertyName(node.key);
			if (name !== 'class' && name !== 'className') return;
			for (const part of node.value ?? []) {
				if (typeof part.value === 'string') inspectString(part.value, report, part);
				else if (part.expression) inspectExpression(part.expression, report);
			}
		}

		function inspectSvelteDirective(node) {
			if (node.kind !== 'Class') return;
			const name = propertyName(node.key);
			if (name) inspectString(name, report, node.key);
			for (const part of node.value ?? []) {
				if (part.expression) inspectExpression(part.expression, report);
			}
		}

		function inspectClassScriptNode(node) {
			if (
				node.type === 'CallExpression' &&
				node.callee.type === 'Identifier' &&
				CLASS_HELPERS.has(node.callee.name)
			) {
				for (const argument of node.arguments) inspectExpression(argument, report);
			}
			if (node.type === 'VariableDeclarator' && CLASS_CONTEXT_NAMES.test(propertyName(node.id))) {
				inspectExpression(node.init, report);
			}
			if (node.type === 'Property' && CLASS_CONTEXT_NAMES.test(propertyName(node.key))) {
				inspectExpression(node.value, report);
			}
		}

		return {
			SvelteAttribute: inspectSvelteAttribute,
			SvelteDirective: inspectSvelteDirective,
			SvelteClassDirective: inspectSvelteDirective,
			CallExpression: inspectClassScriptNode,
			VariableDeclarator: inspectClassScriptNode,
			Property: inspectClassScriptNode,
		};
	},
};

export default { rules: { 'design-tokens': designTokens } };
