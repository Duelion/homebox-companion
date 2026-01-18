<script lang="ts">
	/**
	 * ChatInput - Text input for sending chat messages
	 *
	 * Auto-resizing textarea with send button.
	 * Disabled while streaming.
	 */
	import { Send, Square } from 'lucide-svelte';
	import { chatStore } from '../stores/chat.svelte';

	interface Props {
		hasMessages?: boolean;
		onClearHistory?: () => void;
	}

	let { hasMessages = false, onClearHistory }: Props = $props();

	let inputValue = $state('');
	let textareaRef: HTMLTextAreaElement | null = $state(null);

	const isDisabled = $derived(chatStore.isStreaming || !inputValue.trim());

	function handleSubmit() {
		if (isDisabled) return;

		chatStore.sendMessage(inputValue.trim());
		inputValue = '';

		// Reset textarea height
		if (textareaRef) {
			textareaRef.style.height = 'auto';
		}
	}

	function handleCancel() {
		chatStore.cancelStreaming();
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			handleSubmit();
		}
	}

	function handleInput() {
		// Auto-resize textarea
		if (textareaRef) {
			textareaRef.style.height = 'auto';
			textareaRef.style.height = Math.min(textareaRef.scrollHeight, 120) + 'px';
		}
	}
</script>

<form
	class="mx-auto flex w-full max-w-2xl flex-col border-t border-white/[0.08] bg-neutral-950 px-3 py-1"
	onsubmit={(e) => {
		e.preventDefault();
		handleSubmit();
	}}
>
	<div
		class="flex items-center gap-1.5 rounded-lg border border-neutral-700 bg-neutral-900 px-1 py-0.5 transition-all duration-fast focus-within:border-primary-500 focus-within:shadow-primary-ring"
	>
		{#if chatStore.isStreaming}
			<div class="flex flex-1 items-center px-2 py-1.5 text-sm text-primary-500">
				<span
					>Assistant is responding<span class="typing-ellipsis" aria-hidden="true"
						><span>.</span><span>.</span><span>.</span></span
					></span
				>
			</div>
		{:else}
			<textarea
				bind:this={textareaRef}
				bind:value={inputValue}
				onkeydown={handleKeydown}
				oninput={handleInput}
				placeholder="Ask about your inventory..."
				rows="1"
				autocomplete="off"
				aria-label="Chat message input"
				class="max-h-20 flex-1 resize-none rounded-md border-0 bg-transparent px-2 py-1.5 text-body leading-relaxed text-neutral-200 outline-none placeholder:text-neutral-500"
			></textarea>
		{/if}

		<button
			type="submit"
			disabled={isDisabled}
			aria-label="Send message"
			class="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full border-0 bg-gradient-to-br from-primary-500 to-primary-600 text-white shadow-primary-glow-sm transition-all duration-fast hover:scale-105 hover:shadow-primary-glow active:scale-95 disabled:cursor-not-allowed disabled:bg-neutral-700 disabled:text-neutral-600 disabled:shadow-none"
		>
			{#if chatStore.isStreaming}
				<span class="loading-spinner"></span>
			{:else}
				<Send size={14} />
			{/if}
		</button>

		{#if chatStore.isStreaming}
			<button
				type="button"
				onclick={handleCancel}
				aria-label="Stop generating"
				class="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full border-0 bg-error-500 text-white shadow-error-glow-sm transition-all duration-fast hover:scale-105 hover:bg-error-600 hover:shadow-error-glow active:scale-95"
			>
				<Square size={12} fill="currentColor" />
			</button>
		{/if}

		{#if hasMessages && onClearHistory && !chatStore.isStreaming}
			<button
				type="button"
				onclick={onClearHistory}
				aria-label="Clear chat history"
				class="cursor-pointer rounded border-0 bg-transparent px-1.5 py-0.5 text-xs text-neutral-500 transition-all duration-fast hover:bg-error-500/10 hover:text-error-500 active:scale-95"
			>
				Clear
			</button>
		{/if}
	</div>
</form>

<style>
	.loading-spinner {
		@apply h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white;
	}

	/* Animated typing ellipsis - classic sequential fade */
	.typing-ellipsis {
		display: inline;
		letter-spacing: 0.05em;
	}

	.typing-ellipsis > span {
		display: inline-block;
		opacity: 0;
		animation: typing-fade 1.4s infinite;
	}

	.typing-ellipsis > span:nth-child(1) {
		animation-delay: 0s;
	}

	.typing-ellipsis > span:nth-child(2) {
		animation-delay: 0.2s;
	}

	.typing-ellipsis > span:nth-child(3) {
		animation-delay: 0.4s;
	}

	@keyframes typing-fade {
		0%,
		20% {
			opacity: 0;
		}
		40% {
			opacity: 1;
		}
		60%,
		100% {
			opacity: 1;
		}
	}
</style>
