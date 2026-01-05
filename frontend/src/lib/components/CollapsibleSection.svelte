<script lang="ts">
	/**
	 * CollapsibleSection - A reusable expandable panel with toggle button.
	 *
	 * Features:
	 * - Toggle button with rotating chevron
	 * - Loading state with spinner
	 * - Customizable button text and icon
	 * - Slot for expanded content
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		/** Whether the section is expanded */
		expanded: boolean;
		/** Whether content is loading */
		loading?: boolean;
		/** Button label text */
		label: string;
		/** Loading label text (defaults to "Loading...") */
		loadingLabel?: string;
		/** Icon snippet rendered before the label */
		icon?: Snippet;
		/** Callback when toggle button is clicked */
		ontoggle: () => void;
		/** Content to show when expanded */
		children: Snippet;
	}

	let {
		expanded,
		loading = false,
		label,
		loadingLabel = 'Loading...',
		icon,
		ontoggle,
		children,
	}: Props = $props();
</script>

<button
	type="button"
	class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
	onclick={ontoggle}
	disabled={loading}
>
	{#if loading}
		<div
			class="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
		></div>
		<span>{loadingLabel}</span>
	{:else}
		{#if icon}
			{@render icon()}
		{/if}
		<span>{label}</span>
		<svg
			class="ml-auto h-4 w-4 transition-transform {expanded ? 'rotate-180' : ''}"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
		>
			<polyline points="6 9 12 15 18 9" />
		</svg>
	{/if}
</button>

{#if expanded}
	{@render children()}
{/if}


