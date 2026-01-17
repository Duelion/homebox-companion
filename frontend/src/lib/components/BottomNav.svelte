<script lang="ts">
	import { page } from '$app/stores';
	import { resolve } from '$app/paths';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { getIsDemoModeExplicit } from '$lib/api/settings';
	import { showToast } from '$lib/stores/ui.svelte';
	import AppContainer from '$lib/components/AppContainer.svelte';

	/**
	 * Handle click on a disabled nav item - show toast notification
	 */
	function handleDisabledClick(item: NavItem) {
		if (item.id === 'chat') {
			showToast(
				'Chat is disabled in demo mode. Self-host your own instance to use this feature.',
				'warning'
			);
		}
	}

	// Type-safe route type for dynamic paths
	type AppRoute = Parameters<typeof resolve>[0];

	// Explicit demo mode (HBC_DEMO_MODE env var) disables certain features like chat
	let isDemoModeExplicit = $derived(getIsDemoModeExplicit());

	/**
	 * Bottom navigation item configuration.
	 * Extensible design supports up to 5 tabs.
	 */
	interface NavItem {
		id: string;
		label: string;
		href: string;
		icon: 'scan' | 'settings' | 'chat';
		/** Routes that should highlight this nav item as active */
		activeRoutes: string[];
		/** Whether this item is disabled */
		disabled?: boolean;
		/** Tooltip shown on hover when disabled */
		disabledTooltip?: string;
	}

	// Get current path reactively
	let currentPath = $derived($page.url.pathname);

	// Scan tab href - use workflow status to determine the best route
	let scanHref = $derived.by(() => {
		const status = scanWorkflow.state.status;
		switch (status) {
			case 'reviewing':
				return '/review';
			case 'confirming':
				return '/summary';
			case 'capturing':
			case 'analyzing':
				return '/capture';
			default:
				return '/location';
		}
	});

	// Navigation items - easily extendable for future tabs (max 5 recommended)
	let navItems = $derived<NavItem[]>([
		{
			id: 'chat',
			label: 'Chat',
			href: '/chat',
			icon: 'chat',
			activeRoutes: ['/chat'],
			disabled: isDemoModeExplicit,
			disabledTooltip: 'Chat is disabled in demo mode',
		},
		{
			id: 'scan',
			label: 'Scan',
			href: scanHref,
			icon: 'scan',
			activeRoutes: ['/location', '/capture', '/review', '/summary', '/success'],
		},
		{
			id: 'settings',
			label: 'Settings',
			href: '/settings',
			icon: 'settings',
			activeRoutes: ['/settings'],
		},
	]);

	// Check if a nav item should be highlighted as active
	function isActive(item: NavItem, currentPath: string): boolean {
		return item.activeRoutes.some((route) => currentPath.startsWith(route));
	}
</script>

<!-- Reusable icon snippet to avoid duplication between enabled/disabled states -->
{#snippet navIcon(icon: NavItem['icon'])}
	{#if icon === 'scan'}
		<svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
			<path
				d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"
			/>
			<circle cx="12" cy="12" r="3" />
			<path d="M12 9v-1M12 16v1M9 12H8M16 12h1" />
		</svg>
	{:else if icon === 'settings'}
		<svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
			<circle cx="12" cy="12" r="3" />
			<path
				d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
			/>
		</svg>
	{:else if icon === 'chat'}
		<svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
			<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
		</svg>
	{/if}
{/snippet}

<!-- view-transition-name excludes this from the root page transition, preventing jitter -->
<nav
	class="glass pb-safe fixed bottom-0 left-0 right-0 z-50 border-t border-neutral-700"
	style="view-transition-name: bottom-nav; transform: translateZ(0); -webkit-transform: translateZ(0);"
	aria-label="Main navigation"
>
	<AppContainer class="px-2">
		<ul class="flex h-16 items-center justify-around" role="menubar">
			{#each navItems as item (item.id)}
				{@const active = isActive(item, currentPath)}
				{@const disabled = item.disabled ?? false}
				<li role="none" class="flex-1">
					{#if disabled}
						<!-- Disabled nav item - shows toast on click explaining why -->
						<button
							type="button"
							role="menuitem"
							aria-disabled="true"
							title={item.disabledTooltip}
							onclick={() => handleDisabledClick(item)}
							class="relative flex w-full cursor-not-allowed flex-col items-center justify-center gap-1 rounded-xl px-3 py-2 text-neutral-600"
						>
							<span class="flex h-6 w-6 items-center justify-center">
								{@render navIcon(item.icon)}
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
								{@render navIcon(item.icon)}
							</span>
							<span class="text-xs font-medium">{item.label}</span>
						</a>
					{/if}
				</li>
			{/each}
		</ul>
	</AppContainer>
</nav>
