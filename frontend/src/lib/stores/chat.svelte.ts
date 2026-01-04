/**
 * Chat Store - Svelte 5 Class-based State
 *
 * Manages conversation state for the chat assistant including
 * messages, streaming state, and pending approvals.
 */

import { chat, type ChatEvent, type PendingApproval } from '../api/chat';
import { locationNavigator } from '../services/locationNavigator.svelte';
import { chatLogger as log } from '../utils/logger';
import { labelStore } from './labels.svelte';

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

export interface ExecutedAction {
	toolName: string;
	success: boolean;
	error?: string;
	rejected?: boolean; // True if user rejected this action
}

/**
 * Tracks the outcome of an approval action for AI context.
 */
export interface ApprovalOutcome {
	tool_name: string;
	outcome: 'approved' | 'rejected';
	success?: boolean; // For approved actions, whether execution succeeded
	item_name?: string; // Display name of the item affected
}

export interface ChatMessage {
	id: string;
	role: MessageRole;
	content: string;
	timestamp: Date;
	isStreaming?: boolean;
	toolResults?: ToolResult[];
	executedActions?: ExecutedAction[];
	tokenUsage?: { prompt: number; completion: number; total: number };
}

// =============================================================================
// CONSTANTS
// =============================================================================

/** Tools that modify labels - used for cache invalidation */
const LABEL_TOOLS = new Set(['create_label', 'update_label', 'delete_label']);

/** Tools that modify locations - used for cache invalidation */
const LOCATION_TOOLS = new Set(['create_location', 'update_location', 'delete_location']);

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

	/** Recent approval outcomes to send as context with the next message */
	private _recentApprovalOutcomes = $state<ApprovalOutcome[]>([]);

	// =========================================================================
	// INTERNAL STATE
	// =========================================================================

	/** Counter for generating unique message IDs */
	private messageIdCounter = 0;

	/** Current streaming abort controller */
	private abortController: AbortController | null = null;

	/** ID of the message currently being streamed */
	private streamingMessageId: string | null = null;

	/** Maps executionId -> messageId for in-flight tool executions */
	private pendingTools = new Map<string, string>();

	/** Timeout handles for stuck tool cleanup, keyed by executionId */
	private toolTimeouts = new Map<string, ReturnType<typeof setTimeout>>();

	/** Timeout duration for stuck tools (90 seconds) */
	private static readonly TOOL_TIMEOUT_MS = 90_000;

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

	/** Find the index of the last assistant message, or -1 if none exists */
	private findLastAssistantIndex(): number {
		return this._messages.findLastIndex((m) => m.role === 'assistant');
	}

	/** Find the ID of the last assistant message */
	private findLastAssistantMessageId(): string | null {
		const index = this.findLastAssistantIndex();
		return index === -1 ? null : this._messages[index].id;
	}

	/** Mark a tool as executing (without a result yet) */
	private markToolExecuting(toolName: string, executionId?: string): void {
		// Determine the target message
		const messageId = this.streamingMessageId ?? this.findLastAssistantMessageId();

		if (!messageId) {
			log.warn(
				`markToolExecuting: No assistant message found for tool '${toolName}' with executionId '${executionId}'`
			);
			return;
		}

		if (!executionId) {
			log.warn(
				`markToolExecuting: No executionId provided for tool '${toolName}' - tool result matching may fail`
			);
		}

		// Track the mapping for reliable result correlation
		if (executionId) {
			this.pendingTools.set(executionId, messageId);

			// Set timeout for cleanup of stuck tools
			const timeoutId = setTimeout(() => {
				if (this.pendingTools.has(executionId)) {
					this.handleToolTimeout(executionId, toolName);
				}
			}, ChatStore.TOOL_TIMEOUT_MS);
			this.toolTimeouts.set(executionId, timeoutId);
		}

		// Add tool entry to the message
		this._messages = this._messages.map((msg) =>
			msg.id === messageId
				? {
						...msg,
						toolResults: [
							...(msg.toolResults || []),
							{ tool: toolName, executionId, success: false, isExecuting: true },
						],
					}
				: msg
		);

		log.trace(
			`markToolExecuting: Added tool '${toolName}' (executionId: ${executionId}) to message ${messageId}`
		);
	}

	/** Update an executing tool with its final result */
	private updateToolResult(
		toolName: string,
		executionId: string | undefined,
		result: Omit<ToolResult, 'tool' | 'executionId'>
	): void {
		// Clear timeout for this tool if it exists
		if (executionId) {
			const timeoutId = this.toolTimeouts.get(executionId);
			if (timeoutId) {
				clearTimeout(timeoutId);
				this.toolTimeouts.delete(executionId);
			}
		}

		// Use the pendingTools map for direct lookup (primary method)
		let messageId: string | null = null;
		if (executionId) {
			messageId = this.pendingTools.get(executionId) ?? null;
			if (messageId) {
				this.pendingTools.delete(executionId);
			}
		}

		// Fallback: search messages if not found in map (handles edge cases)
		if (!messageId) {
			log.trace(
				`updateToolResult: executionId '${executionId}' not in pendingTools map, searching messages`
			);
			for (let i = this._messages.length - 1; i >= 0; i--) {
				const msg = this._messages[i];
				if (msg.role !== 'assistant') continue;

				const hasMatch = msg.toolResults?.some((tr) =>
					executionId ? tr.executionId === executionId : tr.tool === toolName && tr.isExecuting
				);
				if (hasMatch) {
					messageId = msg.id;
					break;
				}
			}
		}

		if (!messageId) {
			log.warn(
				`updateToolResult: Could not find message for tool '${toolName}' with executionId '${executionId}'`
			);
			return;
		}

		// Update the tool entry in the message
		this._messages = this._messages.map((msg) => {
			if (msg.id !== messageId) return msg;

			const toolResults = msg.toolResults || [];
			// Match by executionId if available, otherwise fallback to name + isExecuting
			const toolIndex = executionId
				? toolResults.findIndex((tr) => tr.executionId === executionId)
				: toolResults.findIndex((tr) => tr.tool === toolName && tr.isExecuting);

			if (toolIndex === -1) {
				log.warn(
					`updateToolResult: Found message ${messageId} but no matching tool entry for '${toolName}' with executionId '${executionId}'`
				);
				return msg;
			}

			const updatedResults = [...toolResults];
			updatedResults[toolIndex] = { tool: toolName, executionId, ...result, isExecuting: false };

			log.trace(
				`updateToolResult: Updated tool '${toolName}' (executionId: ${executionId}) in message ${messageId} to success=${result.success}`
			);
			return { ...msg, toolResults: updatedResults };
		});
	}

	/** Handle a tool that has timed out without receiving a result */
	private handleToolTimeout(executionId: string, toolName: string): void {
		log.warn(`Tool '${toolName}' timed out (executionId: ${executionId})`);

		// Clean up the timeout handle
		this.toolTimeouts.delete(executionId);

		// Update the tool result to show failure
		this.updateToolResult(toolName, executionId, {
			success: false,
			error: 'Tool execution timed out',
		});
	}

	/**
	 * Auto-reject all pending approvals on the last assistant message.
	 * Called when user sends a new message, which supersedes pending approvals.
	 * This mirrors the backend behavior (auto_reject_all_pending).
	 */
	private autoRejectPendingApprovals(): void {
		if (this._pendingApprovals.length === 0) return;

		log.trace(`Auto-rejecting ${this._pendingApprovals.length} pending approvals`);

		// Find the last assistant message (where approvals were shown)
		const lastAssistantIndex = this.findLastAssistantIndex();
		if (lastAssistantIndex === -1) {
			// No assistant message to attach rejections to, just clear
			this._pendingApprovals = [];
			return;
		}

		// Build rejected actions from pending approvals
		const rejectedActions: ExecutedAction[] = this._pendingApprovals.map((approval) => ({
			toolName: approval.tool_name,
			success: false,
			rejected: true,
		}));

		// Add rejected actions to the last assistant message
		this._messages = this._messages.map((msg, idx) => {
			if (idx !== lastAssistantIndex) return msg;
			return {
				...msg,
				executedActions: [...(msg.executedActions || []), ...rejectedActions],
			};
		});

		// Clear pending approvals
		this._pendingApprovals = [];
	}

	// =========================================================================
	// PUBLIC METHODS
	// =========================================================================

	/**
	 * Consume and clear the recent approval outcomes.
	 * Used to send context with the next message.
	 */
	private consumeApprovalOutcomes(): ApprovalOutcome[] {
		const outcomes = this._recentApprovalOutcomes;
		this._recentApprovalOutcomes = [];
		return outcomes;
	}

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

		// Auto-reject pending approvals on the original assistant message
		// (mirrors backend behavior which auto-rejects when new message arrives)
		if (this._pendingApprovals.length > 0) {
			this.autoRejectPendingApprovals();
		}

		// Consume any pending approval outcomes to send as context
		const approvalContext = this.consumeApprovalOutcomes();
		if (approvalContext.length > 0) {
			log.trace(`Including ${approvalContext.length} approval outcomes as context`);
		}

		// Add user message
		this.addUserMessage(content);

		// Add placeholder assistant message
		this.addAssistantMessage();

		// Start streaming
		this._isStreaming = true;

		this.abortController = chat.sendMessage(content, {
			approvalContext: approvalContext.length > 0 ? approvalContext : undefined,
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

		this.cleanupPendingTools('Cancelled');
		this.handleComplete();
	}

	/**
	 * Clean up all pending tools by marking them as failed with the given error.
	 * Safely snapshots the Map before iterating to avoid modification during iteration.
	 */
	private cleanupPendingTools(errorMessage: string): void {
		if (this.pendingTools.size === 0) return;

		// Snapshot entries to avoid modifying Map during iteration
		const entries = [...this.pendingTools.entries()];

		for (const [executionId, messageId] of entries) {
			// Clear timeout
			const timeoutId = this.toolTimeouts.get(executionId);
			if (timeoutId) {
				clearTimeout(timeoutId);
				this.toolTimeouts.delete(executionId);
			}

			// Find the tool name from the message
			const msg = this._messages.find((m) => m.id === messageId);
			const toolEntry = msg?.toolResults?.find((tr) => tr.executionId === executionId);
			if (toolEntry?.tool) {
				this.updateToolResult(toolEntry.tool, executionId, {
					success: false,
					error: errorMessage,
				});
			} else {
				// Tool entry not found, just remove from pending
				this.pendingTools.delete(executionId);
			}
		}
	}

	/**
	 * Clear all messages and reset state.
	 */
	async clearHistory(): Promise<void> {
		try {
			await chat.clearHistory();

			// Clear all pending tool timeouts to prevent memory leaks
			for (const timeoutId of this.toolTimeouts.values()) {
				clearTimeout(timeoutId);
			}
			this.toolTimeouts.clear();
			this.pendingTools.clear();

			this._messages = [];
			this._pendingApprovals = [];
			this._recentApprovalOutcomes = [];
			this._error = null;
		} catch (error) {
			this._error = error instanceof Error ? error.message : 'Failed to clear history';
		}
	}

	/**
	 * Clear the current error state.
	 * Called after displaying an error as a toast notification.
	 */
	clearError(): void {
		this._error = null;
	}

	/**
	 * Clear all pending approvals when they expire.
	 * Called when the approval countdown reaches zero.
	 * Marks them as rejected on the last assistant message for visual consistency.
	 */
	clearExpiredApprovals(): void {
		if (this._pendingApprovals.length === 0) return;

		// Find the last assistant message to attach rejection indicators
		const lastAssistantIndex = this.findLastAssistantIndex();
		if (lastAssistantIndex !== -1) {
			// Mark expired approvals as rejected actions on the message
			const expiredActions: ExecutedAction[] = this._pendingApprovals.map((approval) => ({
				toolName: approval.tool_name,
				success: false,
				rejected: true,
			}));

			this._messages = this._messages.map((msg, idx) => {
				if (idx !== lastAssistantIndex) return msg;
				return {
					...msg,
					executedActions: [...(msg.executedActions || []), ...expiredActions],
				};
			});
		}

		this._pendingApprovals = [];
	}

	/**
	 * Approve a pending action and track it as an executed action on the last assistant message.
	 *
	 * @param approvalId - ID of the approval to approve
	 * @param modifiedParams - Optional parameters to override the original action parameters
	 */
	async approveAction(approvalId: string, modifiedParams?: Record<string, unknown>): Promise<void> {
		const approval = this._pendingApprovals.find((a) => a.id === approvalId);

		// Guard: approval may have been already processed or expired
		if (!approval) {
			log.warn(`approveAction: Approval ${approvalId} not found - may have already been processed`);
			return;
		}

		const toolName = approval.tool_name;
		const itemName = approval.display_info?.item_name;

		try {
			const result = await chat.approveAction(approvalId, modifiedParams);
			this._pendingApprovals = this._pendingApprovals.filter((a) => a.id !== approvalId);

			// Record outcome for AI context in next message
			this._recentApprovalOutcomes = [
				...this._recentApprovalOutcomes,
				{
					tool_name: toolName,
					outcome: 'approved',
					success: result.success,
					item_name: itemName,
				},
			];

			// Add executed action to the last assistant message
			const executedAction: ExecutedAction = {
				toolName,
				success: result.success,
				error: result.success ? undefined : result.error,
			};

			// Find last assistant message to attach the executed action
			const lastAssistantIndex = this.findLastAssistantIndex();
			if (lastAssistantIndex === -1) {
				log.warn('approveAction: No assistant message to attach executed action to');
				return;
			}

			// Single pass: add executed action AND append confirmation text if provided
			const updatedMessages = this._messages.map((msg, idx) => {
				if (idx !== lastAssistantIndex) return msg;

				// Build updates for the last assistant message
				const updates: Partial<ChatMessage> = {
					executedActions: [...(msg.executedActions || []), executedAction],
				};

				// Append confirmation text to existing content
				if (result.confirmation) {
					const separator = msg.content ? '\n\n' : '';
					updates.content = msg.content + separator + result.confirmation;
				}

				return { ...msg, ...updates };
			});

			// Single reactive update
			this._messages = updatedMessages;

			// Refresh caches if needed based on the tool that was executed
			if (result.success) {
				await this.refreshCachesForTool(toolName);
			}
		} catch (error) {
			this._error = error instanceof Error ? error.message : 'Failed to approve action';
			throw error; // Re-throw to allow caller to handle (e.g., bulk operations)
		}
	}

	/**
	 * Refresh frontend caches based on the tool that was executed.
	 * This ensures the UI reflects changes made by approved tool actions.
	 */
	private async refreshCachesForTool(toolName: string): Promise<void> {
		try {
			// Refresh labels cache when labels are created/updated/deleted
			if (LABEL_TOOLS.has(toolName)) {
				log.debug(`Refreshing labels cache after ${toolName}`);
				await labelStore.fetchLabels(true); // force refresh
			}

			// Refresh locations cache when locations are created/updated/deleted
			if (LOCATION_TOOLS.has(toolName)) {
				log.debug(`Refreshing locations cache after ${toolName}`);
				await locationNavigator.loadTree(); // reloads tree and flat list
			}
		} catch (error) {
			// Don't fail the approval if cache refresh fails - just log it
			log.warn(`Failed to refresh caches after ${toolName}:`, error);
		}
	}

	/**
	 * Reject a pending action and track it as rejected on the last assistant message.
	 */
	async rejectAction(approvalId: string): Promise<void> {
		const approval = this._pendingApprovals.find((a) => a.id === approvalId);

		// Guard: approval may have been already processed or expired
		if (!approval) {
			log.warn(`rejectAction: Approval ${approvalId} not found - may have already been processed`);
			return;
		}

		const toolName = approval.tool_name;
		const itemName = approval.display_info?.item_name;

		try {
			await chat.rejectAction(approvalId);
			this._pendingApprovals = this._pendingApprovals.filter((a) => a.id !== approvalId);

			// Record outcome for AI context in next message
			this._recentApprovalOutcomes = [
				...this._recentApprovalOutcomes,
				{
					tool_name: toolName,
					outcome: 'rejected',
					item_name: itemName,
				},
			];

			// Track rejection on the last assistant message
			const rejectedAction: ExecutedAction = {
				toolName,
				success: false,
				rejected: true,
			};

			const lastAssistantIndex = this.findLastAssistantIndex();
			if (lastAssistantIndex === -1) {
				log.warn('rejectAction: No assistant message to attach rejected action to');
				return;
			}

			this._messages = this._messages.map((msg, idx) => {
				if (idx !== lastAssistantIndex) return msg;
				return {
					...msg,
					executedActions: [...(msg.executedActions || []), rejectedAction],
				};
			});
		} catch (error) {
			this._error = error instanceof Error ? error.message : 'Failed to reject action';
			throw error; // Re-throw to allow caller to handle (e.g., bulk operations)
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
		// TRACE: Log full event data (skip text events - they're logged on completion)
		if (event.type !== 'text') {
			log.trace(`Event [${event.type}]:`, JSON.stringify(event.data, null, 2));
		}

		switch (event.type) {
			case 'text':
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
						display_info: event.data.display_info,
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

		// Clean up any in-flight tools
		this.cleanupPendingTools('Connection error');

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

		// Clean up any tools that started but never received results
		// This can happen if the stream ends unexpectedly or a tool_result event is dropped
		if (this.pendingTools.size > 0) {
			log.warn(
				`Stream completed with ${this.pendingTools.size} pending tool(s) - marking as incomplete`
			);
			this.cleanupPendingTools('Stream ended without result');
		}

		// Mark streaming message as complete and log the final message
		if (this.streamingMessageId) {
			const completedMessage = this._messages.find((m) => m.id === this.streamingMessageId);
			if (completedMessage) {
				log.trace(`Assistant response completed:`, completedMessage.content);
			}
			this.updateMessage(this.streamingMessageId, { isStreaming: false });
			this.streamingMessageId = null;
		}
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const chatStore = new ChatStore();
