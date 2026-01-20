<script lang="ts">
	import type { NavItem } from '$lib/navigation/config';
	import { ScanLine, Settings, MessageSquare } from 'lucide-svelte';

	interface Props {
		icon: NavItem['icon'];
		/** Size class - use 'sm' for header (h-4 w-4), 'md' for bottom nav (h-6 w-6) */
		size?: 'sm' | 'md';
	}

	let { icon, size = 'md' }: Props = $props();

	let iconSize = $derived(size === 'sm' ? 16 : 24);
</script>

{#if icon === 'scan'}
	<ScanLine size={iconSize} strokeWidth={1.75} />
{:else if icon === 'settings'}
	<Settings size={iconSize} strokeWidth={1.75} />
{:else if icon === 'chat'}
	<MessageSquare size={iconSize} strokeWidth={1.75} />
{/if}
