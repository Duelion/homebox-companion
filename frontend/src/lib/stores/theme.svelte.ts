/**
 * Theme Store - Svelte 5 Class-based State
 *
 * Manages application theme using DaisyUI themes.
 * Persists theme preference to localStorage.
 * Matches Homebox theme system for visual consistency.
 */

// =============================================================================
// CONSTANTS
// =============================================================================

/** localStorage key for theme preference */
const THEME_STORAGE_KEY = 'hbc-theme';

/** Default theme if none is set */
const DEFAULT_THEME = 'homebox';

/** All available DaisyUI themes (matching Homebox) */
export const AVAILABLE_THEMES = [
	'homebox',
	'light',
	'dark',
	'cupcake',
	'bumblebee',
	'emerald',
	'corporate',
	'synthwave',
	'retro',
	'cyberpunk',
	'valentine',
	'halloween',
	'garden',
	'forest',
	'aqua',
	'lofi',
	'pastel',
	'fantasy',
	'wireframe',
	'black',
	'luxury',
	'dracula',
	'cmyk',
	'autumn',
	'business',
	'acid',
	'lemonade',
	'night',
	'coffee',
	'winter',
] as const;

export type ThemeName = (typeof AVAILABLE_THEMES)[number];

/** Theme metadata for UI display */
export interface ThemeInfo {
	name: ThemeName;
	label: string;
	isDark: boolean;
}

/** Theme metadata for all available themes */
export const THEME_INFO: ThemeInfo[] = [
	{ name: 'homebox', label: 'Homebox', isDark: true },
	{ name: 'light', label: 'Light', isDark: false },
	{ name: 'dark', label: 'Dark', isDark: true },
	{ name: 'cupcake', label: 'Cupcake', isDark: false },
	{ name: 'bumblebee', label: 'Bumblebee', isDark: false },
	{ name: 'emerald', label: 'Emerald', isDark: false },
	{ name: 'corporate', label: 'Corporate', isDark: false },
	{ name: 'synthwave', label: 'Synthwave', isDark: true },
	{ name: 'retro', label: 'Retro', isDark: false },
	{ name: 'cyberpunk', label: 'Cyberpunk', isDark: false },
	{ name: 'valentine', label: 'Valentine', isDark: false },
	{ name: 'halloween', label: 'Halloween', isDark: true },
	{ name: 'garden', label: 'Garden', isDark: false },
	{ name: 'forest', label: 'Forest', isDark: true },
	{ name: 'aqua', label: 'Aqua', isDark: true },
	{ name: 'lofi', label: 'Lofi', isDark: false },
	{ name: 'pastel', label: 'Pastel', isDark: false },
	{ name: 'fantasy', label: 'Fantasy', isDark: false },
	{ name: 'wireframe', label: 'Wireframe', isDark: false },
	{ name: 'black', label: 'Black', isDark: true },
	{ name: 'luxury', label: 'Luxury', isDark: true },
	{ name: 'dracula', label: 'Dracula', isDark: true },
	{ name: 'cmyk', label: 'CMYK', isDark: false },
	{ name: 'autumn', label: 'Autumn', isDark: false },
	{ name: 'business', label: 'Business', isDark: true },
	{ name: 'acid', label: 'Acid', isDark: false },
	{ name: 'lemonade', label: 'Lemonade', isDark: false },
	{ name: 'night', label: 'Night', isDark: true },
	{ name: 'coffee', label: 'Coffee', isDark: true },
	{ name: 'winter', label: 'Winter', isDark: false },
];

// =============================================================================
// THEME STORE CLASS
// =============================================================================

class ThemeStore {
	// =========================================================================
	// STATE
	// =========================================================================

	/** Current active theme */
	private _theme = $state<ThemeName>(DEFAULT_THEME);

	// =========================================================================
	// GETTERS
	// =========================================================================

	/** Get current theme name */
	get theme(): ThemeName {
		return this._theme;
	}

	/** Get current theme info */
	get themeInfo(): ThemeInfo {
		return THEME_INFO.find((t) => t.name === this._theme) ?? THEME_INFO[0];
	}

	/** Check if current theme is dark */
	get isDark(): boolean {
		return this.themeInfo.isDark;
	}

	// =========================================================================
	// METHODS
	// =========================================================================

	/**
	 * Initialize theme from localStorage and apply to document.
	 * Should be called once on app startup.
	 */
	initialize(): void {
		// Only run in browser
		if (typeof window === 'undefined') return;

		// Load from localStorage or use default
		const stored = localStorage.getItem(THEME_STORAGE_KEY);
		if (stored && AVAILABLE_THEMES.includes(stored as ThemeName)) {
			this._theme = stored as ThemeName;
		} else {
			this._theme = DEFAULT_THEME;
		}

		// Apply theme to document
		this.applyTheme(this._theme);
	}

	/**
	 * Set the theme and persist to localStorage.
	 */
	setTheme(theme: ThemeName): void {
		if (!AVAILABLE_THEMES.includes(theme)) {
			console.warn(`Invalid theme: ${theme}`);
			return;
		}

		this._theme = theme;

		// Persist to localStorage
		if (typeof window !== 'undefined') {
			localStorage.setItem(THEME_STORAGE_KEY, theme);
		}

		// Apply to document
		this.applyTheme(theme);
	}

	/**
	 * Apply theme to document element.
	 */
	private applyTheme(theme: ThemeName): void {
		if (typeof document === 'undefined') return;

		// DaisyUI uses data-theme attribute
		document.documentElement.setAttribute('data-theme', theme);

		// Also set color-scheme for native elements
		const isDark = THEME_INFO.find((t) => t.name === theme)?.isDark ?? true;
		document.documentElement.style.colorScheme = isDark ? 'dark' : 'light';
	}

	/**
	 * Cycle to next theme (useful for quick toggle).
	 */
	cycleTheme(): void {
		const currentIndex = AVAILABLE_THEMES.indexOf(this._theme);
		const nextIndex = (currentIndex + 1) % AVAILABLE_THEMES.length;
		this.setTheme(AVAILABLE_THEMES[nextIndex]);
	}

	/**
	 * Toggle between light and dark mode (uses 'light' and 'homebox' themes).
	 */
	toggleLightDark(): void {
		if (this.isDark) {
			this.setTheme('light');
		} else {
			this.setTheme('homebox');
		}
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const themeStore = new ThemeStore();

// =============================================================================
// CONVENIENCE EXPORTS
// =============================================================================

export const setTheme = (theme: ThemeName) => themeStore.setTheme(theme);
export const toggleLightDark = () => themeStore.toggleLightDark();
