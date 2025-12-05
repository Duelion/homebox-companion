<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/api';
	import { token, isAuthenticated } from '$lib/stores/auth';
	import { showToast, setLoading } from '$lib/stores/ui';
	import Button from '$lib/components/Button.svelte';
	import { onMount } from 'svelte';

	let email = $state('');
	let password = $state('');
	let isSubmitting = $state(false);

	// Redirect if already authenticated
	onMount(() => {
		if ($isAuthenticated) {
			goto('/location');
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
			token.set(response.token);
			showToast('Login successful!', 'success');
			goto('/location');
		} catch (error) {
			console.error('Login failed:', error);
			showToast(
				error instanceof Error ? error.message : 'Login failed. Please check your credentials.',
				'error'
			);
		} finally {
			isSubmitting = false;
			setLoading(false);
		}
	}
</script>

<svelte:head>
	<title>Login - Homebox Companion</title>
</svelte:head>

<div class="flex flex-col items-center justify-center min-h-[70vh] animate-in">
	<!-- Welcome illustration -->
	<div class="relative w-32 h-32 mb-8">
		<div class="absolute inset-0 bg-primary/20 rounded-3xl animate-float" style="animation-delay: 0s;"></div>
		<div class="absolute inset-4 bg-primary/30 rounded-2xl animate-float" style="animation-delay: 0.5s;"></div>
		<div class="absolute inset-8 bg-primary/40 rounded-xl animate-float" style="animation-delay: 1s;"></div>
	</div>

	<h1 class="text-2xl sm:text-3xl font-bold text-text mb-2 text-center px-2">Welcome to Homebox Companion</h1>
	<p class="text-text-muted mb-8 text-center px-2 text-sm sm:text-base">
		Scan and organize your inventory with AI-powered detection
	</p>

	<form class="w-full max-w-sm space-y-4" onsubmit={handleSubmit}>
		<div>
			<label for="email" class="label">Email</label>
			<input
				type="email"
				id="email"
				bind:value={email}
				placeholder="Enter your email"
				required
				class="input"
			/>
		</div>

		<div>
			<label for="password" class="label">Password</label>
			<input
				type="password"
				id="password"
				bind:value={password}
				placeholder="Enter your password"
				required
				class="input"
			/>
		</div>

		<Button type="submit" variant="primary" full loading={isSubmitting}>
			<span>Sign In</span>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<line x1="5" y1="12" x2="19" y2="12" />
				<polyline points="12 5 19 12 12 19" />
			</svg>
		</Button>
	</form>
</div>
