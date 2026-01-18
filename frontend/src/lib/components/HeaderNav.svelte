<script lang="ts">
	import { page } from '$app/stores';
	import { resolve } from '$app/paths';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { getIsDemoModeExplicit } from '$lib/api/settings';
	import NavIcon from '$lib/components/NavIcon.svelte';
	import {
		getNavItems,
		getScanHref,
		isNavItemActive,
		handleDisabledNavClick,
	} from '$lib/navigation/config';

	// Type-safe route type for dynamic paths
	type AppRoute = Parameters<typeof resolve>[0];

	// Get current path reactively
	let currentPath = $derived($page.url.pathname);

	// Scan tab href - use workflow status to determine the best route
	let scanHref = $derived(getScanHref(scanWorkflow.state.status));

	// Demo mode state
	let isDemoModeExplicit = $derived(getIsDemoModeExplicit());

	// Navigation items from shared config
	let navItems = $derived(getNavItems(scanHref, isDemoModeExplicit));
</script>

<!-- Desktop/Tablet header navigation - icons with labels -->
<nav class="flex items-center gap-1" aria-label="Main navigation">
	{#each navItems as item (item.id)}
		{@const active = isNavItemActive(item, currentPath)}
		{@const disabled = item.disabled ?? false}
		{#if disabled}
			<button
				type="button"
				aria-disabled="true"
				title={item.disabledTooltip}
				onclick={() => handleDisabledNavClick(item)}
				class="flex cursor-not-allowed items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-neutral-600"
			>
				<NavIcon icon={item.icon} size="sm" />
				<span>{item.label}</span>
			</button>
		{:else}
			<a
				href={resolve(item.href as AppRoute)}
				aria-current={active ? 'page' : undefined}
				class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-all duration-200
					{active
					? 'bg-primary-500/10 text-primary-500'
					: 'text-neutral-400 hover:bg-neutral-700/50 hover:text-neutral-200'}"
			>
				<NavIcon icon={item.icon} size="sm" />
				<span>{item.label}</span>
			</a>
		{/if}
	{/each}
</nav>
