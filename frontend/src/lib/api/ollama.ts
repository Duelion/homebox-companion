/**
 * Ollama API endpoints for local AI management
 */

import { request } from './client';

// =============================================================================
// TYPES
// =============================================================================

export interface OllamaStatus {
	mode: string;
	connected: boolean;
	url: string;
	current_model: string;
	model_ready: boolean;
	available_models: string[];
	gpu: GPUInfo | null;
	internal_running: boolean;
	error: string | null;
}

export interface OllamaTestRequest {
	url?: string;
	model?: string;
}

export interface OllamaTestResponse {
	status: string;
	connected: boolean;
	url: string;
	model: string | null;
	model_available: boolean;
	available_models: string[];
	message: string | null;
}

export interface GPUInfo {
	detected: boolean;
	vendor: string;
	name: string;
	vram_mb: number;
	vram_gb: number;
	driver_version: string;
	cuda_version: string;
	compute_capability: string;
	recommended_model: string;
	supports_vision_models: boolean;
	detection_method: string;
}

export interface ModelInfo {
	name: string;
	size: number;
	digest: string;
	modified_at: string;
	details?: {
		family: string;
		parameter_size: string;
		quantization_level: string;
	};
}

export interface ModelPullResponse {
	status: string;
	model: string;
	error: string | null;
}

export interface OllamaConfig {
	use_ollama: boolean;
	ollama_internal: boolean;
	ollama_url: string;
	ollama_model: string;
	fallback_to_cloud: boolean;
}

export interface RecommendedModelResponse {
	recommended_model: string;
	gpu_detected: boolean;
	gpu_name: string;
	vram_gb: number;
	supports_vision: boolean;
	all_recommendations: Record<string, string>;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Get current Ollama status including connection, model, and GPU info
 */
export const getOllamaStatus = () => request<OllamaStatus>('/ollama/status');

/**
 * Test connection to an Ollama server
 */
export const testOllamaConnection = (params?: OllamaTestRequest) =>
	request<OllamaTestResponse>('/ollama/test', {
		method: 'POST',
		body: JSON.stringify(params ?? {}),
	});

/**
 * List all available Ollama models
 */
export const listOllamaModels = () => request<ModelInfo[]>('/ollama/models');

/**
 * Pull a model from Ollama registry
 */
export const pullOllamaModel = (model: string) =>
	request<ModelPullResponse>('/ollama/pull', {
		method: 'POST',
		body: JSON.stringify({ model }),
	});

/**
 * Get GPU information
 */
export const getGPUInfo = () => request<GPUInfo>('/ollama/gpu');

/**
 * Get recommended model based on GPU
 */
export const getRecommendedModel = () =>
	request<RecommendedModelResponse>('/ollama/recommended-model');

/**
 * Get current Ollama configuration
 */
export const getOllamaConfig = () => request<OllamaConfig>('/ollama/config');
