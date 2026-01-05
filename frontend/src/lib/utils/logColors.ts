/**
 * Log colorization utilities for displaying backend and frontend logs.
 *
 * Provides Loguru-compatible color styling for log levels and
 * HTML-safe rendering of log content.
 */

import type { LogEntry } from './logger';

/**
 * Get Tailwind CSS classes for a log level.
 * Colors match Loguru's default terminal color scheme.
 *
 * @see https://github.com/Delgan/loguru/blob/master/loguru/_defaults.py
 */
export function getLevelClass(level: string): string {
	switch (level.trim().toUpperCase()) {
		case 'TRACE':
			return 'text-cyan-400 font-semibold';
		case 'DEBUG':
			return 'text-blue-400 font-semibold';
		case 'INFO':
			return 'text-neutral-100 font-semibold';
		case 'SUCCESS':
			return 'text-success-500 font-semibold';
		case 'WARNING':
			return 'text-warning-500 font-semibold';
		case 'ERROR':
			return 'text-error-500 font-semibold';
		case 'CRITICAL':
			return 'text-error-700 font-bold';
		default:
			return 'text-neutral-100 font-semibold';
	}
}

/**
 * Escape HTML special characters to prevent XSS.
 */
export function escapeHtml(text: string): string {
	return text
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#039;');
}

/**
 * Colorize backend log output (Loguru format).
 *
 * Expected format: "YYYY-MM-DD HH:mm:ss | LEVEL    | module:function:line - message"
 *
 * @param logs - Raw log string from backend
 * @returns HTML string with colorized spans
 */
export function colorizeBackendLogs(logs: string): string {
	if (!logs) return '';

	return logs
		.split('\n')
		.map((line) => {
			// Match the log format: timestamp | level | location - message
			const match = line.match(
				/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s*\| ([^-]+)- (.*)$/
			);

			if (!match) {
				// Line doesn't match format, return escaped
				return escapeHtml(line);
			}

			const [, timestamp, level, location, message] = match;
			const levelClass = getLevelClass(level);

			// Build colorized line matching Loguru's format:
			// <green>timestamp</green> | <level>LEVEL</level> | <cyan>location</cyan> - <level>message</level>
			return (
				`<span class="text-success-500">${escapeHtml(timestamp)}</span> | ` +
				`<span class="${levelClass}">${escapeHtml(level)}</span>| ` +
				`<span class="text-cyan-400">${escapeHtml(location)}</span>- ` +
				`<span class="${levelClass}">${escapeHtml(message)}</span>`
			);
		})
		.join('\n');
}

/**
 * Colorize frontend log entries.
 *
 * @param entries - Array of LogEntry objects from frontend logger
 * @returns HTML string with colorized spans
 */
export function colorizeFrontendLogs(entries: LogEntry[]): string {
	if (!entries || entries.length === 0) return '';

	return entries
		.map((entry) => {
			// Format timestamp from ISO to match backend format
			const date = new Date(entry.timestamp);
			const timestamp = date.toISOString().replace('T', ' ').substring(0, 19);

			const levelClass = getLevelClass(entry.level);

			// Pad level to 8 characters for alignment
			const paddedLevel = entry.level.padEnd(8, ' ');

			// Build display message: include error summary (first line only) if present
			let displayMessage = entry.message;
			if (entry.error) {
				// Get first line of error (the error message, not the full stack)
				const errorFirstLine = entry.error.split('\n')[0];
				displayMessage = `${entry.message} [${errorFirstLine}]`;
			}

			// Build colorized line matching Loguru's format
			return (
				`<span class="text-success-500">${escapeHtml(timestamp)}</span> | ` +
				`<span class="${levelClass}">${escapeHtml(paddedLevel)}</span>| ` +
				`<span class="text-cyan-400">${escapeHtml(entry.module)}</span>- ` +
				`<span class="${levelClass}">${escapeHtml(displayMessage)}</span>`
			);
		})
		.join('\n');
}

