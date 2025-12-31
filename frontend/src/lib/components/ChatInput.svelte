<script lang="ts">
    /**
     * ChatInput - Text input for sending chat messages
     *
     * Auto-resizing textarea with send button.
     * Disabled while streaming.
     */
    import { chatStore } from "../stores/chat.svelte";

    interface Props {
        hasMessages?: boolean;
        onClearHistory?: () => void;
    }

    let { hasMessages = false, onClearHistory }: Props = $props();

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
    <div class="input-container">
        <textarea
            bind:this={textareaRef}
            bind:value={inputValue}
            onkeydown={handleKeydown}
            oninput={handleInput}
            placeholder="Ask about your inventory..."
            rows="1"
            disabled={chatStore.isStreaming}
            autocomplete="off"
            aria-label="Chat message input"
        ></textarea>

        <button type="submit" disabled={isDisabled} aria-label="Send message">
            {#if chatStore.isStreaming}
                <span class="loading-spinner"></span>
            {:else}
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <path
                        d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z"
                    />
                </svg>
            {/if}
        </button>
    </div>

    <div class="hint-container">
        {#if chatStore.isStreaming}
            <p class="hint streaming">Assistant is typing...</p>
        {:else}
            <p class="hint">Press Enter to send, Shift+Enter for new line</p>
        {/if}
        {#if hasMessages && onClearHistory}
            <button
                type="button"
                class="clear-history-btn"
                onclick={onClearHistory}
                aria-label="Clear chat history"
            >
                Clear
            </button>
        {/if}
    </div>
</form>

<style>
    .chat-input {
        display: flex;
        flex-direction: column;
        gap: 0.375rem;
        padding: 0.5rem 1rem 0.75rem;
        background: #0a0a0f; /* neutral-950 */
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        max-width: 32rem;
        margin: 0 auto;
        width: 100%;
    }

    .input-container {
        display: flex;
        align-items: flex-end;
        gap: 0.625rem;
        background: #13131f; /* neutral-900 */
        border: 1px solid #2a2a3e; /* neutral-700 */
        border-radius: 1.25rem;
        padding: 0.375rem;
        transition:
            border-color 0.15s,
            box-shadow 0.15s;
    }

    .input-container:focus-within {
        border-color: #6366f1; /* primary-500 */
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
    }

    textarea {
        flex: 1;
        resize: none;
        border: none;
        border-radius: 0.875rem;
        padding: 0.625rem 0.875rem;
        font-size: 0.9375rem;
        font-family: inherit;
        line-height: 1.5;
        max-height: 120px;
        outline: none;
        background: transparent;
        color: #e2e8f0; /* neutral-200 */
    }

    textarea::placeholder {
        color: #64748b; /* neutral-500 */
    }

    textarea:disabled {
        color: #64748b; /* neutral-500 */
        cursor: not-allowed;
    }

    button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 2.5rem;
        height: 2.5rem;
        border: none;
        border-radius: 50%;
        background: linear-gradient(
            135deg,
            #6366f1,
            #4f46e5
        ); /* primary gradient */
        color: white;
        cursor: pointer;
        transition: all 0.15s ease;
        flex-shrink: 0;
        box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
    }

    button svg {
        width: 1.125rem;
        height: 1.125rem;
    }

    button:hover:not(:disabled) {
        transform: scale(1.05);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }

    button:active:not(:disabled) {
        transform: scale(0.95);
    }

    button:disabled {
        background: #2a2a3e; /* neutral-700 */
        color: #4b5563; /* neutral-600 */
        cursor: not-allowed;
        box-shadow: none;
    }

    .hint-container {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        position: relative;
    }

    .hint {
        text-align: center;
        font-size: 0.6875rem;
        color: #475569; /* neutral-600 */
        margin: 0;
        opacity: 0.8;
    }

    .hint.streaming {
        color: #6366f1; /* primary-500 */
        opacity: 1;
    }

    .clear-history-btn {
        position: absolute;
        right: 0;
        padding: 0.25rem 0.5rem;
        font-size: 0.6875rem;
        color: #64748b; /* neutral-500 */
        background: transparent;
        border: none;
        border-radius: 0.375rem;
        cursor: pointer;
        transition: all 0.15s ease;
        opacity: 0.8;
    }

    .clear-history-btn:hover {
        color: #ef4444; /* error-500 */
        background: rgba(239, 68, 68, 0.1);
        opacity: 1;
    }

    .clear-history-btn:active {
        transform: scale(0.95);
    }

    .loading-spinner {
        width: 1.125rem;
        height: 1.125rem;
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
