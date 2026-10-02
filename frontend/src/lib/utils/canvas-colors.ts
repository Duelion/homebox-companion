/**
 * Canvas drawing color constants synchronized with the Tailwind design system.
 *
 * app.css is the source of truth. tests/browser/design-tokens.spec.ts checks
 * these values and their alpha variants so token changes cannot silently drift.
 * Constants avoid DOM reads during module loading and remain usable during export.
 */

/**
 * Design system color tokens for canvas operations.
 * @see ../../app.css for the source of truth
 */
export const CANVAS_COLORS = {
	/** neutral-950 - App background */
	background: '#0a0a0f',

	/** primary-500 - Primary color for strokes and highlights */
	primary: '#6366f1',

	/** primary-500 with 80% opacity for overlays */
	primaryOverlay: 'rgba(99, 102, 241, 0.8)',

	/** neutral-950 with 60% opacity for dimming areas */
	dimOverlay: 'rgba(10, 10, 15, 0.6)',
} as const;

export type CanvasColorKey = keyof typeof CANVAS_COLORS;
