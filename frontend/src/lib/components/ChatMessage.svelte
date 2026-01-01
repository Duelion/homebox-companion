<script lang="ts">
	/**
	 * ChatMessage - Displays a single chat message bubble
	 *
	 * User messages are right-aligned with primary color.
	 * Assistant messages are left-aligned with surface color.
	 * Shows approval badge button when there are pending actions.
	 */
	import type { ChatMessage as ChatMessageType } from '../stores/chat.svelte';
	import { renderMarkdown } from '../markdown';

	interface Props {
		message: ChatMessageType;
		pendingApprovalCount?: number;
		onOpenApprovals?: () => void;
	}

	let { message, pendingApprovalCount = 0, onOpenApprovals }: Props = $props();

	const isUser = $derived(message.role === 'user');
	const hasToolResults = $derived(message.toolResults && message.toolResults.length > 0);
	const showApprovalBadge = $derived(!isUser && pendingApprovalCount > 0);

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
			class="break-words rounded-2xl px-3.5 py-2.5 {isUser
				? 'rounded-br bg-gradient-to-br from-primary-600 to-primary-500 text-white shadow-[0_2px_8px_rgba(99,102,241,0.3)]'
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
						class="flex cursor-pointer select-none items-center gap-1.5 text-xs text-neutral-400 hover:text-neutral-300"
					>
						<span class="transform transition-transform group-open/tools:rotate-90">›</span>
						Used {message.toolResults?.length ?? 0} tool{(message.toolResults?.length ?? 0) > 1
							? 's'
							: ''}
					</summary>
					<div class="mt-2 flex flex-wrap gap-1.5">
						{#each message.toolResults as result, i (result.executionId ?? i)}
							<div
								class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium {result.isExecuting
									? 'border border-primary-500/30 bg-primary-500/15 text-primary-500'
									: result.success
										? 'border border-success-500/30 bg-success-500/15 text-success-500'
										: 'border border-error-500/30 bg-error-500/15 text-error-500'}"
							>
								{#if result.isExecuting}
									<span class="tool-spinner"></span>
								{:else}
									<span class="font-bold">{result.success ? '✓' : '✗'}</span>
								{/if}
								<span class="font-mono">{result.tool}</span>
							</div>
						{/each}
					</div>
				</details>
			{/if}
		</div>

		<!-- Approval Required Badge -->
		{#if showApprovalBadge}
			<button
				type="button"
				class="approval-badge mt-2 flex w-full items-center gap-2 rounded-xl border border-warning-500/40 bg-warning-500/15 px-3 py-2 text-left transition-all hover:border-warning-500/60 hover:bg-warning-500/20 active:scale-[0.98]"
				onclick={onOpenApprovals}
			>
				<div class="flex h-6 w-6 items-center justify-center rounded-lg bg-warning-500/20">
					<svg class="h-3.5 w-3.5 text-warning-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
						/>
					</svg>
				</div>
				<span class="flex-1 text-sm font-medium text-warning-500">
					{pendingApprovalCount} {pendingApprovalCount === 1 ? 'action requires' : 'actions require'} approval
				</span>
				<svg class="h-4 w-4 text-warning-500/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
				</svg>
			</button>
		{/if}

		<!-- Copy button (appears on hover for assistant messages) -->
		{#if !isUser && message.content && !message.isStreaming}
			<button
				class="copy-btn absolute -right-1 -top-1 rounded-md bg-neutral-700/80 p-1.5 text-neutral-400 opacity-0 backdrop-blur-sm transition-all hover:bg-neutral-600 hover:text-neutral-200 group-hover:opacity-100"
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
		@apply h-2 w-2 animate-typing-dot rounded-full bg-primary-500;
	}

	.animation-delay-160 {
		animation-delay: -0.16s;
	}

	.animation-delay-320 {
		animation-delay: -0.32s;
	}

	/* Tool execution spinner */
	.tool-spinner {
		@apply inline-block h-3 w-3 animate-spin rounded-full border-2 border-primary-500 border-t-transparent;
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

	/* Approval badge pulse animation */
	.approval-badge {
		animation: approval-pulse 2s ease-in-out infinite;
	}

	@keyframes approval-pulse {
		0%,
		100% {
			box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.2);
		}
		50% {
			box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.1);
		}
	}
</style>
