/**
 * API Module - HTTP client for Homebox Companion backend
 * 
 * This module provides typed API access organized by domain:
 * - auth: Authentication (login)
 * - locations: Location CRUD
 * - labels: Labels list
 * - items: Item creation and attachments
 * - vision: AI vision endpoints
 * - settings: Config, logs, field preferences
 */

// Re-export client utilities
export { ApiError, request, requestFormData } from './client';

// Re-export domain APIs
export { auth } from './auth';
export { locations } from './locations';
export { labels } from './labels';
export { items } from './items';
export { vision } from './vision';

// Re-export settings APIs
export { 
	getVersion, 
	getConfig, 
	getLogs, 
	fieldPreferences,
	type VersionResponse,
	type ConfigResponse,
	type LogsResponse,
	type FieldPreferences,
	type EffectiveDefaults,
} from './settings';

// Re-export types from vision for convenience
export type { DetectOptions, BatchDetectOptions } from './vision';

