<script lang="ts">
	import '../app.css';
	import Toast from '$lib/components/Toast.svelte';
	import { isAuthenticated, logout } from '$lib/stores/auth';
	import { isOnline, appVersion } from '$lib/stores/ui';
	import { getVersion } from '$lib/api';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';

	// Fetch version on mount
	onMount(async () => {
		if (browser) {
			// Check online status
			isOnline.set(navigator.onLine);
			window.addEventListener('online', () => isOnline.set(true));
			window.addEventListener('offline', () => isOnline.set(false));

			// Fetch app version
			try {
				const { version } = await getVersion();
				appVersion.set(version);
			} catch {
				appVersion.set('unknown');
			}
		}
	});

	function handleLogout() {
		logout();
		window.location.href = '/';
	}
</script>

<div class="min-h-screen min-h-dvh flex flex-col bg-background">
	<!-- Header -->
	<header class="sticky top-0 z-40 glass border-b border-border">
		<div class="max-w-lg mx-auto px-4 h-14 grid grid-cols-3 items-center">
			<!-- Left spacer -->
			<div></div>
			
			<!-- Center: Logo and title -->
			<a href="/" class="flex items-center justify-center gap-2 text-text font-semibold overflow-visible">
				<svg class="w-7 h-7 text-primary shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
					<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
					<polyline points="3.27 6.96 12 12.01 20.73 6.96" />
					<line x1="12" y1="22.08" x2="12" y2="12" />
				</svg>
				<span class="whitespace-nowrap">Homebox Companion</span>
			</a>

			<!-- Right: Logout button -->
			<div class="flex justify-end">
				{#if $isAuthenticated}
					<button
						type="button"
						class="btn-icon"
						title="Logout"
						onclick={handleLogout}
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
							<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
							<polyline points="16 17 21 12 16 7" />
							<line x1="21" y1="12" x2="9" y2="12" />
						</svg>
					</button>
				{/if}
			</div>
		</div>
	</header>

	<!-- Main content -->
	<main class="flex-1 max-w-lg mx-auto w-full px-4 py-6">
		<slot />
	</main>

	<!-- Offline banner -->
	{#if !$isOnline}
		<div class="fixed bottom-0 left-0 right-0 bg-warning/20 border-t border-warning/30 px-4 py-3 flex items-center justify-center gap-2 text-yellow-300 text-sm">
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

	<!-- Footer with version -->
	<footer class="text-center py-3 text-text-dim text-xs">
		{#if $appVersion}
			v{$appVersion}
		{/if}
	</footer>

	<!-- Toast notifications -->
	<Toast />
</div>
