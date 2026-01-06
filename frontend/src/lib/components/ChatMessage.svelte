<script lang="ts">
	/**
	 * ChatMessage - Displays a single chat message bubble
	 *
	 * User messages are right-aligned with primary color.
	 * Assistant messages are left-aligned with surface color.
	 * Shows approval badge inside the bubble when there are pending actions.
	 * Groups tools and executed actions with counters (x2, x3, etc.).
	 */
	import { onDestroy } from 'svelte';
	import type { ChatMessage as ChatMessageType, ToolResult } from '../stores/chat.svelte';
	import { renderMarkdown } from '../markdown';

	interface Props {
		message: ChatMessageType;
		pendingApprovalCount?: number;
		onOpenApprovals?: () => void;
	}

	let { message, pendingApprovalCount = 0, onOpenApprovals }: Props = $props();

	const isUser = $derived(message.role === 'user');
	const hasToolResults = $derived(message.toolResults && message.toolResults.length > 0);
	const hasExecutedActions = $derived(
		message.executedActions && message.executedActions.length > 0
	);
	const showApprovalBadge = $derived(!isUser && pendingApprovalCount > 0);

	// Track timeout for cleanup on component destroy
	let copyTimeoutId: ReturnType<typeof setTimeout> | null = null;

	// Total tool count for unified display (read-only + executed)
	const totalToolCount = $derived(
		(message.toolResults?.length ?? 0) + (message.executedActions?.length ?? 0)
	);

	// Group tool results by tool name with count
	interface GroupedTool {
		toolName: string;
		count: number;
		success: boolean;
		isExecuting: boolean;
	}

	const groupedToolResults = $derived.by(() => {
		if (!message.toolResults || message.toolResults.length === 0) return [];

		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- local variable in pure derivation
		const groups = new Map<string, { count: number; results: ToolResult[] }>();
		for (const result of message.toolResults) {
			const existing = groups.get(result.tool);
			if (existing) {
				existing.count++;
				existing.results.push(result);
			} else {
				groups.set(result.tool, { count: 1, results: [result] });
			}
		}

		const grouped: GroupedTool[] = [];
		for (const [toolName, { count, results }] of groups) {
			// Tool is executing if any instance is executing
			const isExecuting = results.some((r) => r.isExecuting);
			// Tool is successful if all completed instances are successful
			const completedResults = results.filter((r) => !r.isExecuting);
			const success = completedResults.length > 0 && completedResults.every((r) => r.success);
			grouped.push({ toolName, count, success, isExecuting });
		}
		return grouped;
	});

	// Group executed actions by tool name with count
	// Show entity names when available, group only when missing
	interface GroupedAction {
		toolName: string;
		entityName?: string;
		successCount: number;
		failCount: number;
		rejectCount: number;
	}

	const groupedExecutedActions = $derived.by(() => {
		if (!message.executedActions || message.executedActions.length === 0) return [];

		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- local variable in pure derivation
		const groups = new Map<
			string,
			{ entityName?: string; successCount: number; failCount: number; rejectCount: number }
		>();
		for (const action of message.executedActions) {
			// Group by tool name + entity name (or just tool name if no entity)
			// Trim to handle empty/whitespace-only entity names
			const groupKey = action.entityName?.trim()
				? `${action.toolName}::${action.entityName}`
				: action.toolName;
			const existing = groups.get(groupKey);
			if (existing) {
				if (action.rejected) existing.rejectCount++;
				else if (action.success) existing.successCount++;
				else existing.failCount++;
			} else {
				groups.set(groupKey, {
					entityName: action.entityName,
					successCount: action.rejected ? 0 : action.success ? 1 : 0,
					failCount: action.rejected ? 0 : action.success ? 0 : 1,
					rejectCount: action.rejected ? 1 : 0,
				});
			}
		}

		const grouped: GroupedAction[] = [];
		for (const [groupKey, { entityName, successCount, failCount, rejectCount }] of groups) {
			// Extract tool name from the group key
			const toolName = groupKey.includes('::') ? groupKey.split('::')[0] : groupKey;
			grouped.push({
				toolName,
				entityName,
				successCount,
				failCount,
				rejectCount,
			});
		}
		return grouped;
	});

	// Executed action stats for fallback display
	const executedActionStats = $derived.by(() => {
		if (!message.executedActions || message.executedActions.length === 0) {
			return { total: 0, success: 0, rejected: 0, allSuccess: true };
		}
		const total = message.executedActions.length;
		const success = message.executedActions.filter((a) => a.success && !a.rejected).length;
		const rejected = message.executedActions.filter((a) => a.rejected).length;
		return { total, success, rejected, allSuccess: success === total };
	});

	// Copy button state
	let copySuccess = $state(false);

	async function handleCopy() {
		if (!message.content) return;
		try {
			await navigator.clipboard.writeText(message.content);
			copySuccess = true;
			// Clear any existing timeout and set new one
			if (copyTimeoutId) clearTimeout(copyTimeoutId);
			copyTimeoutId = setTimeout(() => {
				copySuccess = false;
				copyTimeoutId = null;
			}, 2000);
		} catch (e) {
			console.error('Copy failed:', e);
		}
	}

	// Cleanup timeout on component destroy to prevent memory leaks
	onDestroy(() => {
		if (copyTimeoutId) clearTimeout(copyTimeoutId);
	});

	// Memoized markdown rendering with GFM support and sanitization
	const renderedContent = $derived.by(() => {
		if (isUser || !message.content) return '';
		try {
			return renderMarkdown(message.content);
		} catch (e) {
			console.error('Markdown render failed:', e);
			return message.content; // fallback to raw text
		}
	});

	// Badge style variants for consistent styling across tool and action badges
	type BadgeVariant = 'success' | 'error' | 'warning' | 'primary';
	const badgeStyles: Record<BadgeVariant, string> = {
		success: 'border-success-500/30 bg-success-500/15 text-success-500',
		error: 'border-error-500/30 bg-error-500/15 text-error-500',
		warning: 'border-warning-500/30 bg-warning-500/15 text-warning-500',
		primary: 'border-primary-500/30 bg-primary-500/15 text-primary-500',
	};

	/** Get badge style classes for a tool result */
	function getToolBadgeVariant(group: GroupedTool): BadgeVariant {
		if (group.isExecuting) return 'primary';
		return group.success ? 'success' : 'error';
	}
</script>

<div
	class="group flex max-w-[80%] flex-col {isUser ? 'items-end self-end' : 'items-start self-start'}"
>
	<div class="relative">
		<div
			class="chat-bubble {isUser
				? 'chat-bubble-user rounded-br bg-gradient-to-br from-primary-600 to-primary-500 text-white shadow-primary-glow-sm'
				: 'rounded-bl border border-neutral-700/50 bg-neutral-800/80 text-neutral-200 backdrop-blur-sm'} {message.isStreaming
				? 'streaming-glow'
				: ''}"
		>
			{#if message.content}
				{#if isUser}
					<p class="m-0 whitespace-pre-wrap">{message.content}</p>
				{:else}
					<!-- eslint-disable-next-line svelte/no-at-html-tags -- Rendered markdown from trusted AI response -->
					<div class="markdown-content">{@html renderedContent}</div>
				{/if}
			{:else if hasExecutedActions && !message.isStreaming}
				<!-- Fallback summary when no content but has executed actions -->
				<p class="m-0 text-neutral-300">
					{#if executedActionStats.allSuccess && executedActionStats.rejected === 0}
						<span class="font-bold text-success-500">✓</span> Completed {executedActionStats.total} action{executedActionStats.total !==
						1
							? 's'
							: ''} successfully
					{:else if executedActionStats.rejected > 0 && executedActionStats.success === 0}
						<span class="font-bold text-warning-500">⊘</span> Rejected {executedActionStats.rejected}
						action{executedActionStats.rejected !== 1 ? 's' : ''}
					{:else}
						{executedActionStats.success} completed{executedActionStats.rejected > 0
							? `, ${executedActionStats.rejected} rejected`
							: ''}
					{/if}
				</p>
			{/if}

			<!-- Approval Required Badge (inside bubble, below text) -->
			{#if showApprovalBadge}
				<button
					type="button"
					class="chat-approval-badge approval-badge border-warning-500/40 bg-warning-500/15 text-warning-500 hover:border-warning-500/60 hover:bg-warning-500/20"
					onclick={onOpenApprovals}
				>
					<div class="flex h-5 w-5 items-center justify-center rounded-md bg-warning-500/20">
						<svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
							/>
						</svg>
					</div>
					<span class="flex-1">
						{pendingApprovalCount}
						{pendingApprovalCount === 1 ? 'action requires' : 'actions require'} approval
					</span>
					<svg class="h-3.5 w-3.5 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M9 5l7 7-7 7"
						/>
					</svg>
				</button>
			{/if}

			{#if message.isStreaming}
				<div class="flex justify-center gap-1 px-2 py-1">
					<span class="typing-dot"></span>
					<span class="typing-dot animation-delay-160"></span>
					<span class="typing-dot animation-delay-320"></span>
				</div>
			{/if}

			{#if hasToolResults || hasExecutedActions}
				<details class="tool-accordion group/tools chat-tools-section">
					<summary class="chat-tools-summary">
						<span class="transform transition-transform group-open/tools:rotate-90">›</span>
						Used {totalToolCount} tool{totalToolCount > 1 ? 's' : ''}
					</summary>
					<div class="chat-tools-grid">
						<!-- Read-only tool badges -->
						{#each groupedToolResults as group (group.toolName)}
							<div class="chat-tool-badge {badgeStyles[getToolBadgeVariant(group)]}">
								{#if group.isExecuting}
									<span class="tool-spinner"></span>
								{:else}
									<span class="font-bold">{group.success ? '✓' : '✗'}</span>
								{/if}
								<span class="font-mono">{group.toolName}</span>
								{#if group.count > 1}
									<span class="opacity-70">×{group.count}</span>
								{/if}
							</div>
						{/each}
						<!-- Executed action badges -->
						{#each groupedExecutedActions as action (action.toolName + (action.entityName || ''))}
							{@const hasSuccess = action.successCount > 0}
							{@const hasFail = action.failCount > 0}
							{@const hasReject = action.rejectCount > 0}
							{@const displayText = action.entityName ? `${action.toolName}: ${action.entityName}` : action.toolName}
							<!-- Show success badge if any succeeded -->
							{#if hasSuccess}
								<div class="chat-tool-badge {badgeStyles.success}">
									<span class="font-bold">✓</span>
									<span class="font-mono">{displayText}</span>
									{#if action.successCount > 1}
										<span class="opacity-70">×{action.successCount}</span>
									{/if}
								</div>
							{/if}
							<!-- Show fail badge if any failed -->
							{#if hasFail}
								<div class="chat-tool-badge {badgeStyles.error}">
									<span class="font-bold">✗</span>
									<span class="font-mono">{displayText}</span>
									{#if action.failCount > 1}
										<span class="opacity-70">×{action.failCount}</span>
									{/if}
								</div>
							{/if}
							<!-- Show rejected badge if any rejected -->
							{#if hasReject}
								<div class="chat-tool-badge {badgeStyles.warning}">
									<span class="font-bold">⊘</span>
									<span class="font-mono">{displayText}</span>
									{#if action.rejectCount > 1}
										<span class="opacity-70">×{action.rejectCount}</span>
									{/if}
								</div>
							{/if}
						{/each}
					</div>
				</details>
			{/if}
		</div>

		<!-- Copy button (appears on hover for all messages) -->
		{#if message.content && !message.isStreaming}
			<button
				class="copy-btn absolute -top-1 rounded-md p-1.5 opacity-0 backdrop-blur-sm transition-all group-hover:opacity-100 {isUser
					? '-right-1 bg-primary-700/80 text-primary-200 hover:bg-primary-600 hover:text-white'
					: '-left-1 bg-neutral-700/80 text-neutral-400 hover:bg-neutral-600 hover:text-neutral-200'}"
				onclick={handleCopy}
				aria-label="Copy message"
			>
				{#if copySuccess}
					<svg
						class="h-3.5 w-3.5 text-success-500"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<polyline points="20 6 9 17 4 12"></polyline>
					</svg>
				{:else}
					<svg
						class="h-3.5 w-3.5"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
						<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
					</svg>
				{/if}
			</button>
		{/if}
	</div>

	<div class="chat-meta">
		<time>
			{message.timestamp.toLocaleTimeString([], {
				hour: '2-digit',
				minute: '2-digit',
			})}
		</time>
		{#if !isUser && message.tokenUsage}
			<span>{message.tokenUsage.total} tokens</span>
		{/if}
	</div>
</div>

<style>
	/* Component-specific styles only.
	 * Markdown content styles are now global in app.css
	 * for reuse across the application.
	 */

	/* Typing indicator animation */
	.typing-dot {
		@apply h-1.5 w-1.5 animate-typing-dot rounded-full bg-primary-500;
	}

	.animation-delay-160 {
		animation-delay: 0.16s;
	}

	.animation-delay-320 {
		animation-delay: 0.32s;
	}

	/* Tool execution spinner */
	.tool-spinner {
		@apply inline-block h-2.5 w-2.5 animate-spin rounded-full border-[1.5px] border-primary-500 border-t-transparent;
	}

	/* Streaming glow animation */
	.streaming-glow {
		@apply animate-stream-glow border-primary-500;
	}

	/* Tool accordion */
	.tool-accordion summary::-webkit-details-marker {
		display: none;
	}

	.tool-accordion summary {
		list-style: none;
	}

	/* Approval badge pulse animation - uses consolidated animation from tailwind.config.js */
	.approval-badge {
		@apply animate-approval-pulse;
	}
</style>
