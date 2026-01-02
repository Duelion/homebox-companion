<script lang="ts">
	/**
	 * ChatMessage - Displays a single chat message bubble
	 *
	 * User messages are right-aligned with primary color.
	 * Assistant messages are left-aligned with surface color.
	 * Shows approval badge inside the bubble when there are pending actions.
	 * Groups tools and executed actions with counters (x2, x3, etc.).
	 */
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

	// Group tool results by tool name with count
	interface GroupedTool {
		tool: string;
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
		for (const [tool, { count, results }] of groups) {
			// Tool is executing if any instance is executing
			const isExecuting = results.some((r) => r.isExecuting);
			// Tool is successful if all completed instances are successful
			const completedResults = results.filter((r) => !r.isExecuting);
			const success = completedResults.length > 0 && completedResults.every((r) => r.success);
			grouped.push({ tool, count, success, isExecuting });
		}
		return grouped;
	});

	// Group executed actions by tool name with count
	interface GroupedAction {
		toolName: string;
		count: number;
		successCount: number;
		failCount: number;
	}

	const groupedExecutedActions = $derived.by(() => {
		if (!message.executedActions || message.executedActions.length === 0) return [];

		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- local variable in pure derivation
		const groups = new Map<string, { successCount: number; failCount: number }>();
		for (const action of message.executedActions) {
			const existing = groups.get(action.toolName);
			if (existing) {
				if (action.success) existing.successCount++;
				else existing.failCount++;
			} else {
				groups.set(action.toolName, {
					successCount: action.success ? 1 : 0,
					failCount: action.success ? 0 : 1,
				});
			}
		}

		const grouped: GroupedAction[] = [];
		for (const [toolName, { successCount, failCount }] of groups) {
			grouped.push({ toolName, count: successCount + failCount, successCount, failCount });
		}
		return grouped;
	});

	// Copy button state
	let copySuccess = $state(false);

	async function handleCopy() {
		if (!message.content) return;
		try {
			await navigator.clipboard.writeText(message.content);
			copySuccess = true;
			setTimeout(() => (copySuccess = false), 2000);
		} catch (e) {
			console.error('Copy failed:', e);
		}
	}

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
</script>

<div
	class="group flex max-w-[80%] flex-col {isUser ? 'items-end self-end' : 'items-start self-start'}"
>
	<div class="relative">
		<div
			class="rounded-2xl px-3.5 py-2.5 break-words {isUser
				? 'from-primary-600 to-primary-500 rounded-br bg-gradient-to-br text-white shadow-[0_2px_8px_rgba(99,102,241,0.3)]'
				: 'rounded-bl border border-neutral-700/50 bg-neutral-800/80 text-neutral-200 backdrop-blur-sm'} {message.isStreaming
				? 'streaming-glow'
				: ''}"
		>
			{#if message.content}
				{#if isUser}
					<p class="m-0 leading-relaxed">{message.content}</p>
				{:else}
					<!-- eslint-disable-next-line svelte/no-at-html-tags -- Rendered markdown from trusted AI response -->
					<div class="markdown-content">{@html renderedContent}</div>
				{/if}
			{/if}

			{#if message.isStreaming && !message.content}
				<div class="flex gap-1 py-1">
					<span class="typing-dot"></span>
					<span class="typing-dot animation-delay-160"></span>
					<span class="typing-dot animation-delay-320"></span>
				</div>
			{/if}

			{#if hasToolResults}
				<details class="tool-accordion group/tools mt-2 border-t border-white/10 pt-2">
					<summary
						class="flex cursor-pointer items-center gap-1.5 text-xs text-neutral-400 select-none hover:text-neutral-300"
					>
						<span class="transform transition-transform group-open/tools:rotate-90">›</span>
						Used {message.toolResults?.length ?? 0} tool{(message.toolResults?.length ?? 0) > 1
							? 's'
							: ''}
					</summary>
					<div class="mt-2 flex flex-wrap gap-1.5">
						{#each groupedToolResults as group (group.tool)}
							<div
								class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium {group.isExecuting
									? 'border-primary-500/30 bg-primary-500/15 text-primary-500 border'
									: group.success
										? 'border-success-500/30 bg-success-500/15 text-success-500 border'
										: 'border-error-500/30 bg-error-500/15 text-error-500 border'}"
							>
								{#if group.isExecuting}
									<span class="tool-spinner"></span>
								{:else}
									<span class="font-bold">{group.success ? '✓' : '✗'}</span>
								{/if}
								<span class="font-mono">{group.tool}</span>
								{#if group.count > 1}
									<span class="opacity-70">×{group.count}</span>
								{/if}
							</div>
						{/each}
					</div>
				</details>
			{/if}

			<!-- Approval Required Badge (inside bubble) -->
			{#if showApprovalBadge}
				<button
					type="button"
					class="approval-badge border-warning-500/40 bg-warning-500/15 hover:border-warning-500/60 hover:bg-warning-500/20 mt-2 flex w-full items-center gap-2 rounded-xl border px-3 py-2 text-left transition-all active:scale-[0.98]"
					onclick={onOpenApprovals}
				>
					<div class="bg-warning-500/20 flex h-6 w-6 items-center justify-center rounded-lg">
						<svg
							class="text-warning-500 h-3.5 w-3.5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
							/>
						</svg>
					</div>
					<span class="text-warning-500 flex-1 text-sm font-medium">
						{pendingApprovalCount}
						{pendingApprovalCount === 1 ? 'action requires' : 'actions require'} approval
					</span>
					<svg
						class="text-warning-500/70 h-4 w-4"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M9 5l7 7-7 7"
						/>
					</svg>
				</button>
			{/if}

			<!-- Executed Actions (inside bubble, green badges) -->
			{#if hasExecutedActions}
				<div class="mt-2 flex flex-wrap gap-1.5 border-t border-white/10 pt-2">
					{#each groupedExecutedActions as action (action.toolName)}
						<div
							class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium {action.failCount >
							0
								? 'border-error-500/30 bg-error-500/15 text-error-500 border'
								: 'border-success-500/30 bg-success-500/15 text-success-500 border'}"
						>
							<span class="font-bold">{action.failCount > 0 ? '✗' : '✓'}</span>
							<span class="font-mono">{action.toolName}</span>
							{#if action.count > 1}
								<span class="opacity-70">×{action.count}</span>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Copy button (appears on hover for assistant messages) -->
		{#if !isUser && message.content && !message.isStreaming}
			<button
				class="copy-btn absolute -top-1 -right-1 rounded-md bg-neutral-700/80 p-1.5 text-neutral-400 opacity-0 backdrop-blur-sm transition-all group-hover:opacity-100 hover:bg-neutral-600 hover:text-neutral-200"
				onclick={handleCopy}
				aria-label="Copy message"
			>
				{#if copySuccess}
					<svg
						class="text-success-500 h-3.5 w-3.5"
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

	<div class="mt-1 flex items-center gap-2 px-2">
		<time class="text-xs text-neutral-500">
			{message.timestamp.toLocaleTimeString([], {
				hour: '2-digit',
				minute: '2-digit',
			})}
		</time>
		{#if !isUser && message.tokenUsage}
			<span class="text-xs text-neutral-500">
				{message.tokenUsage.total} tokens
			</span>
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
		@apply animate-typing-dot bg-primary-500 h-2 w-2 rounded-full;
	}

	.animation-delay-160 {
		animation-delay: -0.16s;
	}

	.animation-delay-320 {
		animation-delay: -0.32s;
	}

	/* Tool execution spinner */
	.tool-spinner {
		@apply border-primary-500 inline-block h-3 w-3 animate-spin rounded-full border-2 border-t-transparent;
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

	/* Approval badge pulse animation - enhanced for visibility */
	.approval-badge {
		animation: approval-pulse 1.5s ease-in-out infinite;
	}

	@keyframes approval-pulse {
		0%,
		100% {
			box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4);
			transform: scale(1);
			border-color: rgba(245, 158, 11, 0.4);
		}
		50% {
			box-shadow: 0 0 8px 4px rgba(245, 158, 11, 0.25);
			transform: scale(1.02);
			border-color: rgba(245, 158, 11, 0.8);
		}
	}
</style>
