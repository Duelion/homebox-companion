<script lang="ts">
	import { onMount } from 'svelte';
	import { locations as locationsApi } from '$lib/api';
	import { showToast } from '$lib/stores/ui';
	import type { Location } from '$lib/types';
	import QrScanner from './QrScanner.svelte';

	interface Props {
		currentLocationId: string | null;
		onSelect: (id: string, name: string, path: string) => void;
		onClose: () => void;
	}

	let { currentLocationId, onSelect, onClose }: Props = $props();

	let allLocations = $state<{ id: string; name: string; path: string }[]>([]);
	let searchQuery = $state('');
	let isLoading = $state(true);
	let showQrScanner = $state(false);

	// Flatten the location tree into a searchable list with full paths
	function flattenLocations(
		locations: Location[],
		parentPath: string = ''
	): { id: string; name: string; path: string }[] {
		const result: { id: string; name: string; path: string }[] = [];

		for (const loc of locations) {
			const fullPath = parentPath ? `${parentPath} / ${loc.name}` : loc.name;
			result.push({ id: loc.id, name: loc.name, path: fullPath });

			if (loc.children && loc.children.length > 0) {
				result.push(...flattenLocations(loc.children, fullPath));
			}
		}

		return result;
	}

	// Filter locations based on search query
	const filteredLocations = $derived(() => {
		if (!searchQuery.trim()) return allLocations;
		const query = searchQuery.toLowerCase();
		return allLocations.filter(
			(loc) =>
				loc.name.toLowerCase().includes(query) || loc.path.toLowerCase().includes(query)
		);
	});

	onMount(async () => {
		try {
			const tree = await locationsApi.tree();
			allLocations = flattenLocations(tree);
		} catch (error) {
			console.error('Failed to load locations:', error);
			showToast('Failed to load locations', 'error');
		} finally {
			isLoading = false;
		}
	});

	function handleSelect(location: { id: string; name: string; path: string }) {
		onSelect(location.id, location.name, location.path);
		onClose();
	}

	async function handleQrScan(decodedText: string) {
		showQrScanner = false;

		// Extract UUID from URL (e.g., https://homebox.example.com/location/uuid-here)
		const uuidMatch = decodedText.match(
			/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i
		);

		if (!uuidMatch) {
			showToast('Invalid QR code - no location ID found', 'error');
			return;
		}

		const locationId = uuidMatch[0];

		try {
			const location = await locationsApi.get(locationId);
			// Build path from the flat list if we have it
			const flatLocation = allLocations.find((l) => l.id === locationId);
			const path = flatLocation?.path || location.name;
			onSelect(locationId, location.name, path);
			onClose();
			showToast(`Location set to "${location.name}"`, 'success');
		} catch (error) {
			console.error('Failed to fetch location:', error);
			showToast('Location not found', 'error');
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Modal backdrop -->
<div
	class="fixed inset-0 z-50 bg-black/70 flex items-end sm:items-center justify-center p-0 sm:p-4"
	onclick={(e) => e.target === e.currentTarget && onClose()}
	role="dialog"
	aria-modal="true"
	aria-label="Change location"
>
	<!-- Modal content -->
	<div class="bg-background w-full sm:max-w-md sm:rounded-2xl rounded-t-2xl max-h-[85vh] flex flex-col">
		<!-- Header -->
		<div class="flex items-center justify-between p-4 border-b border-border">
			<h3 class="text-lg font-semibold text-text">Change Location</h3>
			<button
				type="button"
				class="p-2 text-text-muted hover:text-text rounded-lg hover:bg-surface-elevated transition-colors"
				onclick={onClose}
				aria-label="Close"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<line x1="18" y1="6" x2="6" y2="18" />
					<line x1="6" y1="6" x2="18" y2="18" />
				</svg>
			</button>
		</div>

		<!-- Search and QR -->
		<div class="p-4 border-b border-border space-y-3">
			<!-- Search input -->
			<div class="relative">
				<svg
					class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<circle cx="11" cy="11" r="8" />
					<path d="m21 21-4.35-4.35" />
				</svg>
				<input
					type="text"
					placeholder="Search locations..."
					bind:value={searchQuery}
					class="w-full pl-10 pr-4 py-3 bg-surface border border-border rounded-xl text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
				/>
			</div>

			<!-- QR Scan button -->
			<button
				type="button"
				class="w-full flex items-center justify-center gap-3 p-3 rounded-xl border border-dashed border-border/30 hover:border-primary/40 hover:bg-primary/5 transition-all group"
				onclick={() => (showQrScanner = true)}
			>
				<svg
					class="w-5 h-5 text-text-muted group-hover:text-primary transition-colors"
					fill="none"
					stroke="currentColor"
					stroke-width="1.5"
					viewBox="0 0 24 24"
				>
					<path d="M3 7V5a2 2 0 0 1 2-2h2" />
					<path d="M17 3h2a2 2 0 0 1 2 2v2" />
					<path d="M21 17v2a2 2 0 0 1-2 2h-2" />
					<path d="M7 21H5a2 2 0 0 1-2-2v-2" />
					<rect x="7" y="7" width="3" height="3" />
					<rect x="14" y="7" width="3" height="3" />
					<rect x="7" y="14" width="3" height="3" />
					<rect x="14" y="14" width="3" height="3" />
				</svg>
				<span class="text-sm font-medium text-text-muted group-hover:text-primary transition-colors">
					Scan QR Code
				</span>
			</button>
		</div>

		<!-- Location list -->
		<div class="flex-1 overflow-y-auto p-2">
			{#if isLoading}
				<div class="flex items-center justify-center py-12">
					<div class="w-8 h-8 rounded-full border-2 border-primary/30 border-t-primary animate-spin"></div>
				</div>
			{:else if filteredLocations().length === 0}
				<div class="py-12 text-center text-text-muted">
					{#if searchQuery}
						<p>No locations match "{searchQuery}"</p>
					{:else}
						<p>No locations available</p>
					{/if}
				</div>
			{:else}
				<div class="space-y-1">
					{#each filteredLocations() as location}
						{@const isSelected = location.id === currentLocationId}
						<button
							type="button"
							class="w-full text-left p-3 rounded-xl transition-colors {isSelected
								? 'bg-primary/20 border border-primary/40'
								: 'hover:bg-surface-elevated'}"
							onclick={() => handleSelect(location)}
						>
							<div class="flex items-center gap-3">
								<div
									class="w-8 h-8 rounded-lg flex items-center justify-center {isSelected
										? 'bg-primary/30'
										: 'bg-surface-elevated'}"
								>
									<svg
										class="w-4 h-4 {isSelected ? 'text-primary-light' : 'text-text-muted'}"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
										<circle cx="12" cy="10" r="3" />
									</svg>
								</div>
								<div class="flex-1 min-w-0">
									<p class="font-medium text-text truncate">{location.name}</p>
									{#if location.path !== location.name}
										<p class="text-xs text-text-dim truncate">{location.path}</p>
									{/if}
								</div>
								{#if isSelected}
									<svg
										class="w-5 h-5 text-primary flex-shrink-0"
										fill="none"
										stroke="currentColor"
										stroke-width="2"
										viewBox="0 0 24 24"
									>
										<polyline points="20 6 9 17 4 12" />
									</svg>
								{/if}
							</div>
						</button>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>

{#if showQrScanner}
	<QrScanner onScan={handleQrScan} onClose={() => (showQrScanner = false)} />
{/if}

