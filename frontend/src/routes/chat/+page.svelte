<script lang="ts">
    /**
     * Chat page - Main conversational assistant interface
     */
    import { onMount } from "svelte";
    import { chatStore } from "$lib/stores/chat.svelte";
    import ChatMessage from "$lib/components/ChatMessage.svelte";
    import ChatInput from "$lib/components/ChatInput.svelte";
    import ApprovalCard from "$lib/components/ApprovalCard.svelte";

    let messagesContainer: HTMLDivElement | null = $state(null);
    let isEnabled = $state(true);

    // Scroll to bottom when messages change
    $effect(() => {
        // Track messages length to trigger scroll
        const messageCount = chatStore.messages.length;
        if (messagesContainer && messageCount > 0) {
            // Use requestAnimationFrame to ensure DOM has updated
            requestAnimationFrame(() => {
                if (messagesContainer) {
                    messagesContainer.scrollTop =
                        messagesContainer.scrollHeight;
                }
            });
        }
    });

    onMount(async () => {
        isEnabled = await chatStore.checkEnabled();
        if (isEnabled) {
            await chatStore.refreshPendingApprovals();
        }
    });

    function handleClearHistory() {
        if (confirm("Clear all chat history?")) {
            chatStore.clearHistory();
        }
    }
</script>

<svelte:head>
    <title>Chat | Homebox Companion</title>
</svelte:head>

<div class="chat-page">
    {#if !isEnabled}
        <div class="disabled-message">
            <h2>Chat Disabled</h2>
            <p>The chat feature is currently disabled on the server.</p>
            <p>Enable it by setting <code>HBC_CHAT_ENABLED=true</code></p>
        </div>
    {:else}
        <header class="chat-header">
            <h1>Chat Assistant</h1>
            {#if chatStore.messages.length > 0}
                <button
                    class="clear-btn"
                    onclick={handleClearHistory}
                    title="Clear history"
                >
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        width="18"
                        height="18"
                    >
                        <path
                            fill-rule="evenodd"
                            d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.519.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z"
                            clip-rule="evenodd"
                        />
                    </svg>
                </button>
            {/if}
        </header>

        {#if chatStore.pendingApprovals.length > 0}
            <div class="approvals">
                {#each chatStore.pendingApprovals as approval (approval.id)}
                    <ApprovalCard {approval} />
                {/each}
            </div>
        {/if}

        {#if chatStore.error}
            <div class="error-banner">
                <span>⚠️ {chatStore.error}</span>
            </div>
        {/if}

        <div class="messages" bind:this={messagesContainer}>
            {#if chatStore.messages.length === 0}
                <div class="empty-state">
                    <div class="icon">💬</div>
                    <h2>Start a conversation</h2>
                    <p>Ask me about your inventory, locations, or items.</p>
                    <div class="suggestions">
                        <button
                            onclick={() =>
                                chatStore.sendMessage(
                                    "What locations do I have?",
                                )}
                        >
                            What locations do I have?
                        </button>
                        <button
                            onclick={() =>
                                chatStore.sendMessage("List my labels")}
                        >
                            List my labels
                        </button>
                        <button
                            onclick={() =>
                                chatStore.sendMessage(
                                    "How many items are in my inventory?",
                                )}
                        >
                            How many items are in my inventory?
                        </button>
                    </div>
                </div>
            {:else}
                {#each chatStore.messages as message (message.id)}
                    <ChatMessage {message} />
                {/each}
            {/if}
        </div>

        <ChatInput />
    {/if}
</div>

<style>
    .chat-page {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: var(--color-background, #fff);
    }

    .chat-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.75rem 1rem;
        border-bottom: 1px solid var(--color-border, #e5e7eb);
        background: var(--color-surface, #f9fafb);
    }

    .chat-header h1 {
        font-size: 1.125rem;
        font-weight: 600;
        margin: 0;
    }

    .clear-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0.5rem;
        border: none;
        border-radius: 0.5rem;
        background: transparent;
        color: var(--color-text-muted, #6b7280);
        cursor: pointer;
        transition:
            color 0.2s,
            background 0.2s;
    }

    .clear-btn:hover {
        color: var(--color-error, #dc2626);
        background: rgba(220, 38, 38, 0.1);
    }

    .approvals {
        padding: 0.5rem 1rem;
        background: var(--color-surface, #f9fafb);
        border-bottom: 1px solid var(--color-border, #e5e7eb);
    }

    .error-banner {
        padding: 0.75rem 1rem;
        background: rgba(239, 68, 68, 0.1);
        color: var(--color-error, #dc2626);
        font-size: 0.875rem;
    }

    .messages {
        flex: 1;
        overflow-y: auto;
        padding: 1rem;
        display: flex;
        flex-direction: column;
    }

    .empty-state {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 2rem;
        color: var(--color-text-muted, #6b7280);
    }

    .empty-state .icon {
        font-size: 3rem;
        margin-bottom: 1rem;
    }

    .empty-state h2 {
        font-size: 1.25rem;
        font-weight: 600;
        margin: 0 0 0.5rem;
        color: var(--color-text, #1f2937);
    }

    .empty-state p {
        margin: 0 0 1.5rem;
    }

    .suggestions {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        width: 100%;
        max-width: 300px;
    }

    .suggestions button {
        padding: 0.75rem 1rem;
        border: 1px solid var(--color-border, #e5e7eb);
        border-radius: 0.75rem;
        background: var(--color-background, #fff);
        color: var(--color-text, #1f2937);
        font-size: 0.875rem;
        text-align: left;
        cursor: pointer;
        transition:
            border-color 0.2s,
            background 0.2s;
    }

    .suggestions button:hover {
        border-color: var(--color-primary, #3b82f6);
        background: var(--color-surface, #f9fafb);
    }

    .disabled-message {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 2rem;
    }

    .disabled-message h2 {
        margin: 0 0 0.5rem;
    }

    .disabled-message code {
        background: var(--color-surface, #f3f4f6);
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.875rem;
    }
</style>
