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
<div class="animate-in pb-28">
    {#if !isEnabled}
        <!-- Disabled state -->
        <div class="disabled-message">
            <div class="disabled-icon">
                <svg
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
            <h2>Chat Disabled</h2>
            <p>The chat feature is currently disabled on the server.</p>
            <p>Enable it by setting <code>HBC_CHAT_ENABLED=true</code></p>
        </div>
    {:else}
        <!-- Pending approvals (if any) -->
        {#if chatStore.pendingApprovals.length > 0}
            <div class="approvals">
                {#each chatStore.pendingApprovals as approval (approval.id)}
                    <ApprovalCard {approval} />
                {/each}
            </div>
        {/if}

        <!-- Error banner -->
        {#if chatStore.error}
            <div class="error-banner">
                <svg
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
        <div class="messages-area" bind:this={messagesContainer}>
            {#if chatStore.messages.length === 0}
                <div class="empty-state">
                    <div class="empty-icon">
                        <svg
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
                    <h2>Start a conversation</h2>
                    <p>Ask me about your inventory, locations, or items.</p>
                    <div class="suggestions">
                        <button
                            onclick={() =>
                                chatStore.sendMessage(
                                    "What locations do I have?",
                                )}
                        >
                            <svg
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
                            <span>What locations do I have?</span>
                        </button>
                        <button
                            onclick={() =>
                                chatStore.sendMessage("List my labels")}
                        >
                            <svg
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
                            <span>List my labels</span>
                        </button>
                        <button
                            onclick={() =>
                                chatStore.sendMessage(
                                    "How many items are in my inventory?",
                                )}
                        >
                            <svg
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                                stroke-width="1.5"
                            >
                                <path
                                    d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"
                                />
                            </svg>
                            <span>How many items are in my inventory?</span>
                        </button>
                    </div>
                </div>
            {:else}
                <div class="messages-list">
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
    <div
        class="fixed bottom-nav-offset left-0 right-0 bg-neutral-950/95 backdrop-blur-lg border-t border-neutral-800 p-4 z-40"
    >
        <div class="max-w-lg mx-auto">
            <ChatInput
                hasMessages={chatStore.messages.length > 0}
                onClearHistory={handleClearHistory}
            />
        </div>
    </div>
{/if}

<style>
    /* Pending approvals */
    .approvals {
        padding: 0.75rem 1rem;
        background: #0f0f18;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        max-height: 30vh;
        overflow-y: auto;
    }

    /* Error banner */
    .error-banner {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.625rem 1rem;
        background: rgba(239, 68, 68, 0.1);
        color: #f87171; /* error-400 */
        font-size: 0.875rem;
        border-bottom: 1px solid rgba(239, 68, 68, 0.15);
    }

    .error-banner svg {
        width: 1rem;
        height: 1rem;
        flex-shrink: 0;
    }

    /* Messages area */
    .messages-area {
        min-height: 50vh;
    }

    .messages-list {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        padding: 1rem;
        max-width: 32rem;
        margin: 0 auto;
    }

    /* Empty state */
    .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 3rem 1.5rem;
        min-height: 50vh;
    }

    .empty-icon {
        width: 4rem;
        height: 4rem;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 1rem;
        background: linear-gradient(
            135deg,
            rgba(99, 102, 241, 0.15),
            rgba(139, 92, 246, 0.1)
        );
        margin-bottom: 1.25rem;
    }

    .empty-icon svg {
        width: 2rem;
        height: 2rem;
        color: #6366f1; /* primary-500 */
    }

    .empty-state h2 {
        font-size: 1.25rem;
        font-weight: 600;
        margin: 0 0 0.375rem;
        color: #f1f5f9; /* neutral-100 */
    }

    .empty-state > p {
        margin: 0 0 1.5rem;
        color: #94a3b8; /* neutral-400 */
        font-size: 0.875rem;
    }

    /* Suggestion buttons */
    .suggestions {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        width: 100%;
        max-width: 20rem;
    }

    .suggestions button {
        display: flex;
        align-items: center;
        gap: 0.625rem;
        padding: 0.75rem 1rem;
        border: 1px solid #2a2a3e; /* neutral-700 */
        border-radius: 0.75rem;
        background: #13131f; /* neutral-900 */
        color: #e2e8f0; /* neutral-200 */
        font-size: 0.875rem;
        text-align: left;
        cursor: pointer;
        transition: all 0.15s ease;
    }

    .suggestions button:hover {
        border-color: #6366f1; /* primary-500 */
        background: #1a1a2e;
        transform: translateY(-1px);
    }

    .suggestions button:active {
        transform: scale(0.98);
    }

    .suggestions button svg {
        width: 1.125rem;
        height: 1.125rem;
        flex-shrink: 0;
        color: #6366f1; /* primary-500 */
    }

    .suggestions button span {
        flex: 1;
    }

    /* Disabled state */
    .disabled-message {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 3rem 1.5rem;
        min-height: 60vh;
    }

    .disabled-icon {
        width: 4rem;
        height: 4rem;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 1rem;
        background: rgba(239, 68, 68, 0.1);
        margin-bottom: 1.25rem;
    }

    .disabled-icon svg {
        width: 2rem;
        height: 2rem;
        color: #ef4444; /* error-500 */
    }

    .disabled-message h2 {
        font-size: 1.25rem;
        font-weight: 600;
        margin: 0 0 0.5rem;
        color: #f1f5f9; /* neutral-100 */
    }

    .disabled-message p {
        margin: 0 0 0.25rem;
        color: #94a3b8; /* neutral-400 */
        font-size: 0.875rem;
    }

    .disabled-message code {
        display: inline-block;
        margin-top: 0.75rem;
        background: #1e1e2e; /* neutral-800 */
        color: #a5b4fc; /* primary-300 */
        padding: 0.375rem 0.75rem;
        border-radius: 0.5rem;
        font-size: 0.8125rem;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
            monospace;
        border: 1px solid #2a2a3e; /* neutral-700 */
    }
</style>
