<script lang="ts">
    /**
     * Chat page - Main conversational assistant interface
     *
     * Layout follows the Capture page pattern:
     * - Main scrollable content area with pb-28 padding
     * - Fixed input pinned to bottom (above navigation) using bottom-nav-offset
     */
    import { onMount } from "svelte";
    import { chatStore } from "$lib/stores/chat.svelte";
    import { createLogger } from "$lib/utils/logger";
    import ChatMessage from "$lib/components/ChatMessage.svelte";
    import ChatInput from "$lib/components/ChatInput.svelte";
    import ApprovalCard from "$lib/components/ApprovalCard.svelte";

    const log = createLogger({ prefix: "ChatPage" });

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
                    messagesContainer.scrollTop =
                        messagesContainer.scrollHeight;
                    log.debug("Scrolled to bottom of messages");
                }
            });
        }
    });

    onMount(async () => {
        log.info("Chat page mounted");
        isEnabled = await chatStore.checkEnabled();
        log.debug(`Chat enabled: ${isEnabled}`);
        if (isEnabled) {
            await chatStore.refreshPendingApprovals();
            log.debug(
                `Pending approvals: ${chatStore.pendingApprovals.length}`,
            );
        }
    });

    async function handleClearHistory() {
        if (confirm("Clear all chat history?")) {
            log.info("Clearing chat history");
            await chatStore.clearHistory();
            log.debug("Chat history cleared");
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
            <div class="w-16 h-16 flex items-center justify-center rounded-2xl bg-error-500/10 mb-5">
                <svg
                    class="w-8 h-8 text-error-500"
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
            <h2 class="text-h3 text-neutral-100 mb-2">Chat Disabled</h2>
            <p class="text-body-sm text-neutral-400 mb-1">The chat feature is currently disabled on the server.</p>
            <p class="text-body-sm text-neutral-400 mb-1">Enable it by setting <code class="inline-block mt-3 bg-neutral-800 text-primary-300 px-3 py-1.5 rounded-lg text-[0.8125rem] font-mono border border-neutral-700">HBC_CHAT_ENABLED=true</code></p>
        </div>
    {:else}
        <!-- Pending approvals (if any) -->
        {#if chatStore.pendingApprovals.length > 0}
            <div class="py-3 px-4 bg-neutral-950 border-b border-white/[0.08] max-h-[30vh] overflow-y-auto">
                {#each chatStore.pendingApprovals as approval (approval.id)}
                    <ApprovalCard {approval} />
                {/each}
            </div>
        {/if}

        <!-- Error banner -->
        {#if chatStore.error}
            <div class="flex items-center gap-2 py-2.5 px-4 bg-error-500/10 text-error-400 text-body-sm border-b border-error-500/15">
                <svg
                    class="w-4 h-4 shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    stroke-width="1.5"
                >
                    <path
                        d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                    />
                </svg>
                <span>{chatStore.error}</span>
            </div>
        {/if}

        <!-- Messages area -->
        <div class="min-h-[50vh]" bind:this={messagesContainer}>
            {#if chatStore.messages.length === 0}
                <div class="empty-state">
                    <div class="w-16 h-16 flex items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500/15 to-purple-500/10 mb-5">
                        <svg
                            class="w-8 h-8 text-primary-500"
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
                    <h2 class="text-h3 text-neutral-100 mb-1.5">Start a conversation</h2>
                    <p class="text-body-sm text-neutral-400 mb-6">Ask me about your inventory, locations, or items.</p>
                    <div class="flex flex-col gap-2 w-full max-w-80">
                        <button
                            class="flex items-center gap-2.5 py-3 px-4 border border-neutral-700 rounded-xl bg-neutral-900 text-neutral-200 text-body-sm text-left cursor-pointer transition-all duration-fast hover:border-primary-500 hover:bg-neutral-800 hover:-translate-y-px active:scale-[0.98]"
                            onclick={() =>
                                chatStore.sendMessage(
                                    "What locations do I have?",
                                )}
                        >
                            <svg
                                class="w-[1.125rem] h-[1.125rem] shrink-0 text-primary-500"
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
                            class="flex items-center gap-2.5 py-3 px-4 border border-neutral-700 rounded-xl bg-neutral-900 text-neutral-200 text-body-sm text-left cursor-pointer transition-all duration-fast hover:border-primary-500 hover:bg-neutral-800 hover:-translate-y-px active:scale-[0.98]"
                            onclick={() =>
                                chatStore.sendMessage("List my labels")}
                        >
                            <svg
                                class="w-[1.125rem] h-[1.125rem] shrink-0 text-primary-500"
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
                            class="flex items-center gap-2.5 py-3 px-4 border border-neutral-700 rounded-xl bg-neutral-900 text-neutral-200 text-body-sm text-left cursor-pointer transition-all duration-fast hover:border-primary-500 hover:bg-neutral-800 hover:-translate-y-px active:scale-[0.98]"
                            onclick={() =>
                                chatStore.sendMessage(
                                    "How many items are in my inventory?",
                                )}
                        >
                            <svg
                                class="w-[1.125rem] h-[1.125rem] shrink-0 text-primary-500"
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
                <div class="flex flex-col gap-3 p-4 max-w-2xl mx-auto lg:max-w-3xl">
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
        <div class="max-w-lg mx-auto">
            <ChatInput
                hasMessages={chatStore.messages.length > 0}
                onClearHistory={handleClearHistory}
            />
        </div>
    </div>
{/if}

