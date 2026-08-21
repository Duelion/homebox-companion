<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { CircleAlert, Lock, Key } from 'lucide-svelte';
	import { auth, getConfig } from '$lib/api';
	import { authStore } from '$lib/stores/auth.svelte';
	import { showToast } from '$lib/stores/ui.svelte';
	import { resetLocationState } from '$lib/stores/locations.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { authLogger as log } from '$lib/utils/logger';
	import Button from './Button.svelte';
	import Modal from './Modal.svelte';
	import { onMount } from 'svelte';

	let email = $state('');
	let password = $state('');
	let apiKey = $state('');
	let homeboxUrl = $state('');
	let isSubmitting = $state(false);
	let errorMessage = $state('');

	// Derive sessionExpired from authStore for reactive template usage
	let sessionExpired = $derived(authStore.sessionExpired);
	let useApiKeyReauth = $derived(authStore.authMethod === 'api_key');

	onMount(async () => {
		try {
			const config = await getConfig();
			homeboxUrl = config.homebox_url;
		} catch (error) {
			log.debug('Failed to fetch config for re-auth modal:', error);
		}
	});

	async function handlePasswordSubmit(e: Event) {
		e.preventDefault();

		if (!email || !password) {
			errorMessage = 'Please enter email and password';
			return;
		}

		isSubmitting = true;
		errorMessage = '';

		try {
			const response = await auth.login(email, password);
			authStore.setAuthenticatedState(
				response.token,
				response.expires_at ? new Date(response.expires_at) : null,
				response.user_email ?? email,
				response.auth_method
			);
			// Reset form
			email = '';
			password = '';
			// Confirm session restoration to the user
			showToast('Session restored — you can continue where you left off', 'success');
			log.info('Re-authentication successful, session restored');
		} catch (error) {
			log.error('Re-authentication failed:', error);
			errorMessage =
				error instanceof Error ? error.message : 'Login failed. Please check your credentials.';
		} finally {
			isSubmitting = false;
		}
	}

	async function handleApiKeySubmit(e: Event) {
		e.preventDefault();

		const trimmed = apiKey.trim();
		if (!trimmed) {
			errorMessage = 'Please enter your Homebox API key';
			return;
		}

		isSubmitting = true;
		errorMessage = '';

		try {
			const response = await auth.loginWithApiKey(trimmed);
			authStore.setAuthenticatedState(
				response.token,
				null,
				response.user_email ?? undefined,
				'api_key'
			);
			// Reset form
			apiKey = '';
			// Confirm session restoration to the user
			showToast('Session restored — you can continue where you left off', 'success');
			log.info('API key re-authentication successful');
		} catch (error) {
			log.error('API key re-authentication failed:', error);
			errorMessage =
				error instanceof Error ? error.message : 'Invalid API key. Please check and try again.';
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

	// Prevent closing the modal (session expired is non-dismissable)
	function preventClose() {
		// Do nothing - modal should not be closable
	}
</script>

<Modal open={sessionExpired} onclose={preventClose}>
	<!-- Header -->
	<div class="-mx-6 -mt-6 mb-6 border-b border-neutral-700 bg-warning-500/10 px-6 py-4">
		<div class="flex items-center gap-3">
			<div class="rounded-full bg-warning-500/20 p-2">
				<CircleAlert class="text-warning-500" size={20} />
			</div>
			<div>
				<h3 class="text-lg font-semibold text-neutral-200">Session Expired</h3>
				<p class="text-sm text-neutral-400">
					{#if useApiKeyReauth}
						Enter your Homebox API key to continue
					{:else}
						Please log in again to continue
					{/if}
				</p>
			</div>
		</div>
	</div>

	{#if useApiKeyReauth}
		<!-- Form -->
		<form class="space-y-4" onsubmit={handleApiKeySubmit}>
			{#if errorMessage}
				<div class="rounded-lg border border-error-500/20 bg-error-500/10 p-3 text-sm text-error-500">
					{errorMessage}
				</div>
			{/if}

			<div>
				<label for="reauth-api-key" class="label">Homebox API Key</label>
				<input
					type="password"
					id="reauth-api-key"
					bind:value={apiKey}
					placeholder="hb_..."
					required
					disabled={isSubmitting}
					autocomplete="off"
					class="input font-mono"
				/>
				{#if homeboxUrl}
					<p class="mt-2 text-caption text-neutral-500">
						Create or rotate keys in
						<a
							href="{homeboxUrl}/profile"
							target="_blank"
							rel="noopener noreferrer"
							class="text-primary-400 underline hover:text-primary-300"
						>
							Homebox Profile
						</a>
					</p>
				{/if}
			</div>

			<div class="flex flex-col gap-2 pt-2">
				<Button type="submit" variant="primary" full loading={isSubmitting}>
					<Key size={20} strokeWidth={2} />
					<span>Connect</span>
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
	{:else}
		<!-- Form -->
		<form class="space-y-4" onsubmit={handlePasswordSubmit}>
			{#if errorMessage}
				<div class="rounded-lg border border-error-500/20 bg-error-500/10 p-3 text-sm text-error-500">
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
					<Lock size={20} strokeWidth={2} />
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
	{/if}
</Modal>
