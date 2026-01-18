<script lang="ts">
	import { page } from '$app/stores';
	import { resolve } from '$app/paths';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { getIsDemoModeExplicit } from '$lib/api/settings';
	import AppContainer from '$lib/components/AppContainer.svelte';
	import NavIcon from '$lib/components/NavIcon.svelte';
	import {
		getNavItems,
		getScanHref,
		isNavItemActive,
		handleDisabledNavClick,
	} from '$lib/navigation/config';

	// Type-safe route type for dynamic paths
	type AppRoute = Parameters<typeof resolve>[0];

	// Explicit demo mode (HBC_DEMO_MODE env var) disables certain features like chat
	let isDemoModeExplicit = $derived(getIsDemoModeExplicit());

	// Get current path reactively
	let currentPath = $derived($page.url.pathname);

	// Scan tab href - use workflow status to determine the best route
	let scanHref = $derived(getScanHref(scanWorkflow.state.status));

	// Navigation items from shared config
	let navItems = $derived(getNavItems(scanHref, isDemoModeExplicit));
</script>

<!-- Mobile only - hidden on tablet/desktop -->
<nav
	class="glass pb-safe fixed bottom-0 left-0 right-0 z-50 border-t border-neutral-700 md:hidden"
	style="view-transition-name: bottom-nav; transform: translateZ(0); -webkit-transform: translateZ(0);"
	aria-label="Main navigation"
>
	<AppContainer class="px-2">
		<ul class="flex h-16 items-center justify-around" role="menubar">
			{#each navItems as item (item.id)}
				{@const active = isNavItemActive(item, currentPath)}
				{@const disabled = item.disabled ?? false}
				<li role="none" class="flex-1">
					{#if disabled}
						<!-- Disabled nav item - shows toast on click explaining why -->
						<button
							type="button"
							role="menuitem"
							aria-disabled="true"
							title={item.disabledTooltip}
							onclick={() => handleDisabledNavClick(item)}
							class="relative flex w-full cursor-not-allowed flex-col items-center justify-center gap-1 rounded-xl px-3 py-2 text-neutral-600"
						>
							<span class="flex h-6 w-6 items-center justify-center">
								<NavIcon icon={item.icon} />
							</span>
							<span class="text-xs font-medium">{item.label}</span>
						</button>
					{:else}
						<a
							href={resolve(item.href as AppRoute)}
							role="menuitem"
							aria-current={active ? 'page' : undefined}
							class="flex flex-col items-center justify-center gap-1 rounded-xl px-3 py-2 transition-all duration-200
							{active
								? 'bg-primary-500/10 text-primary-500'
								: 'text-neutral-400 hover:bg-neutral-700/50 hover:text-neutral-200'}"
						>
							<span class="flex h-6 w-6 items-center justify-center">
								<NavIcon icon={item.icon} />
							</span>
							<span class="text-xs font-medium">{item.label}</span>
						</a>
					{/if}
				</li>
			{/each}
		</ul>
	</AppContainer>
</nav>
