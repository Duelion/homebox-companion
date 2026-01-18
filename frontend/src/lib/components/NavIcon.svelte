<script lang="ts">
	import type { NavItem } from '$lib/navigation/config';

	interface Props {
		icon: NavItem['icon'];
		/** Size class - use 'sm' for header (h-4 w-4), 'md' for bottom nav (h-6 w-6) */
		size?: 'sm' | 'md';
	}

	let { icon, size = 'md' }: Props = $props();

	let sizeClass = $derived(size === 'sm' ? 'h-4 w-4' : 'h-6 w-6');
</script>

{#if icon === 'scan'}
	<svg class={sizeClass} fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
		<path
			d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"
		/>
		<circle cx="12" cy="12" r="3" />
		<path d="M12 9v-1M12 16v1M9 12H8M16 12h1" />
	</svg>
{:else if icon === 'settings'}
	<svg class={sizeClass} fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
		<circle cx="12" cy="12" r="3" />
		<path
			d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
		/>
	</svg>
{:else if icon === 'chat'}
	<svg class={sizeClass} fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
		<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
	</svg>
{/if}
