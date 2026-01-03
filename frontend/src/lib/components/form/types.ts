/**
 * Shared types for form components
 *
 * Note on null handling: Form inputs bind to string | null | undefined values.
 * HTML inputs will coerce null to empty string on user edit. Parent components
 * should handle this by normalizing empty strings to null before API submission
 * if the API expects null for "no value".
 */

/**
 * Size variant for form components.
 * - 'sm': Compact layout for inline forms (e.g., approval panel)
 * - 'md': Standard layout for full-page forms (e.g., review page)
 */
export type FormSize = 'sm' | 'md';

/** Returns appropriate input class based on size */
export function getInputClass(size: FormSize): string {
	return size === 'sm' ? 'input-sm' : 'input';
}

/** Returns appropriate label class based on size */
export function getLabelClass(size: FormSize): string {
	return size === 'sm' ? 'label-sm' : 'label';
}

/**
 * Returns all form-related classes as an object for more flexible usage.
 * Useful when components need multiple class types.
 */
export function getFormClasses(size: FormSize) {
	return {
		input: size === 'sm' ? 'input-sm' : 'input',
		label: size === 'sm' ? 'label-sm' : 'label',
		spacing: size === 'sm' ? 'space-y-2.5' : 'space-y-5',
		gridGap: size === 'sm' ? 'gap-2.5' : 'gap-3',
	};
}
