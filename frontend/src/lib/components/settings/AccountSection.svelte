<script lang="ts">
	/**
	 * AccountSection - User account info and logout button.
	 */
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { User, LogOut } from 'lucide-svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { resetLocationState } from '$lib/stores/locations.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { settingsService } from '$lib/workflows/settings.svelte';
	import Button from '$lib/components/Button.svelte';

	function handleLogout() {
		scanWorkflow.reset();
		resetLocationState();
		settingsService.reset();
		authStore.logout();
		goto(resolve('/'));
	}
</script>

<section class="card space-y-4">
	<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
		<User class="text-primary-400" size={20} strokeWidth={1.5} />
		Account
	</h2>

	<!-- Signed in as -->
	{#if authStore.email}
		<div
			class="flex items-center gap-3 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-4"
		>
			<div
				class="flex h-10 w-10 items-center justify-center rounded-full bg-primary-600/20 text-primary-400"
			>
				<User size={20} strokeWidth={1.5} />
			</div>
			<div class="min-w-0 flex-1">
				<p class="text-xs text-neutral-500">Signed in as</p>
				<p class="truncate font-medium text-neutral-100">{authStore.email}</p>
			</div>
		</div>
	{/if}

	<Button variant="danger" full onclick={handleLogout}>
		<LogOut size={20} strokeWidth={1.5} />
		<span>Sign Out</span>
	</Button>
</section>
