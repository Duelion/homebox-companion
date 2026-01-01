<script lang="ts">
	/**
	 * Chat page - Main conversational assistant interface
	 *
	 * Layout follows the Capture page pattern:
	 * - Main scrollable content area with pb-28 padding
	 * - Fixed input pinned to bottom (above navigation) using bottom-nav-offset
	 */
	import { onMount } from 'svelte';
	import { chatStore } from '$lib/stores/chat.svelte';
	import { createLogger } from '$lib/utils/logger';
	import ChatMessage from '$lib/components/ChatMessage.svelte';
	import ChatInput from '$lib/components/ChatInput.svelte';
	import ApprovalCard from '$lib/components/ApprovalCard.svelte';

	const log = createLogger({ prefix: 'ChatPage' });

	let messagesContainer: HTMLDivElement | null = $state(null);
	let isEnabled = $state(true);

	// Scroll to bottom when messages change
	$effect(() => {
		// Track messages length to trigger scroll
		const messageCount = chatStore.messages.length;
		log.debug(`Messages count changed: ${messageCount}`);
		if (messagesContainer && messageCount > 0) {
			// Use requestAnimationFrame to ensure DOM has updated
			requestAnimationFrame(() => {
				if (messagesContainer) {
					messagesContainer.scrollTop = messagesContainer.scrollHeight;
					log.debug('Scrolled to bottom of messages');
				}
			});
		}
	});

	onMount(async () => {
		log.info('Chat page mounted');
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
		<!-- Pending approvals (if any) -->
		{#if chatStore.pendingApprovals.length > 0}
			<div
				class="max-h-[30vh] overflow-y-auto border-b border-white/[0.08] bg-neutral-950 px-4 py-3"
			>
				{#each chatStore.pendingApprovals as approval (approval.id)}
					<ApprovalCard {approval} />
				{/each}
			</div>
		{/if}

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
		<div class="min-h-[50vh]" bind:this={messagesContainer}>
			{#if chatStore.messages.length === 0}
				<div class="empty-state">
					<div
						class="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500/15 to-purple-500/10"
					>
						<svg
							class="h-8 w-8 text-primary-500"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path
								d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"
							/>
						</svg>
					</div>
					<h2 class="mb-1.5 text-h3 text-neutral-100">Start a conversation</h2>
					<p class="mb-6 text-body-sm text-neutral-400">
						Ask me about your inventory, locations, or items.
					</p>
					<div class="flex w-full max-w-80 flex-col gap-2">
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
					{#each chatStore.messages as message (message.id)}
						<ChatMessage {message} />
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>

<!-- Fixed input at bottom - above navigation bar (same pattern as Capture page) -->
{#if isEnabled}
	<div class="fixed-bottom-panel p-4">
		<div class="mx-auto max-w-lg">
			<ChatInput hasMessages={chatStore.messages.length > 0} onClearHistory={handleClearHistory} />
		</div>
	</div>
{/if}
