<script lang="ts">
	/**
	 * BehaviorSubSection - AI behavior settings as a sub-section.
	 *
	 * Includes duplicate detection and serial number index management.
	 */
	import { onMount } from 'svelte';
	import { settingsService } from '$lib/workflows/settings.svelte';
	import Button from '$lib/components/Button.svelte';

	const service = settingsService;

	let isExpanded = $state(false);

	onMount(async () => {
		await service.loadDuplicateIndexStatus();
	});

	function formatDate(isoString: string | null): string {
		if (!isoString) return 'Never';
		try {
			const date = new Date(isoString);
			return date.toLocaleString();
		} catch {
			return 'Invalid date';
		}
	}

	const indexNeedsInit = $derived(
		service.duplicateIndexStatus && !service.duplicateIndexStatus.last_build_time
	);
</script>

<!-- Sub-section header -->
<button
	type="button"
	class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
	onclick={() => (isExpanded = !isExpanded)}
>
	<svg class="h-5 w-5 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
		<path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
		<path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
	</svg>
	<span>AI Output & Behavior</span>
	{#if service.duplicateDetectionEnabled}
		<span class="rounded-full bg-success-500/20 px-2 py-0.5 text-xs text-success-500">Dup. Check</span>
	{/if}
	{#if service.showTokenUsage}
		<span class="rounded-full bg-info-500/20 px-2 py-0.5 text-xs text-info-500">Tokens</span>
	{/if}
	<svg class="ml-auto h-4 w-4 transition-transform {isExpanded ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
		<polyline points="6 9 12 15 18 9" />
	</svg>
</button>

{#if isExpanded}
	<div class="space-y-4 rounded-xl border border-neutral-700 bg-neutral-800/30 p-4">
		<!-- Duplicate Detection Toggle -->
		<div class="flex items-center justify-between">
			<div class="flex-1">
				<h3 class="text-sm font-medium text-neutral-200">Duplicate Detection</h3>
				<p class="mt-1 text-xs text-neutral-400">
					Warn when adding items with serial numbers that already exist.
				</p>
			</div>
			<button
				type="button"
				class="relative h-6 w-11 rounded-full transition-colors {service.duplicateDetectionEnabled ? 'bg-primary-500' : 'bg-neutral-600'}"
				onclick={() => service.setDuplicateDetectionEnabled(!service.duplicateDetectionEnabled)}
				role="switch"
				aria-checked={service.duplicateDetectionEnabled}
			>
				<span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {service.duplicateDetectionEnabled ? 'translate-x-5' : 'translate-x-0'}"></span>
			</button>
		</div>

		<!-- Token Usage Display Toggle -->
		<div class="flex items-center justify-between border-t border-neutral-700 pt-3">
			<div class="flex-1">
				<h3 class="text-sm font-medium text-neutral-200">Show Token Usage</h3>
				<p class="mt-1 text-xs text-neutral-400">
					Display AI token counts (prompt/completion) after analysis.
				</p>
			</div>
			<button
				type="button"
				class="relative h-6 w-11 rounded-full transition-colors {service.showTokenUsage ? 'bg-primary-500' : 'bg-neutral-600'}"
				onclick={() => service.setShowTokenUsage(!service.showTokenUsage)}
				role="switch"
				aria-checked={service.showTokenUsage}
			>
				<span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {service.showTokenUsage ? 'translate-x-5' : 'translate-x-0'}"></span>
			</button>
		</div>

		<!-- Serial Number Index Status -->
		<div class="space-y-3 border-t border-neutral-700 pt-3">
			<div class="flex items-center justify-between">
				<h3 class="text-sm font-medium text-neutral-200">Serial Number Index</h3>
				{#if service.isLoading.duplicateIndex}
					<div class="h-4 w-4 animate-spin rounded-full border-2 border-primary-500 border-t-transparent"></div>
				{/if}
			</div>

			{#if service.duplicateIndexStatus}
				<div class="space-y-2 text-xs">
					<div class="flex items-center justify-between">
						<span class="text-neutral-400">Status</span>
						{#if indexNeedsInit}
							<span class="rounded-full bg-warning-500/20 px-2 py-0.5 text-warning-500">Not built</span>
						{:else if service.duplicateIndexStatus.is_loaded}
							<span class="rounded-full bg-success-500/20 px-2 py-0.5 text-success-500">Ready</span>
						{:else}
							<span class="text-neutral-400">Not loaded</span>
						{/if}
					</div>
					<div class="flex items-center justify-between">
						<span class="text-neutral-400">Items indexed</span>
						<span class="font-mono text-neutral-200">{service.duplicateIndexStatus.total_items_indexed}</span>
					</div>
					<div class="flex items-center justify-between">
						<span class="text-neutral-400">With serials</span>
						<span class="font-mono text-neutral-200">{service.duplicateIndexStatus.items_with_serials}</span>
					</div>
					<div class="flex items-center justify-between">
						<span class="text-neutral-400">Last updated</span>
						<span class="text-neutral-200">{formatDate(service.duplicateIndexStatus.last_update_time)}</span>
					</div>
				</div>
			{:else if service.errors.duplicateIndex}
				<p class="text-xs text-error-500">{service.errors.duplicateIndex}</p>
			{/if}

			<Button variant="secondary" size="sm" onclick={() => service.rebuildDuplicateIndex()} disabled={service.isLoading.duplicateIndex}>
				{#if service.isLoading.duplicateIndex}
					Rebuilding...
				{:else}
					Rebuild Index
				{/if}
			</Button>

			{#if service.duplicateIndexMessage}
				<p class="text-xs {service.duplicateIndexMessageType === 'success' ? 'text-success-500' : 'text-error-500'}">
					{service.duplicateIndexMessage}
				</p>
			{/if}
		</div>
	</div>
{/if}
