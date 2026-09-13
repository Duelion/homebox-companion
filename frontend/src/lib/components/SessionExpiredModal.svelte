<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { CircleAlert, Eye, EyeOff, Lock } from 'lucide-svelte';
	import { auth } from '$lib/api';
	import { authStore } from '$lib/stores/auth.svelte';
	import { showToast } from '$lib/stores/ui.svelte';
	import { resetLocationState } from '$lib/stores/locations.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { authLogger as log } from '$lib/utils/logger';
	import Button from './Button.svelte';
	import Modal from './Modal.svelte';

	let email = $state('');
	let password = $state('');
	let apiKey = $state('');
	let showApiKey = $state(false);
	let isSubmitting = $state(false);
	let errorMessage = $state('');

	// Derive sessionExpired from authStore for reactive template usage
	let sessionExpired = $derived(authStore.sessionExpired);

	async function handleSubmit(e: Event) {
		e.preventDefault();

		// API-key sessions can only be restored with a new/valid API key
		if (authStore.isApiKey) {
			const trimmedKey = apiKey.trim();
			if (!trimmedKey) {
				errorMessage = 'Please enter your API key';
				return;
			}
			if (!trimmedKey.startsWith('hb_')) {
				errorMessage = "API keys start with 'hb_'.";
				return;
			}

			isSubmitting = true;
			errorMessage = '';

			try {
				const response = await auth.loginWithApiKey(trimmedKey);
				authStore.setAuthenticatedState(response.token, null, response.email ?? undefined, {
					authType: 'api_key',
				});
				apiKey = '';
				showToast('Session restored — you can continue where you left off', 'success');
				log.info('Re-authentication successful, session restored');
			} catch (error) {
				log.error('Re-authentication failed:', error);
				errorMessage =
					error instanceof Error ? error.message : 'Login failed. Please check your API key.';
			} finally {
				isSubmitting = false;
			}
			return;
		}

		if (!email || !password) {
			errorMessage = 'Please enter email and password';
			return;
		}

		isSubmitting = true;
		errorMessage = '';

		try {
			const response = await auth.login(email, password);
			authStore.setAuthenticatedState(response.token, new Date(response.expires_at), undefined, {
				authType: 'jwt',
			});
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
				<p class="text-sm text-neutral-400">Please log in again to continue</p>
			</div>
		</div>
	</div>

	<!-- Form -->
	<form class="space-y-4" onsubmit={handleSubmit}>
		{#if errorMessage}
			<div class="rounded-lg border border-error-500/20 bg-error-500/10 p-3 text-sm text-error-500">
				{errorMessage}
			</div>
		{/if}

		{#if authStore.isApiKey}
			<div>
				<label for="reauth-api-key" class="label">Homebox API Key</label>
				<div class="relative">
					<input
						type={showApiKey ? 'text' : 'password'}
						id="reauth-api-key"
						bind:value={apiKey}
						placeholder="hb_..."
						autocomplete="off"
						spellcheck="false"
						disabled={isSubmitting}
						class="input pr-12"
					/>
					<button
						type="button"
						onclick={() => (showApiKey = !showApiKey)}
						class="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-neutral-500 transition-colors hover:bg-neutral-800 hover:text-neutral-300"
						aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
					>
						{#if showApiKey}
							<EyeOff size={20} strokeWidth={1.5} />
						{:else}
							<Eye size={20} strokeWidth={1.5} />
						{/if}
					</button>
				</div>
				<p class="mt-1.5 text-caption text-neutral-500">
					Create a new key in Homebox — Profile → API Keys.
				</p>
			</div>
		{:else}
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
		{/if}

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
</Modal>
