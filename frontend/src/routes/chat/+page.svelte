<script lang="ts">
	/**
	 * Chat page - Main conversational assistant interface
	 *
	 * Layout follows the Capture page pattern:
	 * - Main scrollable content area with pb-28 padding
	 * - Fixed input pinned to bottom (above navigation) using bottom-nav-offset
	 */
	import { onMount, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { chatStore } from '$lib/stores/chat.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { showToast } from '$lib/stores/ui.svelte';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import { getIsDemoModeExplicit, setDemoMode, getConfig } from '$lib/api/settings';
	import { createLogger } from '$lib/utils/logger';
	import {
		TriangleAlert,
		CircleAlert,
		Ban,
		MessageSquare,
		MapPin,
		Tag,
		Archive,
	} from 'lucide-svelte';
	import ChatMessage from '$lib/components/ChatMessage.svelte';
	import ChatInput from '$lib/components/ChatInput.svelte';
	import ApprovalModal from '$lib/components/ApprovalModal.svelte';
	import AppContainer from '$lib/components/AppContainer.svelte';

	const log = createLogger({ prefix: 'ChatPage' });

	let messagesContainer: HTMLDivElement | null = $state(null);
	let isEnabled = $state(true);
	let isDemoMode = $state(false);
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

	// Show errors as toast notifications instead of banner
	$effect(() => {
		const error = chatStore.error;
		if (error) {
			showToast(error, 'error');
			// Use untrack to avoid re-triggering this effect when clearing
			untrack(() => chatStore.clearError());
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

		// Ensure demo mode state is initialized before checking it
		// (guards against race condition where this page mounts before layout's config fetch completes)
		try {
			const config = await getConfig();
			setDemoMode(config.is_demo_mode, config.demo_mode_explicit);
		} catch (error) {
			log.debug('Failed to fetch config:', error);
		}

		// Check if in explicit demo mode (HBC_DEMO_MODE env var) - chat is disabled
		isDemoMode = getIsDemoModeExplicit();
		if (isDemoMode) {
			isEnabled = false;
			log.debug('Chat disabled: explicit demo mode (HBC_DEMO_MODE=true)');
			return;
		}

		isEnabled = await chatStore.checkEnabled();
		log.debug(`Chat enabled: ${isEnabled}`);
		if (isEnabled) {
			// Validate session state with backend - clears local messages if backend was reset
			await chatStore.validateSession();

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
			{#if isDemoMode}
				<!-- Demo mode specific disabled state -->
				<div class="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-warning-500/10">
					<CircleAlert class="text-warning-500" size={32} strokeWidth={1.5} />
				</div>
				<h2 class="mb-2 text-h3 text-neutral-100">Chat Unavailable</h2>
				<p class="mb-3 max-w-xs text-center text-body-sm text-neutral-400">
					Sorry, the chat feature is disabled in demo mode to prevent misuse.
				</p>
				<p class="max-w-xs text-center text-body-sm text-neutral-500">
					To use chat, please set up your own instance with your own API key.
				</p>
			{:else}
				<!-- Server disabled state -->
				<div class="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-error-500/10">
					<Ban class="text-error-500" size={32} strokeWidth={1.5} />
				</div>
				<h2 class="mb-2 text-h3 text-neutral-100">Chat Disabled</h2>
				<p class="mb-1 text-body-sm text-neutral-400">
					The chat feature is currently disabled on the server.
				</p>
				<p class="mb-1 text-body-sm text-neutral-400">
					Enable it by setting <code
						class="mt-3 inline-block rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 font-mono text-sm-tight text-primary-300"
						>HBC_CHAT_ENABLED=true</code
					>
				</p>
			{/if}
		</div>
	{:else}
		<!-- Messages area -->
		<div class="min-h-[50vh]" bind:this={messagesContainer} onscroll={handleScroll}>
			{#if chatStore.messages.length === 0}
				<div class="flex flex-col items-center justify-center pb-16 pt-8">
					<div
						class="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-primary-600/20 shadow-lg"
					>
						<MessageSquare class="text-primary-400" size={56} strokeWidth={1.5} />
					</div>
					<h2 class="mb-2 px-4 text-center text-h1 text-neutral-100">Start a conversation</h2>
					<p class="mb-6 max-w-xs px-4 text-center text-body text-neutral-400">
						Ask me about your inventory, locations, or items.
					</p>

					<!-- Experimental Feature Warning -->
					<div
						class="mx-4 mb-6 max-w-sm rounded-xl border border-warning-500/30 bg-warning-500/10 p-4"
					>
						<div class="flex items-start gap-2.5">
							<TriangleAlert
								class="mt-0.5 flex-shrink-0 text-warning-500"
								size={20}
								strokeWidth={1.5}
							/>
							<div>
								<p class="mb-1 text-sm font-medium text-warning-500">Experimental Feature</p>
								<p class="text-xs leading-relaxed text-neutral-400">
									Chat is still experimental. While many safeguards are in place and it's been
									tested, please <strong class="text-neutral-300">back up your inventory</strong>
									before use.
								</p>
							</div>
						</div>
					</div>

					<div class="flex w-full max-w-sm flex-col gap-2 px-4">
						<button
							class="flex cursor-pointer items-center gap-2.5 rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-left text-body-sm text-neutral-200 transition-all duration-fast hover:-translate-y-px hover:border-primary-500 hover:bg-neutral-800 active:scale-[0.98]"
							onclick={() => chatStore.sendMessage('What locations do I have?')}
						>
							<MapPin class="shrink-0 text-primary-500" size={18} strokeWidth={1.5} />
							<span class="flex-1">What locations do I have?</span>
						</button>
						<button
							class="flex cursor-pointer items-center gap-2.5 rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-left text-body-sm text-neutral-200 transition-all duration-fast hover:-translate-y-px hover:border-primary-500 hover:bg-neutral-800 active:scale-[0.98]"
							onclick={() => chatStore.sendMessage('List my labels')}
						>
							<Tag class="shrink-0 text-primary-500" size={18} strokeWidth={1.5} />
							<span class="flex-1">List my labels</span>
						</button>
						<button
							class="flex cursor-pointer items-center gap-2.5 rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-left text-body-sm text-neutral-200 transition-all duration-fast hover:-translate-y-px hover:border-primary-500 hover:bg-neutral-800 active:scale-[0.98]"
							onclick={() => chatStore.sendMessage('How many items are in my inventory?')}
						>
							<Archive class="shrink-0 text-primary-500" size={18} strokeWidth={1.5} />
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
