<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		open: boolean;
		title?: string;
		onclose?: () => void;
		children: Snippet;
		footer?: Snippet;
	}

	let { open = $bindable(), title = '', onclose, children, footer }: Props = $props();

	function handleClose() {
		open = false;
		onclose?.();
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			handleClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			handleClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
		onclick={handleBackdropClick}
	>
		<div class="w-full max-w-lg bg-surface rounded-2xl border border-border shadow-xl animate-scale-in overflow-hidden">
			{#if title}
				<div class="flex items-center justify-between px-6 py-4 border-b border-border">
					<h3 class="text-lg font-semibold text-text">{title}</h3>
					<button
						type="button"
						class="p-2 rounded-lg text-text-muted hover:text-text hover:bg-surface-elevated transition-colors"
						onclick={handleClose}
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			{/if}

			<div class="p-6 max-h-[70vh] overflow-y-auto">
				{@render children()}
			</div>

			{#if footer}
				<div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-border bg-surface-elevated/50">
					{@render footer()}
				</div>
			{/if}
		</div>
	</div>
{/if}




