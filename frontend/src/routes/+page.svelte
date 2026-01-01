<script lang="ts">
	import { goto } from "$app/navigation";
	import { auth, getConfig, setDemoMode } from "$lib/api";
	import { authStore } from "$lib/stores/auth.svelte";
	import { showToast, setLoading } from "$lib/stores/ui.svelte";
	import { authLogger as log } from "$lib/utils/logger";
	import { getInitPromise } from "$lib/services/tokenRefresh";
	import Button from "$lib/components/Button.svelte";
	import { onMount } from "svelte";

	let email = $state("");
	let password = $state("");
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
				log.debug("Token found, validating before redirect...");
				const result = await auth.validateToken();
				if (result.valid) {
					log.debug("Token valid, redirecting to /location");
					goto("/location");
					return;
				} else {
					log.debug(
						"Token invalid, expired, or validation failed - clearing auth state",
					);
					// Token is invalid - clear it so user can log in
					authStore.logout();
				}
			}

			// Check if in demo mode and auto-fill credentials
			try {
				const config = await getConfig();
				setDemoMode(config.is_demo_mode);
				if (config.is_demo_mode) {
					email = "demo@example.com";
					password = "demo";
				}
			} catch (error) {
				// If config fetch fails, just continue without auto-fill
				log.debug("Failed to fetch config (demo mode check):", error);
			}
		} finally {
			// Auth check complete, show login form
			isCheckingAuth = false;
		}
	});

	async function handleSubmit(e: Event) {
		e.preventDefault();

		if (!email || !password) {
			showToast("Please enter email and password", "warning");
			return;
		}

		isSubmitting = true;
		setLoading(true, "Signing in...");

		try {
			const response = await auth.login(email, password);
			authStore.setAuthenticatedState(
				response.token,
				new Date(response.expires_at),
			);
			goto("/location");
		} catch (error) {
			log.error("Login failed:", error);
			showToast(
				error instanceof Error
					? error.message
					: "Login failed. Please check your credentials.",
				"error",
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

<div class="flex flex-col items-center justify-center min-h-screen animate-in">
	{#if isCheckingAuth}
		<!-- Loading state during auth check -->
		<div class="flex flex-col items-center gap-4">
			<div
				class="w-12 h-12 border-4 border-primary/30 border-t-primary rounded-full animate-spin"
			></div>
			<p class="text-sm text-neutral-400">Loading...</p>
		</div>
	{:else}
		<!-- Refined logo icon -->
		<div
			class="w-20 h-20 bg-primary-600/20 rounded-2xl flex items-center justify-center mb-10 shadow-lg"
		>
			<svg
				class="w-14 h-14 text-primary-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<path
					d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
				/>
			</svg>
		</div>

		<!-- Typography with improved hierarchy -->
		<h1 class="text-h1 text-neutral-100 mb-2 text-center px-4">
			Welcome back
		</h1>
		<p class="text-body text-neutral-400 mb-10 text-center px-4 max-w-xs">
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
						type={showPassword ? "text" : "password"}
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
						class="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-neutral-500 hover:text-neutral-300 transition-colors rounded-lg hover:bg-neutral-800"
						aria-label={showPassword
							? "Hide password"
							: "Show password"}
					>
						{#if showPassword}
							<!-- Eye off icon -->
							<svg
								class="w-5 h-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path
									d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"
								/>
							</svg>
						{:else}
							<!-- Eye icon -->
							<svg
								class="w-5 h-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path
									d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
								/>
								<path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
							</svg>
						{/if}
					</button>
				</div>
			</div>

			<div class="pt-2">
				<Button
					type="submit"
					variant="primary"
					full
					loading={isSubmitting}
				>
					<span>Sign In</span>
					<svg
						class="w-5 h-5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path d="M13 7l5 5m0 0l-5 5m5-5H6" />
					</svg>
				</Button>
			</div>
		</form>
	{/if}
</div>
