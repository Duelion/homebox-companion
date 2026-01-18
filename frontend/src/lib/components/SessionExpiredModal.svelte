<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { auth } from '$lib/api';
	import { authStore } from '$lib/stores/auth.svelte';
	import { resetLocationState } from '$lib/stores/locations.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { authLogger as log } from '$lib/utils/logger';
	import Button from './Button.svelte';

	let email = $state('');
	let password = $state('');
	let isSubmitting = $state(false);
	let errorMessage = $state('');

	// Derive sessionExpired from authStore for reactive template usage
	let sessionExpired = $derived(authStore.sessionExpired);

	async function handleSubmit(e: Event) {
		e.preventDefault();

		if (!email || !password) {
			errorMessage = 'Please enter email and password';
			return;
		}

		isSubmitting = true;
		errorMessage = '';

		try {
			const response = await auth.login(email, password);
			authStore.setAuthenticatedState(response.token, new Date(response.expires_at));
			// Reset form
			email = '';
			password = '';
		} catch (error) {
			log.error('Re-authentication failed:', error);
			errorMessage =
				error instanceof Error ? error.message : 'Login failed. Please check your credentials.';
		} finally {
			isSubmitting = false;
		}
	}

	function handleLogout() {
		scanWorkflow.reset();
		resetLocationState();
		authStore.logout();
		goto(resolve('/'));
	}
</script>

{#if sessionExpired}
	<!-- Non-dismissable modal backdrop -->
	<div
		class="z-overlay animate-fade-in fixed inset-0 flex items-center justify-center bg-neutral-950/70 p-4 backdrop-blur-sm"
	>
		<div
			class="animate-scale-in w-full max-w-sm overflow-hidden rounded-2xl border border-neutral-700 bg-neutral-800 shadow-xl"
		>
			<!-- Header -->
			<div class="bg-warning-500/10 border-b border-neutral-700 px-6 py-4">
				<div class="flex items-center gap-3">
					<div class="bg-warning-500/20 rounded-full p-2">
						<!-- Warning/clock icon for session expired -->
						<svg
							class="text-warning-500 h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="2"
						>
							<circle cx="12" cy="12" r="10" />
							<line x1="12" y1="8" x2="12" y2="12" />
							<line x1="12" y1="16" x2="12.01" y2="16" />
						</svg>
					</div>
					<div>
						<h3 class="text-lg font-semibold text-neutral-200">Session Expired</h3>
						<p class="text-sm text-neutral-400">Please log in again to continue</p>
					</div>
				</div>
			</div>

			<!-- Form -->
			<form class="space-y-4 p-6" onsubmit={handleSubmit}>
				{#if errorMessage}
					<div
						class="border-error-500/20 bg-error-500/10 text-error-500 rounded-lg border p-3 text-sm"
					>
						{errorMessage}
					</div>
				{/if}

				<div>
					<label for="reauth-email" class="label">Email</label>
					<input
						type="email"
						id="reauth-email"
						bind:value={email}
						placeholder="Enter your email"
						required
						disabled={isSubmitting}
						autocomplete="email"
						class="input"
					/>
				</div>

				<div>
					<label for="reauth-password" class="label">Password</label>
					<input
						type="password"
						id="reauth-password"
						bind:value={password}
						placeholder="Enter your password"
						required
						disabled={isSubmitting}
						autocomplete="current-password"
						class="input"
					/>
				</div>

				<div class="flex flex-col gap-2 pt-2">
					<Button type="submit" variant="primary" full loading={isSubmitting}>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="2"
						>
							<rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
							<path d="M7 11V7a5 5 0 0 1 10 0v4" />
						</svg>
						<span>Sign In</span>
					</Button>

					<button
						type="button"
						class="py-2 text-sm text-neutral-400 transition-colors hover:text-neutral-200"
						onclick={handleLogout}
						disabled={isSubmitting}
					>
						Sign out and return to login page
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}
