/**
 * Chat API client for conversational assistant
 * 
 * Provides streaming chat via Server-Sent Events (SSE) and
 * approval management for write actions.
 */

import { authStore } from '../stores/auth.svelte';
import { ApiError, NetworkError } from './client';

const BASE_URL = '/api';

// =============================================================================
// TYPES
// =============================================================================

export type ChatEventType = 'text' | 'tool_start' | 'tool_result' | 'approval_required' | 'error' | 'done';

export interface ChatTextEvent {
    type: 'text';
    data: { content: string };
}

export interface ChatToolStartEvent {
    type: 'tool_start';
    data: { tool: string; params: Record<string, unknown> };
}

export interface ChatToolResultEvent {
    type: 'tool_result';
    data: { tool: string; result: { success: boolean; data?: unknown; error?: string } };
}

export interface ChatApprovalEvent {
    type: 'approval_required';
    data: { id: string; tool: string; params: Record<string, unknown>; expires_at: string | null };
}

export interface ChatErrorEvent {
    type: 'error';
    data: { message: string };
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
    | ChatDoneEvent;

export interface PendingApproval {
    id: string;
    tool_name: string;
    parameters: Record<string, unknown>;
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
 * @param message - The user's message
 * @param options - Callbacks for events, errors, and completion
 * @returns AbortController to cancel the request
 */
export function sendMessage(message: string, options: SendMessageOptions = {}): AbortController {
    const controller = new AbortController();
    const signal = options.signal
        ? AbortSignal.any([options.signal, controller.signal])
        : controller.signal;

    // Run async operation
    (async () => {
        try {
            const response = await fetch(`${BASE_URL}/chat/messages`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authStore.token}`,
                },
                body: JSON.stringify({ message }),
                signal,
            });

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

            let receivedDone = false;
            while (true) {
                const { done, value } = await reader.read();
                if (done) {
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
                        try {
                            const data = JSON.parse(line.slice(6));
                            const event: ChatEvent = { type: currentEvent, data } as ChatEvent;
                            options.onEvent?.(event);

                            if (currentEvent === 'done') {
                                receivedDone = true;
                                options.onComplete?.();
                            }
                        } catch (e) {
                            console.warn('Failed to parse SSE data:', line);
                        }
                        currentEvent = null;
                    }
                }
            }
        } catch (error) {
            if (error instanceof Error && error.name === 'AbortError') {
                // Request was cancelled, don't report as error
                return;
            }
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
    const response = await fetch(`${BASE_URL}/chat/pending`, {
        headers: {
            'Authorization': `Bearer ${authStore.token}`,
        },
    });

    if (!response.ok) {
        if (response.status === 503) {
            throw new ApiError(503, 'Chat feature is disabled');
        }
        throw new ApiError(response.status, `Failed to get pending approvals: ${response.statusText}`);
    }

    const data = await response.json();
    return data.approvals;
}

/**
 * Approve a pending action.
 */
export async function approveAction(approvalId: string): Promise<{ success: boolean; message?: string }> {
    const response = await fetch(`${BASE_URL}/chat/approve/${approvalId}`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${authStore.token}`,
        },
    });

    if (!response.ok) {
        if (response.status === 404) {
            throw new ApiError(404, 'Approval not found or expired');
        }
        throw new ApiError(response.status, `Failed to approve action: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Reject a pending action.
 */
export async function rejectAction(approvalId: string): Promise<{ success: boolean; message?: string }> {
    const response = await fetch(`${BASE_URL}/chat/reject/${approvalId}`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${authStore.token}`,
        },
    });

    if (!response.ok) {
        if (response.status === 404) {
            throw new ApiError(404, 'Approval not found or expired');
        }
        throw new ApiError(response.status, `Failed to reject action: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Clear conversation history.
 */
export async function clearHistory(): Promise<void> {
    const response = await fetch(`${BASE_URL}/chat/history`, {
        method: 'DELETE',
        headers: {
            'Authorization': `Bearer ${authStore.token}`,
        },
    });

    if (!response.ok) {
        throw new ApiError(response.status, `Failed to clear history: ${response.statusText}`);
    }
}

/**
 * Get chat health status.
 */
export async function getChatHealth(): Promise<ChatHealthResponse> {
    const response = await fetch(`${BASE_URL}/chat/health`);

    if (!response.ok) {
        throw new ApiError(response.status, `Failed to get chat health: ${response.statusText}`);
    }

    return response.json();
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
