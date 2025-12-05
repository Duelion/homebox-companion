<script lang="ts">
	import type { LocationData } from '$lib/api';
	import Modal from './Modal.svelte';
	import Button from './Button.svelte';

	interface Props {
		open: boolean;
		mode: 'create' | 'edit';
		location?: LocationData | null;
		parentLocation?: { id: string; name: string } | null;
		onclose?: () => void;
		onsave: (data: { name: string; description: string; parentId: string | null }) => Promise<void>;
	}

	let {
		open = $bindable(),
		mode,
		location = null,
		parentLocation = null,
		onclose,
		onsave,
	}: Props = $props();

	let name = $state('');
	let description = $state('');
	let isSaving = $state(false);
	let error = $state('');

	// Reset form when modal opens
	$effect(() => {
		if (open) {
			if (mode === 'edit' && location) {
				name = location.name;
				description = location.description || '';
			} else {
				name = '';
				description = '';
			}
			error = '';
			isSaving = false;
		}
	});

	async function handleSubmit(e: Event) {
		e.preventDefault();

		if (!name.trim()) {
			error = 'Name is required';
			return;
		}

		isSaving = true;
		error = '';

		try {
			await onsave({
				name: name.trim(),
				description: description.trim(),
				parentId: mode === 'create' ? (parentLocation?.id || null) : null,
			});
			open = false;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to save location';
		} finally {
			isSaving = false;
		}
	}

	function handleClose() {
		open = false;
		onclose?.();
	}

	const title = $derived(mode === 'create' ? 'Create Location' : 'Edit Location');
</script>

<Modal bind:open {title} onclose={handleClose}>
	<form onsubmit={handleSubmit} class="space-y-4">
		{#if mode === 'create' && parentLocation}
			<div class="p-3 bg-surface-elevated rounded-lg border border-border">
				<p class="text-sm text-text-muted">Creating inside:</p>
				<p class="font-medium text-text flex items-center gap-2">
					<svg class="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
						<circle cx="12" cy="10" r="3" />
					</svg>
					{parentLocation.name}
				</p>
			</div>
		{:else if mode === 'create'}
			<div class="p-3 bg-surface-elevated rounded-lg border border-border">
				<p class="text-sm text-text-muted">Creating at:</p>
				<p class="font-medium text-text flex items-center gap-2">
					<svg class="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
						<polyline points="9 22 9 12 15 12 15 22" />
					</svg>
					Root level
				</p>
			</div>
		{/if}

		<div>
			<label for="location-name" class="block text-sm font-medium text-text mb-1">
				Name <span class="text-error">*</span>
			</label>
			<input
				id="location-name"
				type="text"
				bind:value={name}
				placeholder="e.g., Living Room, Drawer 1, Shelf A"
				class="w-full px-4 py-3 bg-background border border-border rounded-xl text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
				disabled={isSaving}
			/>
		</div>

		<div>
			<label for="location-description" class="block text-sm font-medium text-text mb-1">
				Description
			</label>
			<textarea
				id="location-description"
				bind:value={description}
				placeholder="Optional description..."
				rows="3"
				class="w-full px-4 py-3 bg-background border border-border rounded-xl text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors resize-none"
				disabled={isSaving}
			></textarea>
		</div>

		{#if error}
			<div class="p-3 bg-error/10 border border-error/30 rounded-lg">
				<p class="text-sm text-error">{error}</p>
			</div>
		{/if}

		<div class="flex gap-3 pt-2">
			<Button variant="secondary" full onclick={handleClose} disabled={isSaving}>
				Cancel
			</Button>
			<Button variant="primary" full type="submit" disabled={isSaving || !name.trim()}>
				{#if isSaving}
					<svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
					</svg>
					<span>Saving...</span>
				{:else}
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<polyline points="20 6 9 17 4 12" />
					</svg>
					<span>{mode === 'create' ? 'Create Location' : 'Save Changes'}</span>
				{/if}
			</Button>
		</div>
	</form>
</Modal>


