<script lang="ts">
	import { Eye, EyeOff, ArrowRight } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { auth, getConfig, setDemoMode } from '$lib/api';
	import { authStore } from '$lib/stores/auth.svelte';
	import { showToast, setLoading } from '$lib/stores/ui.svelte';
	import { authLogger as log } from '$lib/utils/logger';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import Button from '$lib/components/Button.svelte';
	import { onMount } from 'svelte';

	let email = $state('');
	let password = $state('');
	let isSubmitting = $state(false);
	let showPassword = $state(false);
	let isCheckingAuth = $state(true); // Show loading during auth check

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
				if (config.is_demo_mode) {
					email = 'demo@example.com';
					password = 'demo';
				}
			} catch (error) {
				// If config fetch fails, just continue without auto-fill
				log.debug('Failed to fetch config (demo mode check):', error);
			}
		} finally {
			// Auth check complete, show login form
			isCheckingAuth = false;
		}
	});

	async function handleSubmit(e: Event) {
		e.preventDefault();

		if (!email || !password) {
			showToast('Please enter email and password', 'warning');
			return;
		}

		isSubmitting = true;
		setLoading(true, 'Signing in...');

		try {
			const response = await auth.login(email, password);
			authStore.setAuthenticatedState(response.token, new Date(response.expires_at), email);
			goto(resolve('/location'));
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

	function togglePasswordVisibility() {
		showPassword = !showPassword;
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
			Sign in to continue to Homebox Companion
		</p>

		<form class="w-full max-w-sm space-y-5 px-4" onsubmit={handleSubmit}>
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
	{/if}
</div>
