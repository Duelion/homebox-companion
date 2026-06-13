<script lang="ts">
	import { ChevronDown, Layers } from 'lucide-svelte';
	import { collectionStore } from '$lib/stores/collection.svelte';
	import { locationStore } from '$lib/stores/locations.svelte';
	import { clearTagsCache, fetchTags } from '$lib/stores/tags.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { locationNavigator } from '$lib/services/locationNavigator.svelte';
	import { showToast } from '$lib/stores/ui.svelte';

	let open = $state(false);
	let dropdownRef = $state<HTMLDivElement | null>(null);

	// Close dropdown when clicking outside
	function handleClickOutside(event: MouseEvent) {
		if (dropdownRef && !dropdownRef.contains(event.target as Node)) {
			open = false;
		}
	}

	// Handle keyboard navigation
	function handleKeydown(event: KeyboardEvent) {
		if (!open) return;

		if (event.key === 'Escape') {
			open = false;
			// Return focus to trigger button
			dropdownRef?.querySelector('button')?.focus();
		} else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
			event.preventDefault();
			const options = dropdownRef?.querySelectorAll<HTMLButtonElement>('[role="option"]');
			if (!options?.length) return;
			const currentIndex = Array.from(options).findIndex((el) => el === document.activeElement);
			const nextIndex =
				event.key === 'ArrowDown'
					? Math.min(currentIndex + 1, options.length - 1)
					: Math.max(currentIndex - 1, 0);
			options[nextIndex]?.focus();
		}
	}

	async function handleSelect(groupId: string) {
		open = false;
		const changed = collectionStore.selectGroup(groupId);
		if (changed) {
			// Clear dependent state and re-fetch for the new collection
			locationStore.clear();
			clearTagsCache();
			scanWorkflow.reset();
			// Reload data for the new collection
			try {
				await Promise.all([locationNavigator.loadTree(), fetchTags(true)]);
			} catch {
				showToast('Failed to load collection data. Please try again.', 'error');
			}
		}
	}
</script>

<svelte:window onclick={handleClickOutside} />

{#if collectionStore.hasMultiple}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="relative" bind:this={dropdownRef} onkeydown={handleKeydown}>
		<button
			type="button"
			onclick={() => (open = !open)}
			class="flex items-center gap-1.5 rounded-lg border border-neutral-700 bg-neutral-800/80 px-3 py-1.5 text-sm text-neutral-300 transition-all hover:border-neutral-600 hover:bg-neutral-800 hover:text-neutral-100"
			aria-haspopup="listbox"
			aria-expanded={open}
			id="collection-selector"
		>
			<Layers size={14} strokeWidth={1.5} class="text-primary-400" />
			<span class="max-w-32 truncate">{collectionStore.selectedGroup?.name ?? 'Select'}</span>
			<ChevronDown
				size={14}
				strokeWidth={1.5}
				class="transition-transform {open ? 'rotate-180' : ''}"
			/>
		</button>

		{#if open}
			<div
				class="absolute left-0 top-full z-50 mt-1 min-w-48 rounded-xl border border-neutral-700 bg-neutral-900 py-1 shadow-xl"
				role="listbox"
				aria-labelledby="collection-selector"
			>
				{#each collectionStore.groups as group (group.id)}
					{@const isSelected = group.id === collectionStore.selectedId}
					<button
						type="button"
						role="option"
						aria-selected={isSelected}
						class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors
							{isSelected
							? 'bg-primary-500/10 text-primary-400'
							: 'text-neutral-300 hover:bg-neutral-800 hover:text-neutral-100'}"
						onclick={() => handleSelect(group.id)}
					>
						<Layers
							size={14}
							strokeWidth={1.5}
							class={isSelected ? 'text-primary-400' : 'text-neutral-500'}
						/>
						<span class="truncate">{group.name}</span>
						{#if isSelected}
							<span class="ml-auto text-primary-400">✓</span>
						{/if}
					</button>
				{/each}
			</div>
		{/if}
	</div>
{/if}
