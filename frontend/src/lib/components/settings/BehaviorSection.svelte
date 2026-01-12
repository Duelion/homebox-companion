<script lang="ts">
	/**
	 * BehaviorSection - Application behavior settings.
	 *
	 * Includes:
	 * - Duplicate detection toggle
	 * - Serial number index status and rebuild
	 */
	import { onMount } from 'svelte';
	import { settingsService } from '$lib/workflows/settings.svelte';
	import Button from '$lib/components/Button.svelte';
	import CollapsibleSection from './CollapsibleSection.svelte';

	const service = settingsService;

	// Load index status on mount
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

	// Derived state for index status
	const indexNeedsInit = $derived(
		service.duplicateIndexStatus && !service.duplicateIndexStatus.last_build_time
	);
</script>

{#snippet icon()}
	<svg
		class="h-5 w-5 text-primary"
		fill="none"
		stroke="currentColor"
		viewBox="0 0 24 24"
		stroke-width="1.5"
	>
		<path
			d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
		/>
		<path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
	</svg>
{/snippet}

<CollapsibleSection title="Behavior Settings" {icon}>
	<!-- Duplicate Detection Toggle -->
	<div
		class="flex items-center justify-between rounded-xl border border-base-content/10 bg-base-200/50 p-4"
	>
		<div class="flex-1">
			<h3 class="text-sm font-medium text-base-content">Duplicate Detection</h3>
			<p class="mt-1 text-xs text-base-content/60">
				Warn when adding items with serial numbers that already exist in Homebox.
			</p>
		</div>
		<button
			type="button"
			class="relative h-6 w-11 rounded-full transition-colors {service.duplicateDetectionEnabled
				? 'bg-primary'
				: 'bg-base-content/30'}"
			onclick={() => service.setDuplicateDetectionEnabled(!service.duplicateDetectionEnabled)}
			role="switch"
			aria-checked={service.duplicateDetectionEnabled}
			aria-label="Toggle duplicate detection"
		>
			<span
				class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {service.duplicateDetectionEnabled
					? 'translate-x-5'
					: 'translate-x-0'}"
			></span>
		</button>
	</div>

	<!-- Serial Number Index Status -->
	<div class="space-y-3 rounded-xl border border-base-content/10 bg-base-200/50 p-4">
		<div class="flex items-center justify-between">
			<h3 class="text-sm font-medium text-base-content">Serial Number Index</h3>
			{#if service.isLoading.duplicateIndex}
				<div
					class="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"
				></div>
			{/if}
		</div>

		{#if service.duplicateIndexStatus}
			<div class="space-y-2 text-xs">
				<!-- Status indicators -->
				<div class="flex items-center justify-between">
					<span class="text-base-content/60">Status</span>
					{#if indexNeedsInit}
						<span
							class="inline-flex items-center gap-1 rounded-full bg-warning/20 px-2 py-0.5 text-warning"
						>
							<svg
								class="h-3 w-3"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2"
							>
								<path
									d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
								/>
							</svg>
							Index not yet built
						</span>
					{:else if service.duplicateIndexStatus.is_loaded}
						<span
							class="inline-flex items-center gap-1 rounded-full bg-success/20 px-2 py-0.5 text-success"
						>
							<svg
								class="h-3 w-3"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2"
							>
								<polyline points="20 6 9 17 4 12" />
							</svg>
							Ready
						</span>
					{:else}
						<span class="text-base-content/60">Not loaded</span>
					{/if}
				</div>

				<div class="flex items-center justify-between">
					<span class="text-base-content/60">Total items indexed</span>
					<span class="font-mono text-base-content"
						>{service.duplicateIndexStatus.total_items_indexed}</span
					>
				</div>

				<div class="flex items-center justify-between">
					<span class="text-base-content/60">Items with serial numbers</span>
					<span class="font-mono text-base-content"
						>{service.duplicateIndexStatus.items_with_serials}</span
					>
				</div>

				<div class="flex items-center justify-between">
					<span class="text-base-content/60">Last updated</span>
					<span class="text-base-content"
						>{formatDate(service.duplicateIndexStatus.last_update_time)}</span
					>
				</div>
			</div>
		{:else if service.errors.duplicateIndex}
			<p class="text-xs text-error">{service.errors.duplicateIndex}</p>
		{:else}
			<p class="text-xs text-base-content/60">Loading index status...</p>
		{/if}

		<!-- Rebuild Button -->
		<div class="border-t border-base-content/10 pt-3">
			<Button
				variant="secondary"
				size="sm"
				onclick={() => service.rebuildDuplicateIndex()}
				disabled={service.isLoading.duplicateIndex}
			>
				{#if service.isLoading.duplicateIndex}
					<div
						class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
					></div>
					Rebuilding...
				{:else}
					<svg
						class="h-4 w-4"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path
							d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
						/>
					</svg>
					Rebuild Index
				{/if}
			</Button>
			<p class="mt-2 text-xs text-base-content/50">
				Rebuilds the serial number index from all items in Homebox.
			</p>
		</div>

		<!-- Status Message -->
		{#if service.duplicateIndexMessage}
			<div
				class="mt-2 rounded-lg p-2 text-xs {service.duplicateIndexMessageType === 'success'
					? 'bg-success/10 text-success'
					: 'bg-error/10 text-error'}"
			>
				{service.duplicateIndexMessage}
			</div>
		{/if}
	</div>
</CollapsibleSection>
