<script lang="ts">
	import { auth, ApiError } from '$lib/api';
	import { sessionExpired, sessionExpiredReason, onReauthSuccess, logout, type SessionExpiredReason } from '$lib/stores/auth';
	import { resetLocationState } from '$lib/stores/locations';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import Button from './Button.svelte';

	let email = $state('');
	let password = $state('');
	let isSubmitting = $state(false);
	let errorMessage = $state('');

	// Get UI content based on the reason for session expiry
	function getReasonContent(reason: SessionExpiredReason | null): { 
		title: string; 
		subtitle: string; 
		icon: 'warning' | 'error' | 'network';
	} {
		switch (reason) {
			case 'network':
				return {
					title: 'Connection Lost',
					subtitle: 'Unable to reach the server. Please check your internet connection.',
					icon: 'network'
				};
			case 'server_error':
				return {
					title: 'Server Error',
					subtitle: 'The server encountered an error. Please try again.',
					icon: 'error'
				};
			case 'expired':
			case 'unknown':
			default:
				return {
					title: 'Session Expired',
					subtitle: 'Please log in again to continue',
					icon: 'warning'
				};
		}
	}
	
	/**
	 * Determine the error reason from a login failure.
	 */
	function getLoginErrorReason(error: unknown): SessionExpiredReason {
		if (error instanceof ApiError) {
			if (error.status >= 500) {
				return 'server_error';
			}
			// 401/403 means invalid credentials, not a session issue
			return 'expired';
		}
		
		// Network errors (TypeError: Failed to fetch, etc.)
		if (error instanceof TypeError || 
			(error instanceof Error && error.message.includes('fetch'))) {
			return 'network';
		}
		
		return 'unknown';
	}

	// Reactive content based on reason
	let content = $derived(getReasonContent($sessionExpiredReason));

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
			
			// Update the modal's reason if the error type changed (e.g., network error during re-auth)
			const errorReason = getLoginErrorReason(error);
			if (errorReason === 'network' || errorReason === 'server_error') {
				// Update the header to reflect the current connection issue
				sessionExpiredReason.set(errorReason);
				errorMessage = errorReason === 'network' 
					? 'Unable to connect. Please check your internet connection.'
					: 'Server error. Please try again later.';
			} else {
				// Credential errors - keep original header, show error message
				errorMessage = error instanceof Error ? error.message : 'Login failed. Please check your credentials.';
			}
		} finally {
			isSubmitting = false;
		}
	}

	function handleLogout() {
		scanWorkflow.reset();
		resetLocationState();
		logout();
		window.location.href = '/';
	}
</script>

{#if $sessionExpired}
	<!-- Non-dismissable modal backdrop -->
	<div class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
		<div class="w-full max-w-sm bg-surface rounded-2xl border border-border shadow-xl animate-scale-in overflow-hidden">
			<!-- Header -->
			<div class="px-6 py-4 border-b border-border {content.icon === 'error' ? 'bg-error/10' : content.icon === 'network' ? 'bg-orange-500/10' : 'bg-warning/10'}">
				<div class="flex items-center gap-3">
					<div class="p-2 rounded-full {content.icon === 'error' ? 'bg-error/20' : content.icon === 'network' ? 'bg-orange-500/20' : 'bg-warning/20'}">
						{#if content.icon === 'network'}
							<!-- Network/WiFi off icon -->
							<svg class="w-5 h-5 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
								<path d="M1 1l22 22" />
								<path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
								<path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
								<path d="M10.71 5.05A16 16 0 0 1 22.58 9" />
								<path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
								<path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
								<line x1="12" y1="20" x2="12.01" y2="20" />
							</svg>
						{:else if content.icon === 'error'}
							<!-- Server error icon -->
							<svg class="w-5 h-5 text-error" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
								<rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
								<rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
								<line x1="6" y1="6" x2="6.01" y2="6" />
								<line x1="6" y1="18" x2="6.01" y2="18" />
								<path d="M12 11v2" />
								<path d="M12 17h.01" />
							</svg>
						{:else}
							<!-- Warning/clock icon for session expired -->
							<svg class="w-5 h-5 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
								<circle cx="12" cy="12" r="10" />
								<line x1="12" y1="8" x2="12" y2="12" />
								<line x1="12" y1="16" x2="12.01" y2="16" />
							</svg>
						{/if}
					</div>
					<div>
						<h3 class="text-lg font-semibold text-text">{content.title}</h3>
						<p class="text-sm text-text-muted">{content.subtitle}</p>
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





