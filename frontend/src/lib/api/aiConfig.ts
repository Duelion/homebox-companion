/**
 * AI Provider Configuration API endpoints
 */

import { request } from './client';

// =============================================================================
// TYPES
// =============================================================================

export interface OllamaConfigData {
	enabled: boolean;
	url: string;
	model: string;
	timeout: number;
}

export interface OpenAIConfigData {
	enabled: boolean;
	api_key: string | null;
	has_api_key?: boolean;
	model: string;
	max_tokens: number;
}

export interface AnthropicConfigData {
	enabled: boolean;
	api_key: string | null;
	has_api_key?: boolean;
	model: string;
	max_tokens: number;
}

export interface LiteLLMConfigData {
	enabled: boolean;
	model: string;
}

export interface ProviderInfo {
	id: string;
	name: string;
	description: string;
	enabled: boolean;
	configured: boolean;
	requires_api_key: boolean;
}

export interface AIConfigResponse {
	active_provider: string;
	fallback_to_cloud: boolean;
	fallback_provider: string;
	ollama: OllamaConfigData;
	openai: OpenAIConfigData;
	anthropic: AnthropicConfigData;
	litellm: LiteLLMConfigData;
	providers: ProviderInfo[];
}

export interface AIConfigInput {
	active_provider: string;
	fallback_to_cloud: boolean;
	fallback_provider: string;
	ollama: OllamaConfigData;
	openai: Omit<OpenAIConfigData, 'has_api_key'>;
	anthropic: Omit<AnthropicConfigData, 'has_api_key'>;
	litellm: LiteLLMConfigData;
}

export interface TestConnectionRequest {
	provider: string;
	config: Record<string, unknown>;
}

export interface TestConnectionResponse {
	success: boolean;
	provider: string;
	message: string;
	details: Record<string, unknown>;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Get current AI configuration
 */
export const getAIConfig = () => request<AIConfigResponse>('/settings/ai-config');

/**
 * Update AI configuration
 */
export const updateAIConfig = (config: AIConfigInput) =>
	request<AIConfigResponse>('/settings/ai-config', {
		method: 'PUT',
		body: JSON.stringify(config),
	});

/**
 * Reset AI configuration to defaults
 */
export const resetAIConfig = () =>
	request<AIConfigResponse>('/settings/ai-config', {
		method: 'DELETE',
	});

/**
 * Test connection to an AI provider
 */
export const testProviderConnection = (provider: string, config: Record<string, unknown>) =>
	request<TestConnectionResponse>('/settings/ai-config/test', {
		method: 'POST',
		body: JSON.stringify({ provider, config }),
	});

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Get default config for a new provider
 */
export function getDefaultProviderConfig(provider: string): Record<string, unknown> {
	switch (provider) {
		case 'ollama':
			return {
				enabled: false,
				url: 'http://localhost:11434',
				model: 'minicpm-v',
				timeout: 120,
			};
		case 'openai':
			return {
				enabled: false,
				api_key: null,
				model: 'gpt-4o',
				max_tokens: 4096,
			};
		case 'anthropic':
			return {
				enabled: false,
				api_key: null,
				model: 'claude-sonnet-4-20250514',
				max_tokens: 4096,
			};
		case 'litellm':
			return {
				enabled: true,
				model: 'gpt-4o',
			};
		default:
			return {};
	}
}

/**
 * Available Ollama vision models
 */
export const OLLAMA_VISION_MODELS = [
	{ id: 'minicpm-v', name: 'MiniCPM-V (Recommended for 6GB+)', vram: '6GB+' },
	{ id: 'llama3.2-vision:11b', name: 'Llama 3.2 Vision 11B', vram: '8GB+' },
	{ id: 'llama3.2-vision:90b', name: 'Llama 3.2 Vision 90B', vram: '48GB+' },
	{ id: 'moondream', name: 'Moondream (Lightweight)', vram: '3GB+' },
	{ id: 'granite3.2-vision', name: 'Granite 3.2 Vision', vram: '4GB+' },
];

/**
 * Available OpenAI models
 */
export const OPENAI_MODELS = [
	{ id: 'gpt-4o', name: 'GPT-4o (Recommended)' },
	{ id: 'gpt-4o-mini', name: 'GPT-4o Mini (Faster, Cheaper)' },
	{ id: 'gpt-4-turbo', name: 'GPT-4 Turbo' },
];

/**
 * Available Anthropic models
 */
export const ANTHROPIC_MODELS = [
	{ id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4 (Recommended)' },
	{ id: 'claude-opus-4-20250514', name: 'Claude Opus 4 (Most Capable)' },
	{ id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet' },
	{ id: 'claude-3-5-haiku-20241022', name: 'Claude 3.5 Haiku (Fast)' },
];
