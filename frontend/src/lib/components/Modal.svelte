<script lang="ts">
	import type { Snippet } from 'svelte';
	import { X } from '@lucide/svelte';
	import { modalDialog } from '$lib/actions/dialog';

	interface Props {
		open: boolean;
		title?: string;
		/** Compact mode: smaller width, less padding, no title bar */
		compact?: boolean;
		/** Accessible name when the content supplies its own heading. */
		ariaLabel?: string;
		dismissible?: boolean;
		onclose?: () => void;
		children: Snippet;
		footer?: Snippet;
	}

	let {
		open = $bindable(),
		title = '',
		compact = false,
		ariaLabel = 'Information',
		dismissible = true,
		onclose,
		children,
		footer,
	}: Props = $props();
	const dialogId = $props.id();

	function handleClose() {
		if (!dismissible) return;
		open = false;
		onclose?.();
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			handleClose();
		}
	}

	function handleCancel(event: Event) {
		event.preventDefault();
		handleClose();
	}
</script>

{#if open}
	<dialog
		use:modalDialog
		aria-labelledby={title && !compact ? `${dialogId}-title` : undefined}
		aria-label={title && !compact ? undefined : ariaLabel}
		class="fixed inset-0 z-50 m-0 flex max-h-none max-w-none animate-fade-in items-center justify-center bg-neutral-950/60 p-4 backdrop-blur-sm backdrop:bg-transparent size-full"
		onclick={handleBackdropClick}
		oncancel={handleCancel}
	>
		<div
			class="animate-scale-in overflow-hidden rounded-2xl border border-neutral-700 bg-neutral-800 shadow-xl {compact
				? 'w-full max-w-xs'
				: 'w-full max-w-lg'}"
		>
			{#if title && !compact}
				<div class="flex items-center justify-between border-b border-neutral-700 px-6 py-4">
					<h3 id={`${dialogId}-title`} class="text-h4 font-semibold text-neutral-200">{title}</h3>
					{#if dismissible}
						<button
							type="button"
							class="min-h-touch min-w-touch rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-200"
							onclick={handleClose}
							aria-label="Close"
						>
							<X size={20} />
						</button>
					{/if}
				</div>
			{/if}

			<div class="relative max-h-screen overflow-y-auto {compact ? 'p-4 pr-10' : 'p-6'}">
				{#if compact && dismissible}
					<!-- Simple close button for compact mode -->
					<button
						type="button"
						class="absolute right-2 top-2 min-h-touch min-w-touch rounded-lg p-1.5 text-neutral-500 transition-colors hover:bg-neutral-700 hover:text-neutral-300"
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
	</dialog>
{/if}
