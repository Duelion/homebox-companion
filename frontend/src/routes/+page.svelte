<script lang="ts">
	import { Eye, EyeOff, ArrowRight, Key } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { auth, getConfig, setDemoMode } from '$lib/api';
	import type { HomeboxOidcStatus } from '$lib/api/settings';
	import { authStore } from '$lib/stores/auth.svelte';
	import { collectionStore } from '$lib/stores/collection.svelte';
	import { showToast, setLoading } from '$lib/stores/ui.svelte';
	import { authLogger as log } from '$lib/utils/logger';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import Button from '$lib/components/Button.svelte';
	import { onMount } from 'svelte';

	let email = $state('');
	let password = $state('');
	let apiKey = $state('');
	let isSubmitting = $state(false);
	let showPassword = $state(false);
	let showApiKeyForm = $state(false);
	let isCheckingAuth = $state(true); // Show loading during auth check
	let homeboxUrl = $state('');
	let homeboxOidc = $state<HomeboxOidcStatus | null>(null);

	let oidcOnly = $derived(
		homeboxOidc?.enabled === true && homeboxOidc?.allow_local === false
	);
	let hybridOidc = $derived(
		homeboxOidc?.enabled === true && homeboxOidc?.allow_local !== false
	);
	let showPasswordForm = $derived(!oidcOnly && !showApiKeyForm);
	let showApiKeySection = $derived(oidcOnly || showApiKeyForm);

	// Redirect if already authenticated, or auto-fill demo credentials
	onMount(async () => {
		try {
			// Wait for auth initialization to complete to avoid race conditions
			// where we check isAuthenticated before initializeAuth clears expired tokens
			await getInitPromise();

			// Check if token exists and validate it before redirecting
			if (authStore.isAuthenticated) {
				log.debug('Token found, validating before redirect...');
				const result = await auth.validateToken();
				if (result.valid) {
					log.debug('Token valid, redirecting to /location');
					goto(resolve('/location'));
					return;
				} else {
					log.debug('Token invalid, expired, or validation failed - clearing auth state');
					// Token is invalid - clear it so user can log in
					authStore.logout();
				}
			}

			// Check if in demo mode and auto-fill credentials
			try {
				const config = await getConfig();
				setDemoMode(config.is_demo_mode, config.demo_mode_explicit);
				homeboxUrl = config.homebox_url;
				homeboxOidc = config.homebox_oidc;
				if (config.is_demo_mode) {
					email = 'demo@example.com';
					password = 'demo';
				}
			} catch (error) {
				// If config fetch fails, just continue without auto-fill
				log.debug('Failed to fetch config (demo mode / OIDC check):', error);
			}
		} finally {
			// Auth check complete, show login form
			isCheckingAuth = false;
		}
	});

	async function completeLogin(response: Awaited<ReturnType<typeof auth.login>>) {
		authStore.setAuthenticatedState(
			response.token,
			response.expires_at ? new Date(response.expires_at) : null,
			response.user_email ?? email,
			response.auth_method
		);
		await collectionStore.fetchGroups();
		goto(resolve('/location'));
	}

	async function handlePasswordSubmit(e: Event) {
		e.preventDefault();

		if (!email || !password) {
			showToast('Please enter email and password', 'warning');
			return;
		}

		isSubmitting = true;
		setLoading(true, 'Signing in...');

		try {
			const response = await auth.login(email, password);
			await completeLogin(response);
		} catch (error) {
			log.error('Login failed:', error);
			showToast(
				error instanceof Error ? error.message : 'Login failed. Please check your credentials.',
				'error'
			);
		} finally {
			isSubmitting = false;
			setLoading(false);
		}
	}

	async function handleApiKeySubmit(e: Event) {
		e.preventDefault();

		const trimmed = apiKey.trim();
		if (!trimmed) {
			showToast('Please enter your Homebox API key', 'warning');
			return;
		}

		isSubmitting = true;
		setLoading(true, 'Connecting...');

		try {
			const response = await auth.loginWithApiKey(trimmed);
			apiKey = '';
			await completeLogin(response);
		} catch (error) {
			log.error('API key login failed:', error);
			showToast(
				error instanceof Error ? error.message : 'Invalid API key. Please check and try again.',
				'error'
			);
		} finally {
			isSubmitting = false;
			setLoading(false);
		}
	}

	function togglePasswordVisibility() {
		showPassword = !showPassword;
	}

	function toggleApiKeyForm() {
		showApiKeyForm = !showApiKeyForm;
	}
</script>

<svelte:head>
	<title>Login - Homebox Companion</title>
</svelte:head>

<div class="animate-in flex flex-col items-center justify-center pb-16 pt-8">
	{#if isCheckingAuth}
		<!-- Loading state during auth check -->
		<div class="flex flex-col items-center gap-4">
			<div
				class="h-12 w-12 animate-spin rounded-full border-4 border-primary-500/30 border-t-primary-500"
			></div>
			<p class="text-sm text-neutral-400">Loading...</p>
		</div>
	{:else}
		<!-- Refined logo icon -->
		<div
			class="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-primary-600/20 shadow-lg"
		>
			<svg
				class="h-14 w-14 text-primary-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
			</svg>
		</div>

		<!-- Typography with improved hierarchy -->
		<h1 class="mb-2 px-4 text-center text-h1 text-neutral-100">Welcome back</h1>
		<p class="mb-6 max-w-xs px-4 text-center text-body text-neutral-400">
			{#if oidcOnly}
				Connect with your Homebox API key to continue
			{:else}
				Sign in to continue to Homebox Companion
			{/if}
		</p>

		{#if oidcOnly && homeboxUrl}
			<div
				class="mb-6 w-full max-w-sm space-y-2 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-4 px-4 text-body-sm text-neutral-300"
			>
				<p class="font-medium text-neutral-200">First-time setup</p>
				<ol class="list-decimal space-y-1 pl-4 text-neutral-400">
					<li>
						Sign in to
						<a
							href="{homeboxUrl}/profile"
							target="_blank"
							rel="noopener noreferrer"
							class="text-primary-400 underline hover:text-primary-300"
						>
							Homebox
						</a>
						with SSO
					</li>
					<li>Open Profile → API Keys and create a named key</li>
					<li>Paste the key below (starts with <code class="text-neutral-300">hb_</code>)</li>
				</ol>
			</div>
		{/if}

		{#if showPasswordForm}
			<form class="w-full max-w-sm space-y-5 px-4" onsubmit={handlePasswordSubmit}>
				<div>
					<label for="email" class="label">Email</label>
					<input
						type="email"
						id="email"
						bind:value={email}
						placeholder="you@example.com"
						required
						autocomplete="email"
						class="input"
					/>
				</div>

				<div>
					<label for="password" class="label">Password</label>
					<div class="relative">
						<input
							type={showPassword ? 'text' : 'password'}
							id="password"
							bind:value={password}
							placeholder="Enter your password"
							required
							autocomplete="current-password"
							class="input pr-12"
						/>
						<button
							type="button"
							onclick={togglePasswordVisibility}
							class="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-neutral-500 transition-colors hover:bg-neutral-800 hover:text-neutral-300"
							aria-label={showPassword ? 'Hide password' : 'Show password'}
						>
							{#if showPassword}
								<!-- Eye off icon -->
								<EyeOff size={20} strokeWidth={1.5} />
							{:else}
								<!-- Eye icon -->
								<Eye size={20} strokeWidth={1.5} />
							{/if}
						</button>
					</div>
				</div>

				<div class="pt-2">
					<Button type="submit" variant="primary" full loading={isSubmitting}>
						<span>Sign In</span>
						<ArrowRight size={20} strokeWidth={2} />
					</Button>
				</div>
			</form>

			{#if hybridOidc}
				<div class="mt-4 w-full max-w-sm px-4">
					<button
						type="button"
						class="w-full py-2 text-body-sm text-neutral-400 transition-colors hover:text-neutral-200"
						onclick={toggleApiKeyForm}
					>
						Connect with API key instead
					</button>
				</div>
			{/if}
		{/if}

		{#if showApiKeySection}
			{#if hybridOidc && showApiKeyForm}
				<div class="mb-4 w-full max-w-sm px-4">
					<button
						type="button"
						class="w-full py-2 text-body-sm text-neutral-400 transition-colors hover:text-neutral-200"
						onclick={toggleApiKeyForm}
					>
						Back to password sign in
					</button>
				</div>
			{/if}

			<form class="w-full max-w-sm space-y-5 px-4" onsubmit={handleApiKeySubmit}>
				<div>
					<label for="api-key" class="label">Homebox API Key</label>
					<input
						type="password"
						id="api-key"
						bind:value={apiKey}
						placeholder="hb_..."
						required
						autocomplete="off"
						class="input font-mono"
					/>
					{#if hybridOidc && homeboxUrl}
						<p class="mt-2 text-caption text-neutral-500">
							Create a key in
							<a
								href="{homeboxUrl}/profile"
								target="_blank"
								rel="noopener noreferrer"
								class="text-primary-400 underline hover:text-primary-300"
							>
								Homebox Profile → API Keys
							</a>
						</p>
					{/if}
				</div>

				<div class="pt-2">
					<Button type="submit" variant="primary" full loading={isSubmitting}>
						<Key size={20} strokeWidth={2} />
						<span>Connect</span>
					</Button>
				</div>
			</form>
		{/if}
	{/if}
</div>
