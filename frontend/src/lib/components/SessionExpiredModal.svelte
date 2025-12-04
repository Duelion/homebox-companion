<script lang="ts">
	import { auth } from '$lib/api';
	import { sessionExpired, onReauthSuccess, logout } from '$lib/stores/auth';
	import Button from './Button.svelte';

	let email = $state('');
	let password = $state('');
	let isSubmitting = $state(false);
	let errorMessage = $state('');

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
			onReauthSuccess(response.token);
			// Reset form
			email = '';
			password = '';
		} catch (error) {
			console.error('Re-authentication failed:', error);
			errorMessage =
				error instanceof Error ? error.message : 'Login failed. Please check your credentials.';
		} finally {
			isSubmitting = false;
		}
	}

	function handleLogout() {
		logout();
		window.location.href = '/';
	}
</script>

{#if $sessionExpired}
	<!-- Non-dismissable modal backdrop -->
	<div class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
		<div class="w-full max-w-sm bg-surface rounded-2xl border border-border shadow-xl animate-scale-in overflow-hidden">
			<!-- Header -->
			<div class="px-6 py-4 border-b border-border bg-warning/10">
				<div class="flex items-center gap-3">
					<div class="p-2 rounded-full bg-warning/20">
						<svg class="w-5 h-5 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
							<circle cx="12" cy="12" r="10" />
							<line x1="12" y1="8" x2="12" y2="12" />
							<line x1="12" y1="16" x2="12.01" y2="16" />
						</svg>
					</div>
					<div>
						<h3 class="text-lg font-semibold text-text">Session Expired</h3>
						<p class="text-sm text-text-muted">Please log in again to continue</p>
					</div>
				</div>
			</div>

			<!-- Form -->
			<form class="p-6 space-y-4" onsubmit={handleSubmit}>
				{#if errorMessage}
					<div class="p-3 rounded-lg bg-error/10 border border-error/20 text-error text-sm">
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
						class="input"
					/>
				</div>

				<div class="flex flex-col gap-2 pt-2">
					<Button type="submit" variant="primary" full loading={isSubmitting}>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
							<rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
							<path d="M7 11V7a5 5 0 0 1 10 0v4" />
						</svg>
						<span>Sign In</span>
					</Button>

					<button
						type="button"
						class="text-sm text-text-muted hover:text-text transition-colors py-2"
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

