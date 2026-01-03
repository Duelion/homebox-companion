<script lang="ts">
	/**
	 * Chat page - Main conversational assistant interface
	 *
	 * Layout follows the Capture page pattern:
	 * - Main scrollable content area with pb-28 padding
	 * - Fixed input pinned to bottom (above navigation) using bottom-nav-offset
	 */
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { chatStore } from '$lib/stores/chat.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import { createLogger } from '$lib/utils/logger';
	import ChatMessage from '$lib/components/ChatMessage.svelte';
	import ChatInput from '$lib/components/ChatInput.svelte';
	import ApprovalModal from '$lib/components/ApprovalModal.svelte';
	import AppContainer from '$lib/components/AppContainer.svelte';

	const log = createLogger({ prefix: 'ChatPage' });

	let messagesContainer: HTMLDivElement | null = $state(null);
	let isEnabled = $state(true);
	let approvalModalOpen = $state(false);

	// Terminal-style auto-scroll: only scroll if user hasn't scrolled up
	let userHasScrolledUp = $state(false);
	const SCROLL_THRESHOLD = 50; // pixels from bottom to consider "at bottom"

	// Find the last assistant message index for showing approval badge
	const lastAssistantIndex = $derived.by(() => {
		for (let i = chatStore.messages.length - 1; i >= 0; i--) {
			if (chatStore.messages[i].role === 'assistant') {
				return i;
			}
		}
		return -1;
	});

	// Check if container is scrolled to bottom
	function isAtBottom(container: HTMLElement): boolean {
		return container.scrollHeight - container.scrollTop - container.clientHeight < SCROLL_THRESHOLD;
	}

	// Scroll to bottom helper
	function scrollToBottom() {
		if (messagesContainer) {
			messagesContainer.scrollTop = messagesContainer.scrollHeight;
		}
	}

	// Handle user scroll - detect if they've scrolled up from bottom
	function handleScroll(event: Event) {
		const container = event.target as HTMLElement;
		if (!container) return;

		const atBottom = isAtBottom(container);
		if (atBottom && userHasScrolledUp) {
			// User scrolled back to bottom - re-enable auto-scroll
			userHasScrolledUp = false;
			log.debug('User scrolled to bottom, re-enabling auto-scroll');
		} else if (!atBottom && !userHasScrolledUp && chatStore.isStreaming) {
			// User scrolled up during streaming - disable auto-scroll
			userHasScrolledUp = true;
			log.debug('User scrolled up, disabling auto-scroll');
		}
	}

	// Auto-scroll when new messages arrive
	$effect(() => {
		const messageCount = chatStore.messages.length;
		if (messagesContainer && messageCount > 0 && !userHasScrolledUp) {
			requestAnimationFrame(scrollToBottom);
		}
	});

	// Auto-scroll during streaming (tracks content changes)
	$effect(() => {
		// Access streaming message content to trigger reactivity
		const lastMessage = chatStore.messages[chatStore.messages.length - 1];
		const streamingContent = lastMessage?.content;
		const isStreaming = chatStore.isStreaming;

		if (messagesContainer && isStreaming && streamingContent && !userHasScrolledUp) {
			requestAnimationFrame(scrollToBottom);
		}
	});

	onMount(async () => {
		log.info('Chat page mounted');

		// Wait for auth initialization to complete to avoid race conditions
		// where we check isAuthenticated before initializeAuth clears expired tokens
		await getInitPromise();

		// Redirect if not authenticated
		if (!authStore.isAuthenticated) {
			goto(resolve('/'));
			return;
		}

		isEnabled = await chatStore.checkEnabled();
		log.debug(`Chat enabled: ${isEnabled}`);
		if (isEnabled) {
			await chatStore.refreshPendingApprovals();
			log.debug(`Pending approvals: ${chatStore.pendingApprovals.length}`);
		}
	});

	async function handleClearHistory() {
		if (confirm('Clear all chat history?')) {
			log.info('Clearing chat history');
			await chatStore.clearHistory();
			log.debug('Chat history cleared');
		}
	}

	function handleOpenApprovals() {
		approvalModalOpen = true;
	}
</script>

<svelte:head>
	<title>Chat | Homebox Companion</title>
</svelte:head>

<!-- Main content area with bottom padding for the fixed input -->
<div class="page-content">
	{#if !isEnabled}
		<!-- Disabled state -->
		<div class="empty-state min-h-[60vh]">
			<div class="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-error-500/10">
				<svg
					class="h-8 w-8 text-error-500"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
					/>
				</svg>
			</div>
			<h2 class="mb-2 text-h3 text-neutral-100">Chat Disabled</h2>
			<p class="mb-1 text-body-sm text-neutral-400">
				The chat feature is currently disabled on the server.
			</p>
			<p class="mb-1 text-body-sm text-neutral-400">
				Enable it by setting <code
					class="mt-3 inline-block rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 font-mono text-[0.8125rem] text-primary-300"
					>HBC_CHAT_ENABLED=true</code
				>
			</p>
		</div>
	{:else}
		<!-- Error banner -->
		{#if chatStore.error}
			<div
				class="text-error-400 flex items-center gap-2 border-b border-error-500/15 bg-error-500/10 px-4 py-2.5 text-body-sm"
			>
				<svg
					class="h-4 w-4 shrink-0"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
				</svg>
				<span>{chatStore.error}</span>
			</div>
		{/if}

		<!-- Messages area -->
		<div class="min-h-[50vh]" bind:this={messagesContainer} onscroll={handleScroll}>
			{#if chatStore.messages.length === 0}
				<div class="flex flex-col items-center justify-center pb-16 pt-8">
					<div
						class="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-primary-600/20 shadow-lg"
					>
						<svg
							class="h-14 w-14 text-primary-400"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
							stroke-linecap="round"
							stroke-linejoin="round"
						>
							<path
								d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"
							/>
						</svg>
					</div>
					<h2 class="mb-2 px-4 text-center text-h1 text-neutral-100">Start a conversation</h2>
					<p class="mb-6 max-w-xs px-4 text-center text-body text-neutral-400">
						Ask me about your inventory, locations, or items.
					</p>
					<div class="flex w-full max-w-sm flex-col gap-2 px-4">
						<button
							class="flex cursor-pointer items-center gap-2.5 rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-left text-body-sm text-neutral-200 transition-all duration-fast hover:-translate-y-px hover:border-primary-500 hover:bg-neutral-800 active:scale-[0.98]"
							onclick={() => chatStore.sendMessage('What locations do I have?')}
						>
							<svg
								class="h-[1.125rem] w-[1.125rem] shrink-0 text-primary-500"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
								<path
									d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z"
								/>
							</svg>
							<span class="flex-1">What locations do I have?</span>
						</button>
						<button
							class="flex cursor-pointer items-center gap-2.5 rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-left text-body-sm text-neutral-200 transition-all duration-fast hover:-translate-y-px hover:border-primary-500 hover:bg-neutral-800 active:scale-[0.98]"
							onclick={() => chatStore.sendMessage('List my labels')}
						>
							<svg
								class="h-[1.125rem] w-[1.125rem] shrink-0 text-primary-500"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path
									d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z"
								/>
								<path d="M6 6h.008v.008H6V6z" />
							</svg>
							<span class="flex-1">List my labels</span>
						</button>
						<button
							class="flex cursor-pointer items-center gap-2.5 rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-left text-body-sm text-neutral-200 transition-all duration-fast hover:-translate-y-px hover:border-primary-500 hover:bg-neutral-800 active:scale-[0.98]"
							onclick={() => chatStore.sendMessage('How many items are in my inventory?')}
						>
							<svg
								class="h-[1.125rem] w-[1.125rem] shrink-0 text-primary-500"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path
									d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"
								/>
							</svg>
							<span class="flex-1">How many items are in my inventory?</span>
						</button>
					</div>
				</div>
			{:else}
				<div class="mx-auto flex max-w-2xl flex-col gap-3 p-4 lg:max-w-3xl">
					{#each chatStore.messages as message, index (message.id)}
						<ChatMessage
							{message}
							pendingApprovalCount={index === lastAssistantIndex
								? chatStore.pendingApprovals.length
								: 0}
							onOpenApprovals={handleOpenApprovals}
						/>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>

<!-- Fixed input at bottom - above navigation bar -->
{#if isEnabled}
	<div class="chat-input-keyboard-aware px-3">
		<AppContainer>
			<ChatInput hasMessages={chatStore.messages.length > 0} onClearHistory={handleClearHistory} />
		</AppContainer>
	</div>
{/if}

<!-- Approval Modal -->
<ApprovalModal bind:open={approvalModalOpen} approvals={chatStore.pendingApprovals} />
