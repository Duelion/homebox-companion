<script lang="ts">
    /**
     * ChatInput - Text input for sending chat messages
     *
     * Auto-resizing textarea with send button.
     * Disabled while streaming.
     */
    import { chatStore } from "../stores/chat.svelte";

    let inputValue = $state("");
    let textareaRef: HTMLTextAreaElement | null = $state(null);

    const isDisabled = $derived(chatStore.isStreaming || !inputValue.trim());

    function handleSubmit() {
        if (isDisabled) return;

        chatStore.sendMessage(inputValue.trim());
        inputValue = "";

        // Reset textarea height
        if (textareaRef) {
            textareaRef.style.height = "auto";
        }
    }

    function handleKeydown(event: KeyboardEvent) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            handleSubmit();
        }
    }

    function handleInput() {
        // Auto-resize textarea
        if (textareaRef) {
            textareaRef.style.height = "auto";
            textareaRef.style.height =
                Math.min(textareaRef.scrollHeight, 120) + "px";
        }
    }
</script>

<form
    class="chat-input"
    onsubmit={(e) => {
        e.preventDefault();
        handleSubmit();
    }}
>
    <textarea
        bind:this={textareaRef}
        bind:value={inputValue}
        onkeydown={handleKeydown}
        oninput={handleInput}
        placeholder="Type a message..."
        rows="1"
        disabled={chatStore.isStreaming}
        autocomplete="off"
        aria-label="Chat message input"
    ></textarea>

    <button type="submit" disabled={isDisabled} aria-label="Send message">
        {#if chatStore.isStreaming}
            <span class="loading-spinner"></span>
        {:else}
            <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                width="20"
                height="20"
            >
                <path
                    d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z"
                />
            </svg>
        {/if}
    </button>
</form>

<style>
    .chat-input {
        display: flex;
        gap: 0.5rem;
        padding: 0.75rem;
        background: var(--color-background, #fff);
        border-top: 1px solid var(--color-border, #e5e7eb);
    }

    textarea {
        flex: 1;
        resize: none;
        border: 1px solid var(--color-border, #e5e7eb);
        border-radius: 1rem;
        padding: 0.625rem 1rem;
        font-size: 1rem;
        font-family: inherit;
        line-height: 1.5;
        max-height: 120px;
        outline: none;
        transition: border-color 0.2s;
    }

    textarea:focus {
        border-color: var(--color-primary, #3b82f6);
    }

    textarea:disabled {
        background: var(--color-surface, #f9fafb);
        cursor: not-allowed;
    }

    button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 44px;
        height: 44px;
        border: none;
        border-radius: 50%;
        background: var(--color-primary, #3b82f6);
        color: white;
        cursor: pointer;
        transition:
            background 0.2s,
            opacity 0.2s;
        flex-shrink: 0;
    }

    button:hover:not(:disabled) {
        background: var(--color-primary-dark, #2563eb);
    }

    button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .loading-spinner {
        width: 20px;
        height: 20px;
        border: 2px solid rgba(255, 255, 255, 0.3);
        border-top-color: white;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }
</style>
