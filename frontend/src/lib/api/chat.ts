/**
 * Chat API client for conversational assistant
 *
 * Provides streaming chat via Server-Sent Events (SSE) and
 * approval management for write actions.
 */

import { authStore } from '../stores/auth.svelte';
import { abortSignalAny } from '../utils/abortSignal';
import { ApiError, request } from './client';
import { chatLogger as log } from '../utils/logger';

const BASE_URL = '/api';

// =============================================================================
// TYPES
// =============================================================================

export type ChatEventType =
	| 'text'
	| 'tool_start'
	| 'tool_result'
	| 'approval_required'
	| 'error'
	| 'usage'
	| 'done';

export interface ChatTextEvent {
	type: 'text';
	data: { content: string };
}

export interface ChatToolStartEvent {
	type: 'tool_start';
	data: { tool: string; execution_id?: string; params: Record<string, unknown> };
}

export interface ChatToolResultEvent {
	type: 'tool_result';
	data: {
		tool: string;
		execution_id?: string;
		result: { success: boolean; data?: unknown; error?: string };
	};
}

export interface ApprovalDisplayInfo {
	target_name?: string; // Unified target name for all action types (item, location, label)
	item_name?: string; // Kept for backward compatibility with item operations
	asset_id?: string;
	location?: string;
	action_type?: 'delete' | 'create' | 'update';
}

export interface ChatApprovalEvent {
	type: 'approval_required';
	data: {
		id: string;
		tool: string;
		params: Record<string, unknown>;
		display_info?: ApprovalDisplayInfo;
		expires_at: string | null;
	};
}

export interface ChatErrorEvent {
	type: 'error';
	data: { message: string };
}

export interface ChatUsageEvent {
	type: 'usage';
	data: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
}

export interface ChatDoneEvent {
	type: 'done';
	data: Record<string, never>;
}

export type ChatEvent =
	| ChatTextEvent
	| ChatToolStartEvent
	| ChatToolResultEvent
	| ChatApprovalEvent
	| ChatErrorEvent
	| ChatUsageEvent
	| ChatDoneEvent;

export interface PendingApproval {
	id: string;
	tool_name: string;
	parameters: Record<string, unknown>;
	display_info?: ApprovalDisplayInfo;
	created_at: string;
	expires_at: string | null;
	is_expired: boolean;
}

export interface ChatHealthResponse {
	status: string;
	chat_enabled: boolean;
	max_history: number;
	approval_timeout_seconds: number;
}

// =============================================================================
// SSE STREAMING
// =============================================================================

export interface SendMessageOptions {
	onEvent?: (event: ChatEvent) => void;
	onError?: (error: Error) => void;
	onComplete?: () => void;
	signal?: AbortSignal;
}

/**
 * Send a chat message and receive streaming SSE events.
 *
 * Uses fetch with ReadableStream for SSE parsing instead of EventSource
 * because EventSource doesn't support POST or custom headers.
 *
 * Handles 401 responses and auth-related SSE errors by triggering the
 * session expired modal.
 *
 * @param message - The user's message
 * @param options - Callbacks for events, errors, and completion
 * @returns AbortController to cancel the request
 */
export function sendMessage(message: string, options: SendMessageOptions = {}): AbortController {
	const controller = new AbortController();
	// Use abortSignalAny for browser compatibility (AbortSignal.any not in older Safari/Chrome)
	const signal = options.signal
		? abortSignalAny([options.signal, controller.signal])
		: controller.signal;

	// Run async operation
	(async () => {
		// TRACE: Log request start with timing
		const startTime = performance.now();
		log.trace(
			`Starting chat request for message: "${message.substring(0, 100)}${message.length > 100 ? '...' : ''}"`
		);

		try {
			const headers: Record<string, string> = {
				'Content-Type': 'application/json',
			};
			if (authStore.token) {
				headers['Authorization'] = `Bearer ${authStore.token}`;
			}

			const response = await fetch(`${BASE_URL}/chat/messages`, {
				method: 'POST',
				headers,
				body: JSON.stringify({ message }),
				signal,
			});

			// TRACE: Log response received
			log.trace(`SSE stream started after ${(performance.now() - startTime).toFixed(0)}ms`);

			// Handle 401 - trigger session expired modal
			if (response.status === 401) {
				log.warn('Chat request received 401 - marking session as expired');
				authStore.markSessionExpired();
				throw new ApiError(401, 'Session expired. Please re-authenticate.');
			}

			if (!response.ok) {
				throw new ApiError(response.status, `Chat request failed: ${response.statusText}`);
			}

			if (!response.body) {
				throw new Error('No response body');
			}

			// Parse SSE stream
			const reader = response.body.getReader();
			const decoder = new TextDecoder();
			let buffer = '';

			log.debug('Starting SSE stream parsing');
			let receivedDone = false;
			while (true) {
				const { done, value } = await reader.read();
				if (done) {
					log.debug('SSE stream ended', { receivedDone });
					// Ensure onComplete is called even if no explicit 'done' event was received
					if (!receivedDone) {
						options.onComplete?.();
					}
					break;
				}

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() || ''; // Keep incomplete line in buffer

				let currentEvent: ChatEventType | null = null;
				for (const line of lines) {
					if (line.startsWith('event: ')) {
						currentEvent = line.slice(7).trim() as ChatEventType;
					} else if (line.startsWith('data: ') && currentEvent) {
						const rawData = line.slice(6);

						try {
							const data = JSON.parse(rawData);
							const event: ChatEvent = { type: currentEvent, data } as ChatEvent;

							// Only log non-text events to avoid per-chunk spam
							if (currentEvent !== 'text') {
								log.debug('SSE event:', {
									type: currentEvent,
									dataPreview: typeof data === 'object' ? Object.keys(data) : data,
								});
							}

							// Check for auth-related error events from the backend
							if (currentEvent === 'error' && data.message) {
								const errorMsg = String(data.message).toLowerCase();
								if (
									errorMsg.includes('authorization') ||
									errorMsg.includes('authenticate') ||
									errorMsg.includes('token') ||
									errorMsg.includes('unauthorized') ||
									errorMsg.includes('401')
								) {
									log.warn('Chat SSE received auth error - marking session as expired');
									authStore.markSessionExpired();
								}
							}

							options.onEvent?.(event);

							if (currentEvent === 'done') {
								receivedDone = true;
								const totalTime = (performance.now() - startTime).toFixed(0);
								log.debug('SSE done event received');
								log.trace(`Total chat request completed in ${totalTime}ms`);
								options.onComplete?.();
							}
						} catch {
							log.warn('Failed to parse SSE data - raw data:', rawData);
						}
						currentEvent = null;
					}
				}
			}
		} catch (error) {
			if (error instanceof Error && error.name === 'AbortError') {
				log.debug('SSE request was cancelled');
				// Request was cancelled, don't report as error
				return;
			}
			log.error('SSE stream error:', error instanceof Error ? error : new Error(String(error)));
			options.onError?.(error instanceof Error ? error : new Error(String(error)));
		}
	})();

	return controller;
}

// =============================================================================
// APPROVAL MANAGEMENT
// =============================================================================

/**
 * Get all pending approval requests.
 */
export async function getPendingApprovals(): Promise<PendingApproval[]> {
	log.debug('Fetching pending approvals');
	const data = await request<{ approvals: PendingApproval[] }>('/chat/pending');
	log.debug(`Received ${data.approvals.length} pending approvals`);
	return data.approvals;
}

/**
 * Approve a pending action, optionally with modified parameters.
 *
 * @param approvalId - ID of the approval to approve
 * @param modifiedParams - Optional parameters to override the original action parameters
 */
export async function approveAction(
	approvalId: string,
	modifiedParams?: Record<string, unknown>
): Promise<{ success: boolean; confirmation?: string; error?: string }> {
	log.info(`Approving action: ${approvalId}`, modifiedParams ? { modifiedParams } : undefined);
	return request<{ success: boolean; confirmation?: string; error?: string }>(
		`/chat/approve/${approvalId}`,
		{
			method: 'POST',
			body: modifiedParams ? JSON.stringify({ parameters: modifiedParams }) : undefined,
		}
	);
}

/**
 * Reject a pending action.
 */
export async function rejectAction(
	approvalId: string
): Promise<{ success: boolean; message?: string }> {
	log.info(`Rejecting action: ${approvalId}`);
	return request<{ success: boolean; message?: string }>(`/chat/reject/${approvalId}`, {
		method: 'POST',
	});
}

/**
 * Clear conversation history.
 */
export async function clearHistory(): Promise<void> {
	log.info('Clearing chat history');
	await request<void>('/chat/history', {
		method: 'DELETE',
	});
	log.success('Chat history cleared');
}

/**
 * Get chat health status.
 */
export async function getChatHealth(): Promise<ChatHealthResponse> {
	log.debug('Checking chat health');
	return request<ChatHealthResponse>('/chat/health');
}

// =============================================================================
// NAMESPACE EXPORT
// =============================================================================

export const chat = {
	sendMessage,
	getPendingApprovals,
	approveAction,
	rejectAction,
	clearHistory,
	getChatHealth,
};
