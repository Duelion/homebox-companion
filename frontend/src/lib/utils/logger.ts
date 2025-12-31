/**
 * Structured frontend logger with single log level control.
 * 
 * ## Log Level Control
 * 
 * **HBC_LOG_LEVEL** (synced from backend via setLogLevel):
 * Controls which logs are stored in the ring buffer AND shown in console.
 * Logs below this level are completely ignored.
 * 
 * Example: If HBC_LOG_LEVEL=DEBUG:
 * - DEBUG logs are stored in the ring buffer (viewable in Settings)
 * - DEBUG logs are shown in browser console
 * 
 * Example: If HBC_LOG_LEVEL=INFO:
 * - DEBUG logs are completely ignored (not buffered, not shown)
 * 
 * Logs are stored in a ring buffer (500 entries) for viewing in Settings.
 * Log level is synced from backend config at app startup.
 */

type LogLevel = 'TRACE' | 'DEBUG' | 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR' | 'CRITICAL';

/**
 * Log entry stored in the ring buffer.
 */
export interface LogEntry {
	timestamp: string;   // ISO 8601
	level: LogLevel;
	module: string;      // Logger prefix
	message: string;
	error?: string;      // Serialized error/stack
}

/**
 * Loguru-compatible log levels with numeric values.
 */
const LOG_LEVELS = {
	TRACE: 5,
	DEBUG: 10,
	INFO: 20,
	SUCCESS: 25,
	WARNING: 30,
	ERROR: 40,
	CRITICAL: 50,
} as const;

/**
 * Ring buffer for storing recent logs.
 */
const LOG_BUFFER_SIZE = 500;
/** Batch cleanup threshold - clean up 50 entries at once to avoid O(n) shift on every add */
const LOG_BUFFER_CLEANUP_BATCH = 50;
const logBuffer: LogEntry[] = [];

/**
 * Current log level threshold (synced from backend config).
 */
let currentLogLevel: (typeof LOG_LEVELS)[keyof typeof LOG_LEVELS] = LOG_LEVELS.INFO;

interface LoggerOptions {
	/** Prefix for all log messages from this logger */
	prefix: string;
}

/**
 * Add a log entry to the ring buffer.
 * Uses batch cleanup to avoid O(n) shift on every entry.
 */
function addToBuffer(entry: LogEntry): void {
	logBuffer.push(entry);
	// Batch cleanup to avoid frequent O(n) shifts
	if (logBuffer.length > LOG_BUFFER_SIZE + LOG_BUFFER_CLEANUP_BATCH) {
		logBuffer.splice(0, LOG_BUFFER_CLEANUP_BATCH);
	}
}

/**
 * Get all logs from the buffer.
 */
export function getLogBuffer(): readonly LogEntry[] {
	return [...logBuffer];
}

/**
 * Clear all logs from the buffer.
 */
export function clearLogBuffer(): void {
	logBuffer.length = 0;
}

/**
 * Export logs as JSON string for download.
 */
export function exportLogs(): string {
	return JSON.stringify(logBuffer, null, 2);
}

/**
 * Set the log level threshold from backend config.
 * Warns if an invalid level is provided.
 */
export function setLogLevel(level: string): void {
	const normalized = level.toUpperCase() as keyof typeof LOG_LEVELS;
	if (normalized in LOG_LEVELS) {
		currentLogLevel = LOG_LEVELS[normalized];
	} else {
		console.warn(`[Logger] Unknown log level "${level}", keeping current level`);
	}
}

/**
 * Check if a log level should be output based on current threshold.
 */
function shouldLog(level: LogLevel): boolean {
	return LOG_LEVELS[level] >= currentLogLevel;
}

/** Max length for JSON-stringified objects in log messages */
const MAX_JSON_LENGTH = 1000;

/**
 * Safely stringify an object with length limit.
 */
function safeStringify(obj: object): string {
	try {
		const str = JSON.stringify(obj);
		if (str.length > MAX_JSON_LENGTH) {
			return str.substring(0, MAX_JSON_LENGTH) + '...[truncated]';
		}
		return str;
	} catch {
		return '[Circular]';
	}
}

/**
 * Serialize an error including its cause chain.
 */
function serializeError(error: Error, depth = 0): string {
	// Prevent infinite recursion on malformed cause chains
	if (depth > 5) return '[max cause depth]';

	const parts = [error.stack || error.message];
	if (error.cause instanceof Error) {
		parts.push(`Caused by: ${serializeError(error.cause, depth + 1)}`);
	}
	return parts.join('\n');
}

/**
 * Create a namespaced logger instance.
 * 
 * @example
 * const log = createLogger({ prefix: 'ScanWorkflow' });
 * log.debug('Starting analysis'); // Only logs if level >= DEBUG
 * log.error('Failed:', error);    // Always logs
 */
export function createLogger(options: LoggerOptions) {
	const { prefix } = options;
	const tag = `[${prefix}]`;

	/**
	 * Helper to format and log a message.
	 */
	function logMessage(level: LogLevel, ...args: unknown[]): void {
		// Check if this level should be logged FIRST (before expensive processing)
		if (!shouldLog(level)) {
			return;
		}

		// Single-pass: find error and build message args
		let errorArg: Error | undefined;
		const messageParts: string[] = [];

		for (const arg of args) {
			if (arg instanceof Error) {
				// Keep only the first error for structured logging
				errorArg = errorArg ?? arg;
			} else if (typeof arg === 'string') {
				messageParts.push(arg);
			} else if (typeof arg === 'object' && arg !== null) {
				messageParts.push(safeStringify(arg));
			} else {
				messageParts.push(String(arg));
			}
		}

		const message = messageParts.join(' ');

		// Format timestamp
		const timestamp = new Date().toISOString();

		// Serialize error with cause chain if present
		const errorStr = errorArg ? serializeError(errorArg) : undefined;

		// Add to ring buffer
		addToBuffer({
			timestamp,
			level,
			module: prefix,
			message,
			error: errorStr,
		});

		// Output to console (single log level controls both buffer and console)
		switch (level) {
			case 'TRACE':
			case 'DEBUG':
				// Use console.debug to allow filtering in browser DevTools
				console.debug(tag, message, ...(errorArg ? [errorArg] : []));
				break;
			case 'INFO':
			case 'SUCCESS':
				console.info(tag, message, ...(errorArg ? [errorArg] : []));
				break;
			case 'WARNING':
				console.warn(tag, message, ...(errorArg ? [errorArg] : []));
				break;
			case 'ERROR':
			case 'CRITICAL':
				console.error(tag, message, ...(errorArg ? [errorArg] : []));
				break;
		}
	}

	return {
		/**
		 * Trace-level log - most verbose, for fine-grained debugging.
		 */
		trace: (...args: unknown[]): void => {
			logMessage('TRACE', ...args);
		},

		/**
		 * Debug-level log - verbose operational logs for development.
		 */
		debug: (...args: unknown[]): void => {
			logMessage('DEBUG', ...args);
		},

		/**
		 * Info-level log - significant events and state changes.
		 */
		info: (...args: unknown[]): void => {
			logMessage('INFO', ...args);
		},

		/**
		 * Success-level log - successful operations.
		 */
		success: (...args: unknown[]): void => {
			logMessage('SUCCESS', ...args);
		},

		/**
		 * Warning-level log - recoverable issues or deprecated usage.
		 */
		warn: (...args: unknown[]): void => {
			logMessage('WARNING', ...args);
		},

		/**
		 * Error-level log - errors that need attention.
		 */
		error: (...args: unknown[]): void => {
			logMessage('ERROR', ...args);
		},

		/**
		 * Critical-level log - critical failures.
		 */
		critical: (...args: unknown[]): void => {
			logMessage('CRITICAL', ...args);
		},
	};
}

/**
 * Pre-configured loggers for common modules.
 * Import these directly for convenience.
 */
export const apiLogger = createLogger({ prefix: 'API' });
export const workflowLogger = createLogger({ prefix: 'ScanWorkflow' });
export const settingsLogger = createLogger({ prefix: 'Settings' });
export const authLogger = createLogger({ prefix: 'Auth' });
export const qrLogger = createLogger({ prefix: 'QRScanner' });
export const chatLogger = createLogger({ prefix: 'Chat' });
