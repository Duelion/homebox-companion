<script lang="ts">
	import Search from '@lucide/svelte/icons/search';
	import Package from '@lucide/svelte/icons/package';
	import type { Location } from '$lib/types';
	import Button from './Button.svelte';
	import Modal from './Modal.svelte';

	interface Props {
		containers: Location[];
		onSelect: (container: Location) => void;
		onClose: () => void;
	}

	let { containers, onSelect, onClose }: Props = $props();
	let searchQuery = $state('');
	let matchingContainers = $derived(
		containers.filter((container) =>
			container.name.toLowerCase().includes(searchQuery.trim().toLowerCase())
		)
	);
</script>

<Modal open={true} title="Select Container" onclose={onClose}>
	<div class="relative mb-4">
		<div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
			<Search class="text-neutral-500" size={20} strokeWidth={1.5} />
		</div>
		<input
			type="search"
			placeholder="Search containers..."
			aria-label="Search containers"
			bind:value={searchQuery}
			class="input-with-icon"
		/>
	</div>

	<div class="max-h-64 space-y-2 overflow-y-auto">
		{#each matchingContainers as container (container.id)}
			<button type="button" class="selectable-item" onclick={() => onSelect(container)}>
				<Package class="shrink-0 text-neutral-500" size={20} strokeWidth={1.5} />
				<div class="min-w-0 flex-1">
					<p class="truncate font-medium text-neutral-100">{container.name}</p>
					{#if container.description}
						<p class="truncate text-body-sm text-neutral-500">{container.description}</p>
					{/if}
				</div>
			</button>
		{:else}
			<p class="py-8 text-center text-neutral-500">
				{searchQuery.trim() ? 'No matching containers' : 'No containers inside this location'}
			</p>
		{/each}
	</div>

	{#snippet footer()}
		<Button variant="ghost" onclick={onClose}>Cancel</Button>
	{/snippet}
</Modal>
