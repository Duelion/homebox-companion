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
		class="animate-fade-in fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/60 p-4 backdrop-blur-sm"
		onclick={handleBackdropClick}
	>
		<div
			class="animate-scale-in w-full max-w-lg overflow-hidden rounded-2xl border border-neutral-700 bg-neutral-800 shadow-xl"
		>
			{#if title}
				<div class="flex items-center justify-between border-b border-neutral-700 px-6 py-4">
					<h3 class="text-lg font-semibold text-neutral-200">{title}</h3>
					<button
						type="button"
						class="min-h-touch min-w-touch rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-200"
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
					class="flex items-center justify-end gap-3 border-t border-neutral-700 bg-neutral-800/50 px-6 py-4"
				>
					{@render footer()}
				</div>
			{/if}
		</div>
	</div>
{/if}
