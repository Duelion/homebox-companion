<script lang="ts">
    /**
     * ChatMessage - Displays a single chat message bubble
     *
     * User messages are right-aligned with primary color.
     * Assistant messages are left-aligned with surface color.
     */
    import type { ChatMessage as ChatMessageType } from "../stores/chat.svelte";
    import { renderMarkdown } from "../markdown";

    interface Props {
        message: ChatMessageType;
    }

    let { message }: Props = $props();

    const isUser = $derived(message.role === "user");
    const hasToolResults = $derived(
        message.toolResults && message.toolResults.length > 0,
    );

    // Copy button state
    let copySuccess = $state(false);

    async function handleCopy() {
        if (!message.content) return;
        try {
            await navigator.clipboard.writeText(message.content);
            copySuccess = true;
            setTimeout(() => (copySuccess = false), 2000);
        } catch (e) {
            console.error("Copy failed:", e);
        }
    }

    // Memoized markdown rendering with GFM support and sanitization
    const renderedContent = $derived.by(() => {
        if (isUser || !message.content) return "";
        try {
            return renderMarkdown(message.content);
        } catch (e) {
            console.error("Markdown render failed:", e);
            return message.content; // fallback to raw text
        }
    });
</script>

<div
    class="flex flex-col max-w-[85%] group {isUser
        ? 'self-end items-end'
        : 'self-start items-start'}"
>
    <div class="relative">
        <div
            class="py-2.5 px-3.5 rounded-2xl break-words {isUser
                ? 'bg-gradient-to-br from-primary-600 to-primary-500 text-white rounded-br shadow-[0_2px_8px_rgba(99,102,241,0.3)]'
                : 'bg-neutral-800/80 backdrop-blur-sm text-neutral-200 border border-neutral-700/50 rounded-bl'} {message.isStreaming
                ? 'streaming-glow'
                : ''}"
        >
            {#if message.content}
                {#if isUser}
                    <p class="m-0 leading-relaxed">{message.content}</p>
                {:else}
                    <div class="markdown-content">{@html renderedContent}</div>
                {/if}
            {/if}

            {#if message.isStreaming && !message.content}
                <div class="flex gap-1 py-1">
                    <span class="typing-dot"></span>
                    <span class="typing-dot animation-delay-160"></span>
                    <span class="typing-dot animation-delay-320"></span>
                </div>
            {/if}

            {#if hasToolResults}
                <details
                    class="tool-accordion group/tools mt-2 pt-2 border-t border-white/10"
                >
                    <summary
                        class="flex items-center gap-1.5 cursor-pointer text-xs text-neutral-400 hover:text-neutral-300 select-none"
                    >
                        <span
                            class="transform transition-transform group-open/tools:rotate-90"
                            >›</span
                        >
                        Used {message.toolResults?.length ?? 0} tool{(message
                            .toolResults?.length ?? 0) > 1
                            ? "s"
                            : ""}
                    </summary>
                    <div class="flex flex-wrap gap-1.5 mt-2">
                        {#each message.toolResults as result}
                            <div
                                class="inline-flex items-center gap-1 py-1 px-2 rounded-lg text-xs font-medium {result.isExecuting
                                    ? 'bg-primary-500/15 text-primary-500 border border-primary-500/30'
                                    : result.success
                                      ? 'bg-success-500/15 text-success-500 border border-success-500/30'
                                      : 'bg-error-500/15 text-error-500 border border-error-500/30'}"
                            >
                                {#if result.isExecuting}
                                    <span class="tool-spinner"></span>
                                {:else}
                                    <span class="font-bold"
                                        >{result.success ? "✓" : "✗"}</span
                                    >
                                {/if}
                                <span class="font-mono">{result.tool}</span>
                            </div>
                        {/each}
                    </div>
                </details>
            {/if}
        </div>

        <!-- Copy button (appears on hover for assistant messages) -->
        {#if !isUser && message.content && !message.isStreaming}
            <button
                class="copy-btn absolute -top-1 -right-1 p-1.5 rounded-md bg-neutral-700/80 hover:bg-neutral-600 text-neutral-400 hover:text-neutral-200 transition-all opacity-0 group-hover:opacity-100 backdrop-blur-sm"
                onclick={handleCopy}
                aria-label="Copy message"
            >
                {#if copySuccess}
                    <svg
                        class="w-3.5 h-3.5 text-success-500"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                    >
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                {:else}
                    <svg
                        class="w-3.5 h-3.5"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                    >
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"
                        ></rect>
                        <path
                            d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
                        ></path>
                    </svg>
                {/if}
            </button>
        {/if}
    </div>

    <div class="flex items-center gap-2 mt-1 px-2">
        <time class="text-xs text-neutral-500">
            {message.timestamp.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
            })}
        </time>
        {#if !isUser && message.tokenUsage}
            <span class="text-xs text-neutral-500">
                ▶ {message.tokenUsage.total} tokens
            </span>
        {/if}
    </div>
</div>

<style>
    /* Markdown content styling */
    .markdown-content {
        margin: 0;
        line-height: 1.5;
    }

    .markdown-content :global(ul),
    .markdown-content :global(ol) {
        margin: 0.5rem 0;
        padding-left: 1.5rem;
    }

    .markdown-content :global(li) {
        margin: 0.25rem 0;
    }

    .markdown-content :global(p) {
        margin: 0.5rem 0;
    }

    .markdown-content :global(p:first-child) {
        margin-top: 0;
    }

    .markdown-content :global(p:last-child) {
        margin-bottom: 0;
    }

    .markdown-content :global(*:last-child) {
        margin-bottom: 0;
    }

    .markdown-content :global(strong) {
        font-weight: 600;
        @apply text-neutral-100;
    }

    .markdown-content :global(em) {
        font-style: italic;
    }

    .markdown-content :global(code) {
        @apply font-mono bg-primary-500/10 text-[0.875em] px-1.5 py-0.5 rounded;
    }

    .markdown-content :global(pre) {
        @apply bg-black/30 p-3 rounded-lg overflow-x-auto my-2;
    }

    .markdown-content :global(pre code) {
        @apply bg-transparent p-0;
    }

    .markdown-content :global(h1),
    .markdown-content :global(h2),
    .markdown-content :global(h3) {
        @apply font-semibold text-neutral-100;
        margin: 0.75rem 0 0.5rem;
    }

    .markdown-content :global(h1) {
        @apply text-h3;
    }

    .markdown-content :global(h2) {
        @apply text-h4;
    }

    .markdown-content :global(h3) {
        @apply text-body;
    }

    /* GFM Tables */
    .markdown-content :global(table) {
        @apply w-full border-collapse my-3;
    }

    .markdown-content :global(th),
    .markdown-content :global(td) {
        @apply border border-neutral-600 px-3 py-2 text-left;
    }

    .markdown-content :global(th) {
        @apply bg-neutral-700/50 font-semibold text-neutral-100;
    }

    .markdown-content :global(tr:nth-child(even)) {
        @apply bg-neutral-800/30;
    }

    /* GFM Task Lists */
    .markdown-content :global(input[type="checkbox"]) {
        @apply mr-2 accent-primary-500;
    }

    .markdown-content :global(li:has(input[type="checkbox"])) {
        list-style: none;
        margin-left: -1.25rem;
    }

    /* Links */
    .markdown-content :global(a) {
        @apply text-primary-400 hover:text-primary-300 underline transition-colors;
    }

    /* Blockquotes */
    .markdown-content :global(blockquote) {
        @apply border-l-4 border-primary-500/50 pl-4 my-3 italic text-neutral-400;
    }

    /* Horizontal Rule */
    .markdown-content :global(hr) {
        @apply border-neutral-600 my-4;
    }

    /* Strikethrough */
    .markdown-content :global(del) {
        @apply text-neutral-500;
    }

    /* Typing indicator animation */
    .typing-dot {
        @apply w-2 h-2 bg-primary-500 rounded-full;
        animation: bounce 1.4s infinite ease-in-out both;
    }

    .animation-delay-160 {
        animation-delay: -0.16s;
    }

    .animation-delay-320 {
        animation-delay: -0.32s;
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

    /* Tool execution spinner */
    .tool-spinner {
        @apply w-3 h-3 border-2 border-primary-500 border-t-transparent rounded-full inline-block;
        animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
        0% {
            transform: rotate(0deg);
        }
        100% {
            transform: rotate(360deg);
        }
    }

    /* Streaming glow animation */
    .streaming-glow {
        @apply border-primary-500;
        animation: pulse-glow 2s ease-in-out infinite;
    }

    @keyframes pulse-glow {
        0%,
        100% {
            box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.3);
        }
        50% {
            box-shadow: 0 0 12px 2px rgba(99, 102, 241, 0.4);
        }
    }

    /* Tool accordion */
    .tool-accordion summary::-webkit-details-marker {
        display: none;
    }

    .tool-accordion summary {
        list-style: none;
    }
</style>
