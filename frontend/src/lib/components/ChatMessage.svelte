<script lang="ts">
    /**
     * ChatMessage - Displays a single chat message bubble
     *
     * User messages are right-aligned with primary color.
     * Assistant messages are left-aligned with surface color.
     */
    import type {
        ChatMessage as ChatMessageType,
        ToolResult,
    } from "../stores/chat.svelte";

    interface Props {
        message: ChatMessageType;
    }

    let { message }: Props = $props();

    const isUser = $derived(message.role === "user");
    const hasToolResults = $derived(
        message.toolResults && message.toolResults.length > 0,
    );
</script>

<div class="message-container" class:user={isUser} class:assistant={!isUser}>
    <div class="message-bubble" class:streaming={message.isStreaming}>
        {#if message.content}
            <p class="content">{message.content}</p>
        {/if}

        {#if message.isStreaming && !message.content}
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        {/if}

        {#if hasToolResults}
            <div class="tool-results">
                {#each message.toolResults as result}
                    <div
                        class="tool-result"
                        class:success={result.success}
                        class:error={!result.success}
                    >
                        <span class="tool-icon"
                            >{result.success ? "✓" : "✗"}</span
                        >
                        <span class="tool-name">{result.tool}</span>
                    </div>
                {/each}
            </div>
        {/if}
    </div>

    <time class="timestamp">
        {message.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        })}
    </time>
</div>

<style>
    .message-container {
        display: flex;
        flex-direction: column;
        margin-bottom: 1rem;
        max-width: 85%;
    }

    .message-container.user {
        align-self: flex-end;
        align-items: flex-end;
    }

    .message-container.assistant {
        align-self: flex-start;
        align-items: flex-start;
    }

    .message-bubble {
        padding: 0.75rem 1rem;
        border-radius: 1rem;
        word-wrap: break-word;
        white-space: pre-wrap;
    }

    .user .message-bubble {
        background: var(--color-primary, #3b82f6);
        color: white;
        border-bottom-right-radius: 0.25rem;
    }

    .assistant .message-bubble {
        background: var(--color-surface, #f3f4f6);
        color: var(--color-text, #1f2937);
        border-bottom-left-radius: 0.25rem;
    }

    .message-bubble.streaming {
        border: 1px solid var(--color-primary, #3b82f6);
    }

    .content {
        margin: 0;
        line-height: 1.5;
    }

    .timestamp {
        font-size: 0.75rem;
        color: var(--color-text-muted, #6b7280);
        margin-top: 0.25rem;
        padding: 0 0.5rem;
    }

    /* Typing indicator animation */
    .typing-indicator {
        display: flex;
        gap: 4px;
        padding: 4px 0;
    }

    .typing-indicator span {
        width: 8px;
        height: 8px;
        background: var(--color-text-muted, #6b7280);
        border-radius: 50%;
        animation: bounce 1.4s infinite ease-in-out both;
    }

    .typing-indicator span:nth-child(1) {
        animation-delay: -0.32s;
    }

    .typing-indicator span:nth-child(2) {
        animation-delay: -0.16s;
    }

    @keyframes bounce {
        0%,
        80%,
        100% {
            transform: scale(0);
        }
        40% {
            transform: scale(1);
        }
    }

    /* Tool results */
    .tool-results {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 0.5rem;
        padding-top: 0.5rem;
        border-top: 1px solid rgba(0, 0, 0, 0.1);
    }

    .tool-result {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.75rem;
        font-weight: 500;
    }

    .tool-result.success {
        background: rgba(34, 197, 94, 0.2);
        color: #16a34a;
    }

    .tool-result.error {
        background: rgba(239, 68, 68, 0.2);
        color: #dc2626;
    }

    .tool-icon {
        font-weight: bold;
    }

    .tool-name {
        font-family: monospace;
    }
</style>
