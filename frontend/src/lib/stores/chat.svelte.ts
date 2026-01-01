/**
 * Chat Store - Svelte 5 Class-based State
 *
 * Manages conversation state for the chat assistant including
 * messages, streaming state, and pending approvals.
 */

import { chat, type ChatEvent, type PendingApproval } from '../api/chat';
import { chatLogger as log } from '../utils/logger';

// =============================================================================
// TYPES
// =============================================================================

export type MessageRole = 'user' | 'assistant' | 'system';

export interface ToolResult {
	tool: string;
	executionId?: string; // Unique ID for matching start/result events
	success: boolean;
	data?: unknown;
	error?: string;
	isExecuting?: boolean; // Track if tool is currently executing
}

export interface ChatMessage {
	id: string;
	role: MessageRole;
	content: string;
	timestamp: Date;
	isStreaming?: boolean;
	toolResults?: ToolResult[];
	tokenUsage?: { prompt: number; completion: number; total: number };
}

// =============================================================================
// CHAT STORE CLASS
// =============================================================================

class ChatStore {
	// =========================================================================
	// STATE
	// =========================================================================

	/** All messages in the conversation */
	private _messages = $state<ChatMessage[]>([]);

	/** Whether we're currently receiving a response */
	private _isStreaming = $state(false);

	/** Pending approval requests */
	private _pendingApprovals = $state<PendingApproval[]>([]);

	/** Error message if something went wrong */
	private _error = $state<string | null>(null);

	/** Whether chat feature is enabled */
	private _isEnabled = $state(true);

	// =========================================================================
	// INTERNAL STATE
	// =========================================================================

	/** Counter for generating unique message IDs */
	private messageIdCounter = 0;

	/** Current streaming abort controller */
	private abortController: AbortController | null = null;

	/** ID of the message currently being streamed */
	private streamingMessageId: string | null = null;

	// =========================================================================
	// GETTERS
	// =========================================================================

	get messages(): ChatMessage[] {
		return this._messages;
	}

	get isStreaming(): boolean {
		return this._isStreaming;
	}

	get pendingApprovals(): PendingApproval[] {
		return this._pendingApprovals;
	}

	get error(): string | null {
		return this._error;
	}

	get isEnabled(): boolean {
		return this._isEnabled;
	}

	// =========================================================================
	// MESSAGE MANAGEMENT
	// =========================================================================

	/** Generate a unique message ID */
	private generateId(): string {
		return `msg-${++this.messageIdCounter}-${Date.now()}`;
	}

	/** Add a user message */
	private addUserMessage(content: string): ChatMessage {
		const message: ChatMessage = {
			id: this.generateId(),
			role: 'user',
			content,
			timestamp: new Date(),
		};
		this._messages = [...this._messages, message];
		return message;
	}

	/** Add an assistant message (initially empty for streaming) */
	private addAssistantMessage(): ChatMessage {
		const message: ChatMessage = {
			id: this.generateId(),
			role: 'assistant',
			content: '',
			timestamp: new Date(),
			isStreaming: true,
			toolResults: [],
		};
		this._messages = [...this._messages, message];
		this.streamingMessageId = message.id;
		return message;
	}

	/** Update a message by ID */
	private updateMessage(id: string, updates: Partial<ChatMessage>): void {
		this._messages = this._messages.map((msg) => (msg.id === id ? { ...msg, ...updates } : msg));
	}

	/** Append content to the streaming message */
	private appendContent(content: string): void {
		if (!this.streamingMessageId) return;

		this._messages = this._messages.map((msg) =>
			msg.id === this.streamingMessageId ? { ...msg, content: msg.content + content } : msg
		);
	}

	/** Mark a tool as executing (without a result yet) */
	private markToolExecuting(toolName: string, executionId?: string): void {
		if (!this.streamingMessageId) return;

		this._messages = this._messages.map((msg) =>
			msg.id === this.streamingMessageId
				? {
						...msg,
						toolResults: [
							...(msg.toolResults || []),
							{ tool: toolName, executionId, success: false, isExecuting: true },
						],
					}
				: msg
		);
	}

	/** Update an executing tool with its final result */
	private updateToolResult(
		toolName: string,
		executionId: string | undefined,
		result: Omit<ToolResult, 'tool' | 'executionId'>
	): void {
		if (!this.streamingMessageId) return;

		this._messages = this._messages.map((msg) => {
			if (msg.id !== this.streamingMessageId) return msg;

			const toolResults = msg.toolResults || [];
			// Match by executionId if available, otherwise fallback to name + isExecuting
			const toolIndex = executionId
				? toolResults.findIndex((tr) => tr.executionId === executionId)
				: toolResults.findIndex((tr) => tr.tool === toolName && tr.isExecuting);

			if (toolIndex === -1) return msg;

			const updatedResults = [...toolResults];
			updatedResults[toolIndex] = { tool: toolName, executionId, ...result, isExecuting: false };

			return { ...msg, toolResults: updatedResults };
		});
	}

	/** Add a system message */
	private addSystemMessage(content: string): void {
		this._messages = [
			...this._messages,
			{
				id: this.generateId(),
				role: 'system',
				content,
				timestamp: new Date(),
			},
		];
	}

	// =========================================================================
	// PUBLIC METHODS
	// =========================================================================

	/**
	 * Send a message and stream the response.
	 */
	sendMessage(content: string): void {
		if (this._isStreaming) {
			log.warn('Already streaming, ignoring send request');
			return;
		}

		if (!content.trim()) {
			return;
		}

		// TRACE: Log full message being sent
		log.trace(`Sending message: "${content}"`);

		// Clear any previous error
		this._error = null;

		// Add user message
		this.addUserMessage(content);

		// Add placeholder assistant message
		this.addAssistantMessage();

		// Start streaming
		this._isStreaming = true;

		this.abortController = chat.sendMessage(content, {
			onEvent: (event: ChatEvent) => this.handleEvent(event),
			onError: (error: Error) => this.handleError(error),
			onComplete: () => this.handleComplete(),
		});
	}

	/**
	 * Cancel the current streaming request.
	 */
	cancelStreaming(): void {
		if (this.abortController) {
			this.abortController.abort();
			this.abortController = null;
		}
		this.handleComplete();
	}

	/**
	 * Clear all messages and reset state.
	 */
	async clearHistory(): Promise<void> {
		try {
			await chat.clearHistory();
			this._messages = [];
			this._pendingApprovals = [];
			this._error = null;
		} catch (error) {
			this._error = error instanceof Error ? error.message : 'Failed to clear history';
		}
	}

	/**
	 * Approve a pending action and show the result.
	 */
	async approveAction(approvalId: string): Promise<void> {
		const approval = this._pendingApprovals.find((a) => a.id === approvalId);
		const toolName = approval?.tool_name || 'unknown';

		try {
			const result = await chat.approveAction(approvalId);
			this._pendingApprovals = this._pendingApprovals.filter((a) => a.id !== approvalId);

			// Add system message with result
			if (result.success) {
				this.addSystemMessage(`✅ Action "${toolName}" executed successfully.`);
			} else {
				this.addSystemMessage(
					`❌ Action "${toolName}" failed: ${(result as { error?: string }).error || 'Unknown error'}`
				);
			}
		} catch (error) {
			this._error = error instanceof Error ? error.message : 'Failed to approve action';
		}
	}

	/**
	 * Reject a pending action.
	 */
	async rejectAction(approvalId: string): Promise<void> {
		try {
			await chat.rejectAction(approvalId);
			this._pendingApprovals = this._pendingApprovals.filter((a) => a.id !== approvalId);
		} catch (error) {
			this._error = error instanceof Error ? error.message : 'Failed to reject action';
		}
	}

	/**
	 * Refresh pending approvals from the server.
	 */
	async refreshPendingApprovals(): Promise<void> {
		try {
			this._pendingApprovals = await chat.getPendingApprovals();
		} catch (error) {
			log.error(
				'Failed to refresh pending approvals',
				error instanceof Error ? error : new Error(String(error))
			);
		}
	}

	/**
	 * Check if chat is enabled on the server.
	 */
	async checkEnabled(): Promise<boolean> {
		try {
			const health = await chat.getChatHealth();
			this._isEnabled = health.chat_enabled;
			return health.chat_enabled;
		} catch {
			this._isEnabled = false;
			return false;
		}
	}

	// =========================================================================
	// EVENT HANDLERS
	// =========================================================================

	private handleEvent(event: ChatEvent): void {
		// TRACE: Log full event data
		log.trace(`Event [${event.type}]:`, JSON.stringify(event.data, null, 2));

		switch (event.type) {
			case 'text':
				log.trace(`Text chunk received: "${event.data.content}"`);
				this.appendContent(event.data.content);
				break;

			case 'tool_start':
				log.trace(`Tool starting: ${event.data.tool}`, event.data.params);
				// Mark tool as executing to show loading indicator
				this.markToolExecuting(event.data.tool, event.data.execution_id);
				break;

			case 'tool_result':
				log.trace(`Tool ${event.data.tool} result:`, event.data.result);
				// Update the executing tool with final result
				this.updateToolResult(event.data.tool, event.data.execution_id, {
					success: event.data.result.success,
					data: event.data.result.data,
					error: event.data.result.error,
				});
				break;

			case 'approval_required':
				log.trace(`Approval required for: ${event.data.tool}`, event.data.params);
				this._pendingApprovals = [
					...this._pendingApprovals,
					{
						id: event.data.id,
						tool_name: event.data.tool,
						parameters: event.data.params,
						created_at: new Date().toISOString(),
						expires_at: event.data.expires_at,
						is_expired: false,
					},
				];
				break;

			case 'error':
				log.trace(`Error event: ${event.data.message}`);
				this._error = event.data.message;
				break;

			case 'usage':
				log.trace(`Token usage: ${event.data.total_tokens} total`, event.data);
				// Update the streaming message with token usage
				if (this.streamingMessageId) {
					this.updateMessage(this.streamingMessageId, {
						tokenUsage: {
							prompt: event.data.prompt_tokens,
							completion: event.data.completion_tokens,
							total: event.data.total_tokens,
						},
					});
				}
				break;

			case 'done':
				log.trace('Done event received');
				// Handled by onComplete callback
				break;
		}
	}

	private handleError(error: Error): void {
		this._error = error.message;

		// Remove empty assistant message on early failure
		if (this.streamingMessageId) {
			const msg = this._messages.find((m) => m.id === this.streamingMessageId);
			if (msg && !msg.content && (!msg.toolResults || msg.toolResults.length === 0)) {
				this._messages = this._messages.filter((m) => m.id !== this.streamingMessageId);
			}
		}

		this.handleComplete();
	}

	private handleComplete(): void {
		this._isStreaming = false;
		this.abortController = null;

		// Mark streaming message as complete
		if (this.streamingMessageId) {
			this.updateMessage(this.streamingMessageId, { isStreaming: false });
			this.streamingMessageId = null;
		}
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const chatStore = new ChatStore();
