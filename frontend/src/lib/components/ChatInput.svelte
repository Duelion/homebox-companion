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

    function handleCancel() {
        chatStore.cancelStreaming();
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
    class="flex flex-col gap-1.5 py-2 px-4 pb-3 bg-neutral-950 border-t border-white/[0.08] max-w-2xl mx-auto w-full"
    onsubmit={(e) => {
        e.preventDefault();
        handleSubmit();
    }}
>
    <div class="flex items-end gap-2.5 bg-neutral-900 border border-neutral-700 rounded-2xl p-1.5 transition-all duration-fast focus-within:border-primary-500 focus-within:shadow-[0_0_0_2px_rgba(99,102,241,0.15)]">
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
            class="flex-1 resize-none border-0 rounded-pill py-2.5 px-3.5 text-md-tight leading-relaxed max-h-30 outline-none bg-transparent text-neutral-200 placeholder:text-neutral-500 disabled:text-neutral-500 disabled:cursor-not-allowed"
        ></textarea>

        <button 
            type="submit" 
            disabled={isDisabled} 
            aria-label="Send message"
            class="flex items-center justify-center w-10 h-10 border-0 rounded-full text-white cursor-pointer transition-all duration-fast shrink-0 bg-gradient-to-br from-primary-500 to-primary-600 shadow-[0_2px_8px_rgba(99,102,241,0.3)] hover:scale-105 hover:shadow-[0_4px_12px_rgba(99,102,241,0.4)] active:scale-95 disabled:bg-neutral-700 disabled:text-neutral-600 disabled:cursor-not-allowed disabled:shadow-none"
        >
            {#if chatStore.isStreaming}
                <span class="loading-spinner"></span>
            {:else}
                <svg class="w-4.5 h-4.5" viewBox="0 0 24 24" fill="currentColor">
                    <path
                        d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z"
                    />
                </svg>
            {/if}
        </button>

        {#if chatStore.isStreaming}
            <button
                type="button"
                onclick={handleCancel}
                aria-label="Stop generating"
                class="flex items-center justify-center w-10 h-10 border-0 rounded-full text-white cursor-pointer transition-all duration-fast shrink-0 bg-error-500 shadow-[0_2px_8px_rgba(239,68,68,0.3)] hover:scale-105 hover:shadow-[0_4px_12px_rgba(239,68,68,0.4)] hover:bg-error-600 active:scale-95"
            >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
            </button>
        {/if}
    </div>

    <div class="flex items-center justify-center gap-3 relative">
        {#if chatStore.isStreaming}
            <p class="text-center text-xs-tight text-primary-500 m-0 opacity-100">Assistant is typing...</p>
        {:else}
            <p class="text-center text-xs-tight text-neutral-600 m-0 opacity-80">Press Enter to send, Shift+Enter for new line</p>
        {/if}
        {#if hasMessages && onClearHistory}
            <button
                type="button"
                onclick={onClearHistory}
                aria-label="Clear chat history"
                class="absolute right-0 py-1 px-2 text-xs-tight text-neutral-500 bg-transparent border-0 rounded-md cursor-pointer transition-all duration-fast opacity-80 hover:text-error-500 hover:bg-error-500/10 hover:opacity-100 active:scale-95"
            >
                Clear
            </button>
        {/if}
    </div>
</form>

<style>
    .loading-spinner {
        @apply w-4.5 h-4.5 border-2 border-white/30 border-t-white rounded-full animate-spin;
    }
</style>
