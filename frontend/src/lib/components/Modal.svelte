<script lang="ts">
	import type { Snippet } from 'svelte';
	import { X } from 'lucide-svelte';

	interface Props {
		open: boolean;
		title?: string;
		/** Compact mode: smaller width, less padding, no title bar */
		compact?: boolean;
		onclose?: () => void;
		children: Snippet;
		footer?: Snippet;
	}

	let {
		open = $bindable(),
		title = '',
		compact = false,
		onclose,
		children,
		footer,
	}: Props = $props();

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
		if (open && e.key === 'Escape') {
			handleClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-neutral-950/60 p-4 backdrop-blur-sm"
		onclick={handleBackdropClick}
	>
		<div
			class="animate-scale-in overflow-hidden rounded-2xl border border-neutral-700 bg-neutral-800 shadow-xl {compact
				? 'w-full max-w-xs'
				: 'w-full max-w-lg'}"
		>
			{#if title && !compact}
				<div class="flex items-center justify-between border-b border-neutral-700 px-6 py-4">
					<h3 class="text-lg font-semibold text-neutral-200">{title}</h3>
					<button
						type="button"
						class="min-h-touch min-w-touch rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-200"
						onclick={handleClose}
						aria-label="Close"
					>
						<X size={20} />
					</button>
				</div>
			{/if}

			<div class="relative max-h-screen overflow-y-auto {compact ? 'p-4 pr-10' : 'p-6'}">
				{#if compact}
					<!-- Simple close button for compact mode -->
					<button
						type="button"
						class="absolute right-2 top-2 rounded-lg p-1.5 text-neutral-500 transition-colors hover:bg-neutral-700 hover:text-neutral-300"
						onclick={handleClose}
						aria-label="Close"
					>
						<X size={16} />
					</button>
				{/if}
				{@render children()}
			</div>

			{#if footer && !compact}
				<div
					class="flex items-center justify-end gap-3 border-t border-neutral-700 bg-neutral-800/50 px-6 py-4"
				>
					{@render footer()}
				</div>
			{/if}
		</div>
	</div>
{/if}
