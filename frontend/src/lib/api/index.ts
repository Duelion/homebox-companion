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
export {
	ApiError,
	NetworkError,
	request,
	requestFormData,
	requestBlobUrl,
	DEFAULT_REQUEST_TIMEOUT_MS,
	type RequestOptions,
	type FormDataRequestOptions,
	type BlobUrlRequestOptions,
} from './client';

// Re-export domain APIs
export { auth } from './auth';
export { locations } from './locations';
export { labels } from './labels';
export { items, type BlobUrlResult } from './items';
export { vision } from './vision';
export { chat, type ChatEvent, type PendingApproval, type ChatHealthResponse } from './chat';

// Re-export settings APIs
export {
	getVersion,
	getConfig,
	getLogs,
	downloadLogs,
	fieldPreferences,
	setDemoMode,
	type VersionResponse,
	type ConfigResponse,
	type LogsResponse,
	type FieldPreferences,
	type EffectiveDefaults,
} from './settings';

// Re-export Ollama APIs
export {
	getOllamaStatus,
	testOllamaConnection,
	listOllamaModels,
	pullOllamaModel,
	getGPUInfo,
	getRecommendedModel,
	getOllamaConfig,
	type OllamaStatus,
	type OllamaTestRequest,
	type OllamaTestResponse,
	type GPUInfo,
	type ModelInfo,
	type ModelPullResponse,
	type OllamaConfig,
	type RecommendedModelResponse,
} from './ollama';

// Re-export Sessions APIs (crash recovery)
export {
	checkActiveSession,
	listRecoverableSessions,
	listAllSessions,
	getSession,
	createSession,
	recoverSession,
	completeSession,
	deleteSession,
	addSessionImage,
	startImageProcessing,
	completeImageProcessing,
	failImageProcessing,
	type SessionSummary,
	type SessionImage,
	type SessionDetail,
	type SessionCreateRequest,
	type SessionCreateResponse,
	type RecoveryResponse,
	type ActiveSessionCheck,
} from './sessions';

// Re-export AI Config APIs
export {
	getAIConfig,
	updateAIConfig,
	resetAIConfig,
	testProviderConnection,
	getDefaultProviderConfig,
	OLLAMA_VISION_MODELS,
	OPENAI_MODELS,
	ANTHROPIC_MODELS,
	type AIConfigResponse,
	type AIConfigInput,
	type OllamaConfigData,
	type OpenAIConfigData,
	type AnthropicConfigData,
	type LiteLLMConfigData,
	type ProviderInfo,
	type TestConnectionResponse,
} from './aiConfig';

// Re-export types from vision for convenience
export type { DetectOptions, BatchDetectOptions } from './vision';

// Re-export domain types for consumers that import from '$lib/api'
export type {
	LocationData,
	LocationTreeNode,
	LocationCreateData,
	LocationUpdateData,
	LabelData,
	DetectedItem,
	DetectionResponse,
	ItemInput,
	BatchCreateRequest,
	BatchCreateResponse,
	AdvancedItemDetails,
	CorrectionResponse,
	BatchDetectionResult,
	BatchDetectionResponse,
} from '../types';
