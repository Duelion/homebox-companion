/**
 * Debug logging API client.
 *
 * Sends debug logs to the backend for persistent storage in the data folder.
 * Logs are only written when debug mode is enabled on the server.
 */

import { request } from './client';

// =============================================================================
// TYPES
// =============================================================================

export interface DebugStatus {
	enabled: boolean;
	log_file: string;
	entry_count: number;
}

export interface DebugLogEntry {
	timestamp: string;
	level: string;
	category: string;
	message: string;
	data?: Record<string, unknown>;
}

export interface DebugLogsResponse {
	entries: DebugLogEntry[];
	total_count: number;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Get debug logging status.
 */
export const getDebugStatus = () => request<DebugStatus>('/debug/status');

/**
 * Enable debug logging.
 */
export const enableDebugLogging = () =>
	request<DebugStatus>('/debug/enable', { method: 'POST' });

/**
 * Disable debug logging.
 */
export const disableDebugLogging = () =>
	request<DebugStatus>('/debug/disable', { method: 'POST' });

/**
 * Get recent debug logs.
 */
export const getDebugLogs = (count = 100) =>
	request<DebugLogsResponse>(`/debug/logs?count=${count}`);

/**
 * Clear all debug logs.
 */
export const clearDebugLogs = () =>
	request<{ cleared_count: number; message: string }>('/debug/logs', { method: 'DELETE' });

/**
 * Write a debug log entry from the frontend.
 *
 * This is a fire-and-forget operation - errors are silently ignored
 * to avoid disrupting the user experience.
 */
export const writeDebugLog = async (
	category: string,
	message: string,
	data?: Record<string, unknown>,
	level: string = 'INFO'
): Promise<void> => {
	try {
		await request('/debug/log', {
			method: 'POST',
			body: JSON.stringify({ category, message, data, level }),
		});
	} catch {
		// Silently ignore errors - debug logging should never break the app
	}
};

// =============================================================================
// CONVENIENCE LOGGER
// =============================================================================

/**
 * Frontend debug logger.
 *
 * Usage:
 *   debugLog.info('ENRICHMENT', 'Starting enrichment', { itemId: '123' });
 *   debugLog.error('ENRICHMENT', 'Enrichment failed', { error: 'timeout' });
 */
export const debugLog = {
	debug: (category: string, message: string, data?: Record<string, unknown>) =>
		writeDebugLog(category, message, data, 'DEBUG'),

	info: (category: string, message: string, data?: Record<string, unknown>) =>
		writeDebugLog(category, message, data, 'INFO'),

	warning: (category: string, message: string, data?: Record<string, unknown>) =>
		writeDebugLog(category, message, data, 'WARNING'),

	error: (category: string, message: string, data?: Record<string, unknown>) =>
		writeDebugLog(category, message, data, 'ERROR'),
};
