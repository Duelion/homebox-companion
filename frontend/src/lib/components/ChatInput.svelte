<script lang="ts">
	/**
	 * ChatInput - Text input for sending chat messages
	 *
	 * Auto-resizing textarea with send button.
	 * Disabled while streaming.
	 */
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
	class="mx-auto flex w-full max-w-2xl flex-col gap-1 border-t border-white/[0.08] bg-neutral-950 px-3 py-1.5"
	onsubmit={(e) => {
		e.preventDefault();
		handleSubmit();
	}}
>
	<div
		class="duration-fast focus-within:border-primary-500 flex items-end gap-2 rounded-xl border border-neutral-700 bg-neutral-900 p-1 transition-all focus-within:shadow-[0_0_0_2px_rgba(99,102,241,0.15)]"
	>
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
			class="max-h-24 flex-1 resize-none rounded-lg border-0 bg-transparent px-3 py-2 text-sm leading-relaxed text-neutral-200 outline-none placeholder:text-neutral-500 disabled:cursor-not-allowed disabled:text-neutral-500"
		></textarea>

		<button
			type="submit"
			disabled={isDisabled}
			aria-label="Send message"
			class="min-h-touch min-w-touch from-primary-500 to-primary-600 duration-fast flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full border-0 bg-gradient-to-br text-white shadow-[0_2px_8px_rgba(99,102,241,0.3)] transition-all hover:scale-105 hover:shadow-[0_4px_12px_rgba(99,102,241,0.4)] active:scale-95 disabled:cursor-not-allowed disabled:bg-neutral-700 disabled:text-neutral-600 disabled:shadow-none"
		>
			{#if chatStore.isStreaming}
				<span class="loading-spinner"></span>
			{:else}
				<svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
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
				class="min-h-touch min-w-touch bg-error-500 duration-fast hover:bg-error-600 flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full border-0 text-white shadow-[0_2px_8px_rgba(239,68,68,0.3)] transition-all hover:scale-105 hover:shadow-[0_4px_12px_rgba(239,68,68,0.4)] active:scale-95"
			>
				<svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
					<rect x="6" y="6" width="12" height="12" rx="2" />
				</svg>
			</button>
		{/if}
	</div>

	<div class="flex items-center justify-between px-1">
		{#if chatStore.isStreaming}
			<p class="text-primary-500 m-0 text-xs">Assistant is typing...</p>
		{:else}
			<p class="m-0 text-xs text-neutral-600">Enter to send, Shift+Enter for new line</p>
		{/if}
		{#if hasMessages && onClearHistory}
			<button
				type="button"
				onclick={onClearHistory}
				aria-label="Clear chat history"
				class="duration-fast hover:bg-error-500/10 hover:text-error-500 cursor-pointer rounded border-0 bg-transparent px-1.5 py-0.5 text-xs text-neutral-500 transition-all active:scale-95"
			>
				Clear
			</button>
		{/if}
	</div>
</form>

<style>
	.loading-spinner {
		@apply h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white;
	}
</style>
