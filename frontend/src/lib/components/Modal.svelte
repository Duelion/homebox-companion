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
		class="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-base-100/60 p-4 backdrop-blur-sm"
		onclick={handleBackdropClick}
	>
		<div
			class="w-full max-w-lg animate-scale-in overflow-hidden rounded-2xl border border-base-content/20 bg-base-300 shadow-xl"
		>
			{#if title}
				<div class="flex items-center justify-between border-b border-base-content/20 px-6 py-4">
					<h3 class="text-lg font-semibold text-base-content">{title}</h3>
					<button
						type="button"
						class="rounded-lg p-2 text-base-content/60 transition-colors hover:bg-base-content/10 hover:text-base-content"
						onclick={handleClose}
						aria-label="Close"
					>
						<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M6 18L18 6M6 6l12 12"
							/>
						</svg>
					</button>
				</div>
			{/if}

			<div class="max-h-screen overflow-y-auto p-6">
				{@render children()}
			</div>

			{#if footer}
				<div
					class="flex items-center justify-end gap-3 border-t border-base-content/20 bg-base-300/50 px-6 py-4"
				>
					{@render footer()}
				</div>
			{/if}
		</div>
	</div>
{/if}
