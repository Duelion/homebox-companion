/**
 * Structured logger with debug gating for production environments.
 * 
 * Debug mode is enabled when:
 * - localStorage.getItem('debug') === 'true', OR
 * - URL contains ?debug=true query parameter
 * 
 * This prevents verbose logs from flooding the console in production
 * while still allowing developers to enable debug output when needed.
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LoggerOptions {
	/** Prefix for all log messages from this logger */
	prefix: string;
}

/**
 * Check if debug mode is enabled.
 * Caches result to avoid repeated localStorage/URL checks.
 */
let debugModeCache: boolean | null = null;

function isDebugMode(): boolean {
	if (debugModeCache !== null) {
		return debugModeCache;
	}

	// Check localStorage first (persists across sessions)
	if (typeof localStorage !== 'undefined') {
		const stored = localStorage.getItem('debug');
		if (stored === 'true') {
			debugModeCache = true;
			return true;
		}
	}

	// Check URL query parameter (useful for one-off debugging)
	if (typeof window !== 'undefined' && window.location) {
		const params = new URLSearchParams(window.location.search);
		if (params.get('debug') === 'true') {
			debugModeCache = true;
			return true;
		}
	}

	debugModeCache = false;
	return false;
}

/**
 * Reset debug mode cache (useful for testing or when settings change)
 */
export function resetDebugModeCache(): void {
	debugModeCache = null;
}

/**
 * Enable debug mode programmatically
 */
export function enableDebugMode(): void {
	if (typeof localStorage !== 'undefined') {
		localStorage.setItem('debug', 'true');
	}
	debugModeCache = true;
}

/**
 * Disable debug mode programmatically
 */
export function disableDebugMode(): void {
	if (typeof localStorage !== 'undefined') {
		localStorage.removeItem('debug');
	}
	debugModeCache = false;
}

/**
 * Create a namespaced logger instance.
 * 
 * @example
 * const log = createLogger({ prefix: 'ScanWorkflow' });
 * log.debug('Starting analysis'); // Only logs in debug mode
 * log.error('Failed:', error);    // Always logs
 */
export function createLogger(options: LoggerOptions) {
	const { prefix } = options;
	const tag = `[${prefix}]`;

	return {
		/**
		 * Debug-level log - only outputs when debug mode is enabled.
		 * Use for verbose operational logs like request/response details,
		 * state transitions, timing info, etc.
		 */
		debug: (...args: unknown[]): void => {
			if (isDebugMode()) {
				console.log(tag, ...args);
			}
		},

		/**
		 * Info-level log - only outputs when debug mode is enabled.
		 * Use for significant but non-error events.
		 */
		info: (...args: unknown[]): void => {
			if (isDebugMode()) {
				console.info(tag, ...args);
			}
		},

		/**
		 * Warning-level log - always outputs.
		 * Use for recoverable issues or deprecated usage.
		 */
		warn: (...args: unknown[]): void => {
			console.warn(tag, ...args);
		},

		/**
		 * Error-level log - always outputs.
		 * Use for actual errors that need attention.
		 * Note: Detailed stack traces are only shown in debug mode.
		 */
		error: (message: string, error?: unknown): void => {
			if (isDebugMode() && error instanceof Error) {
				// In debug mode, show full error details
				console.error(tag, message, error);
				if (error.stack) {
					console.error(tag, 'Stack:', error.stack);
				}
			} else if (error) {
				// In production, show minimal error info
				const errorMsg = error instanceof Error ? error.message : String(error);
				console.error(tag, message, errorMsg);
			} else {
				console.error(tag, message);
			}
		},

		/**
		 * Check if debug mode is currently enabled
		 */
		isDebugEnabled: isDebugMode,
	};
}

/**
 * Pre-configured loggers for common modules.
 * Import these directly for convenience.
 */
export const apiLogger = createLogger({ prefix: 'API' });
export const workflowLogger = createLogger({ prefix: 'ScanWorkflow' });
