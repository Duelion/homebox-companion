/**
 * Canvas drawing color constants synchronized with the Tailwind design system.
 *
 * These values must be kept in sync with tailwind.config.js color definitions.
 * Canvas 2D context doesn't support CSS classes, so we use hex values here.
 */

/**
 * Design system color tokens for canvas operations.
 * @see tailwind.config.js for the source of truth
 */
export const CANVAS_COLORS = {
	/** neutral-950 - App background */
	background: '#0a0a0f',

	/** primary-500 - Primary color for strokes and highlights */
	primary: '#6366f1',

	/** primary-500 with 80% opacity for overlays */
	primaryOverlay: 'rgba(99, 102, 241, 0.8)',

	/** Black overlay for dimming areas */
	dimOverlay: 'rgba(0, 0, 0, 0.6)',
} as const;

export type CanvasColorKey = keyof typeof CANVAS_COLORS;
