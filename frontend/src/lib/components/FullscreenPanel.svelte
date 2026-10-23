<script lang="ts">
	/**
	 * FullscreenPanel - A full-viewport overlay for expanded content viewing.
	 *
	 * Unlike Modal (centered dialog), this fills the entire screen with
	 * a scrollable content area. Used for log viewers, prompt previews, etc.
	 *
	 * Features:
	 * - Escape key to close
	 * - Header with title, subtitle, and action buttons
	 * - Scrollable content with bottom padding for mobile nav
	 */
	import type { Snippet } from 'svelte';
	import { X } from '@lucide/svelte';
	import { modalDialog } from '$lib/actions/dialog';

	interface Props {
		open: boolean;
		title: string;
		subtitle?: string;
		onclose: () => void;
		/** Icon snippet rendered before the title */
		icon?: Snippet;
		/** Action buttons rendered in the header (right side) */
		headerActions?: Snippet;
		children: Snippet;
	}

	let {
		open = $bindable(),
		title,
		subtitle,
		onclose,
		icon,
		headerActions,
		children,
	}: Props = $props();
	const titleId = $props.id();

	function handleClose() {
		open = false;
		onclose();
	}

	function handleCancel(event: Event) {
		event.preventDefault();
		handleClose();
	}
</script>

{#if open}
	<dialog
		use:modalDialog
		aria-labelledby={titleId}
		class="fixed inset-0 z-modal m-0 flex max-h-none max-w-none flex-col bg-neutral-950 p-0 backdrop:bg-transparent size-full"
		oncancel={handleCancel}
	>
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-neutral-700 bg-neutral-900 p-4">
			<div class="flex items-center gap-3">
				{#if icon}
					{@render icon()}
				{/if}
				<div>
					<h2 id={titleId} class="text-body-lg font-semibold text-neutral-100">{title}</h2>
					{#if subtitle}
						<p class="text-caption text-neutral-500">{subtitle}</p>
					{/if}
				</div>
			</div>
			<div class="flex items-center gap-2">
				{#if headerActions}
					{@render headerActions()}
				{/if}
				<button
					type="button"
					class="btn-icon-touch"
					onclick={handleClose}
					title="Close fullscreen (Escape)"
					aria-label="Close"
				>
					<X size={20} strokeWidth={1.5} />
				</button>
			</div>
		</div>

		<!-- Content -->
		<div class="flex-1 overflow-auto p-4 pb-24">
			{@render children()}
		</div>
	</dialog>
{/if}
