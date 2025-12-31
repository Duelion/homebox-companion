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
    class="flex flex-col max-w-[85%] {isUser
        ? 'self-end items-end'
        : 'self-start items-start'}"
>
    <div
        class="py-3 px-4 rounded-2xl whitespace-pre-wrap break-words {isUser
            ? 'bg-gradient-to-br from-primary-600 to-primary-500 text-white rounded-br shadow-[0_2px_8px_rgba(99,102,241,0.3)]'
            : 'bg-neutral-800 text-neutral-200 border border-neutral-700 rounded-bl'} {message.isStreaming
            ? 'border-primary-500 shadow-[0_0_0_1px_rgba(99,102,241,0.3)]'
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
            <div
                class="flex flex-wrap gap-2 mt-2 pt-2 border-t border-white/10"
            >
                {#each message.toolResults as result}
                    <div
                        class="inline-flex items-center gap-1 py-1 px-2 rounded-lg text-xs font-medium {result.success
                            ? 'bg-success-500/15 text-success-500 border border-success-500/30'
                            : 'bg-error-500/15 text-error-500 border border-error-500/30'}"
                    >
                        <span class="font-bold"
                            >{result.success ? "✓" : "✗"}</span
                        >
                        <span class="font-mono">{result.tool}</span>
                    </div>
                {/each}
            </div>
        {/if}
    </div>

    <time class="text-xs text-neutral-500 mt-1 px-2">
        {message.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        })}
    </time>
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
</style>
