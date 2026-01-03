<script lang="ts">
	import type { Snippet } from 'svelte';
	import '../app.css';
	import Toast from '$lib/components/Toast.svelte';
	import SessionExpiredModal from '$lib/components/SessionExpiredModal.svelte';
	import BottomNav from '$lib/components/BottomNav.svelte';
	import AppContainer from '$lib/components/AppContainer.svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { uiStore } from '$lib/stores/ui.svelte';
	import { getVersion, getConfig } from '$lib/api';
	import { setLogLevel } from '$lib/utils/logger';
	import { initializeAuth } from '$lib/services/tokenRefresh';
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { afterNavigate, onNavigate } from '$app/navigation';
	import { resolve } from '$app/paths';

	let { children }: { children: Snippet } = $props();

	// Derive reactive values from stores for template usage
	let isAuthenticated = $derived(authStore.isAuthenticated);
	let isOnline = $derived(uiStore.isOnline);
	let appVersion = $derived(uiStore.appVersion);
	let latestVersion = $derived(uiStore.latestVersion);
	let updateDismissed = $derived(uiStore.updateDismissed);

	function dismissUpdate() {
		uiStore.setUpdateDismissed(true);
	}

	// Event handlers (stable references for cleanup)
	function handleOnline() {
		uiStore.setOnline(true);
	}

	function handleOffline() {
		uiStore.setOnline(false);
	}

	// Scroll to top after each navigation
	// Note: afterNavigate is automatically cleaned up by SvelteKit when the component unmounts
	afterNavigate(() => {
		if (browser) {
			window.scrollTo({ top: 0, behavior: 'instant' });
		}
	});

	// Global page transitions (progressive enhancement)
	// Uses the native View Transitions API when available.
	onNavigate((navigation) => {
		if (!browser) return;
		const doc = document as Document & {
			startViewTransition?: (cb: () => void | Promise<void>) => unknown;
		};
		// IMPORTANT: bind to `document` — some browsers throw if the method is called unbound
		// (e.g. "called on an object that does not implement interface Document").
		const startViewTransition = doc.startViewTransition?.bind(doc);
		if (!startViewTransition) return;

		// Wrap the navigation in a view transition.
		// SvelteKit will wait for the returned promise before completing the navigation.
		return new Promise<void>((resolve) => {
			startViewTransition(async () => {
				resolve();
				await navigation.complete;
			});
		});
	});

	// Fetch version on mount and register event listeners
	onMount(async () => {
		if (browser) {
			// Disable per-page "animate-in" when View Transitions are supported
			// (prevents double-animations on modern browsers; falls back cleanly elsewhere)
			if ('startViewTransition' in document) {
				document.documentElement.classList.add('vt-enabled');
			}

			// Initialize auth (check token, refresh if needed)
			await initializeAuth();

			// Check online status and register listeners
			uiStore.setOnline(navigator.onLine);
			window.addEventListener('online', handleOnline);
			window.addEventListener('offline', handleOffline);

			// Fetch config and sync log level early (before any logs are generated)
			try {
				const config = await getConfig();
				setLogLevel(config.log_level);
			} catch {
				// Config fetch failed - keep default INFO level
			}

			// Fetch app version and check for updates
			try {
				const versionInfo = await getVersion();
				uiStore.setAppVersion(versionInfo.version);
				if (versionInfo.update_available && versionInfo.latest_version) {
					uiStore.setLatestVersion(versionInfo.latest_version);
				}
			} catch {
				uiStore.setAppVersion('unknown');
			}
		}
	});

	// Cleanup window event listeners on destroy
	onDestroy(() => {
		if (browser) {
			window.removeEventListener('online', handleOnline);
			window.removeEventListener('offline', handleOffline);
		}
	});
</script>

<div class="flex min-h-dvh min-h-screen flex-col bg-neutral-950">
	<!-- Header with safe area background - fixed to ensure consistent z-index with pull-to-refresh -->
	<!-- view-transition-name: header excludes this element from the root page transition, preventing jitter -->
	<div
		class="glass fixed left-0 right-0 top-0 z-40 border-b border-neutral-700"
		style="view-transition-name: header;"
	>
		<div class="pt-safe">
			<AppContainer class="flex h-14 items-center justify-center px-4">
				<!-- Center: Logo and title -->
				<a
					href={resolve(isAuthenticated ? '/location' : '/')}
					class="flex items-center justify-center gap-2 overflow-visible font-semibold text-neutral-200"
				>
					<svg
						class="h-7 w-7 shrink-0 text-primary"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path
							d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"
						/>
						<polyline points="3.27 6.96 12 12.01 20.73 6.96" />
						<line x1="12" y1="22.08" x2="12" y2="12" />
					</svg>
					<span class="whitespace-nowrap text-lg">Homebox Companion</span>
				</a>
			</AppContainer>
		</div>
	</div>

	<!-- Spacer for fixed header -->
	<div class="pt-safe h-14 shrink-0"></div>

	<!-- Update available banner - fixed overlay just below header -->
	{#if latestVersion && !updateDismissed}
		<div
			class="fixed left-1/2 top-[calc(3.5rem+env(safe-area-inset-top)+0.5rem)] z-30 flex -translate-x-1/2 items-center justify-center gap-3 rounded-full border border-amber-500/40 bg-amber-900/90 px-4 py-2 text-sm text-amber-300 shadow-lg backdrop-blur-sm"
		>
			<svg
				class="h-4 w-4 shrink-0"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="2"
			>
				<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
				<polyline points="7 10 12 15 17 10" />
				<line x1="12" y1="15" x2="12" y2="3" />
			</svg>
			<span>
				Update available: <strong class="text-amber-200">v{latestVersion}</strong>
			</span>
			<a
				href="https://github.com/Duelion/homebox-companion/releases/latest"
				target="_blank"
				rel="noopener noreferrer"
				class="underline transition-colors hover:text-amber-100"
			>
				View release
			</a>
			<button
				type="button"
				class="ml-1 rounded-full p-1 transition-colors hover:bg-amber-500/30"
				title="Dismiss"
				onclick={dismissUpdate}
			>
				<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
					<line x1="18" y1="6" x2="6" y2="18" />
					<line x1="6" y1="6" x2="18" y2="18" />
				</svg>
			</button>
		</div>
	{/if}

	<!-- Main content - add bottom padding when nav is visible -->
	<main class="flex-1">
		<AppContainer class="px-4 py-6 {isAuthenticated ? 'pb-24' : ''}">
			{@render children()}
		</AppContainer>
	</main>

	<!-- Offline banner - positioned above bottom nav when authenticated -->
	{#if !isOnline}
		<div
			class="fixed left-0 right-0 z-40 flex items-center justify-center gap-2 border-t border-warning/30 bg-warning/20 px-4 py-3 text-sm text-yellow-300 {isAuthenticated
				? 'bottom-nav-offset'
				: 'bottom-0'}"
		>
			<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<line x1="1" y1="1" x2="23" y2="23" />
				<path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
				<path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
				<path d="M10.71 5.05A16 16 0 0 1 22.58 9" />
				<path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
				<path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
				<line x1="12" y1="20" x2="12.01" y2="20" />
			</svg>
			<span>You're offline. Some features may not work.</span>
		</div>
	{/if}

	<!-- Footer with version - only shown on login page (not authenticated) -->
	{#if !isAuthenticated}
		<footer
			class="sticky bottom-0 mt-auto flex items-center justify-center gap-3 bg-neutral-950 py-3 text-center text-xs text-neutral-500"
		>
			{#if appVersion}
				<span>v{appVersion}</span>
			{/if}
			{#if latestVersion}
				<a
					href="https://github.com/Duelion/homebox-companion/releases/latest"
					target="_blank"
					rel="noopener noreferrer"
					class="inline-flex items-center gap-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-300 transition-colors hover:bg-amber-500/30"
					title="Click to view release"
				>
					<svg
						class="h-3 w-3"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
						<polyline points="7 10 12 15 17 10" />
						<line x1="12" y1="15" x2="12" y2="3" />
					</svg>
					<span>v{latestVersion}</span>
				</a>
			{/if}
			<a
				href="https://github.com/Duelion/homebox-companion"
				target="_blank"
				rel="noopener noreferrer"
				class="inline-flex items-center gap-1 transition-colors hover:text-neutral-400"
				title="Star on GitHub"
			>
				<svg class="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 16 16">
					<path
						d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"
					/>
				</svg>
				<span>Star</span>
				<svg class="h-3 w-3" fill="currentColor" viewBox="0 0 16 16">
					<path
						d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"
					/>
				</svg>
			</a>
		</footer>
	{/if}

	<!-- Bottom Navigation - only when authenticated -->
	{#if isAuthenticated}
		<BottomNav />
	{/if}

	<!-- Toast notifications -->
	<Toast />

	<!-- Session expired re-auth modal -->
	<SessionExpiredModal />
</div>
