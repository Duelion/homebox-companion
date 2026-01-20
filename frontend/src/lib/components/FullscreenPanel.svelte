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
	import { X } from 'lucide-svelte';

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

	function handleClose() {
		open = false;
		onclose();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (open && e.key === 'Escape') {
			handleClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<div class="fixed inset-0 z-modal flex flex-col bg-neutral-950">
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-neutral-700 bg-neutral-900 p-4">
			<div class="flex items-center gap-3">
				{#if icon}
					{@render icon()}
				{/if}
				<div>
					<h2 class="text-body-lg font-semibold text-neutral-100">{title}</h2>
					{#if subtitle}
						<p class="text-xs text-neutral-500">{subtitle}</p>
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
	</div>
{/if}
