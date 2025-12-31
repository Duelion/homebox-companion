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
        background: linear-gradient(
            135deg,
            #4f46e5,
            #6366f1
        ); /* primary gradient */
        color: white;
        border-bottom-right-radius: 0.25rem;
        box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
    }

    .assistant .message-bubble {
        background: #1e1e2e; /* neutral-800 */
        color: #e2e8f0; /* neutral-200 */
        border-bottom-left-radius: 0.25rem;
        border: 1px solid #2a2a3e; /* neutral-700 */
    }

    .message-bubble.streaming {
        border-color: #6366f1; /* primary-500 */
        box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.3);
    }

    .content {
        margin: 0;
        line-height: 1.5;
    }

    .timestamp {
        font-size: 0.75rem;
        color: #64748b; /* neutral-500 */
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
        background: #6366f1; /* primary-500 */
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
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }

    .tool-result {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.25rem 0.5rem;
        border-radius: 0.5rem;
        font-size: 0.75rem;
        font-weight: 500;
    }

    .tool-result.success {
        background: rgba(16, 185, 129, 0.15);
        color: #10b981; /* success-500 */
        border: 1px solid rgba(16, 185, 129, 0.3);
    }

    .tool-result.error {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444; /* error-500 */
        border: 1px solid rgba(239, 68, 68, 0.3);
    }

    .tool-icon {
        font-weight: bold;
    }

    .tool-name {
        font-family: "JetBrains Mono", monospace;
    }
</style>
