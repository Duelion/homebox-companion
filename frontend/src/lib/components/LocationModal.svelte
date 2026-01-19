<script lang="ts">
	import { MapPin, Home, Check } from 'lucide-svelte';
	import type { Location } from '$lib/types';
	import Modal from './Modal.svelte';
	import Button from './Button.svelte';

	interface Props {
		open: boolean;
		mode: 'create' | 'edit';
		location?: Location | null;
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
	let saveState = $state<'idle' | 'saving' | 'success' | 'error'>('idle');
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
			saveState = 'idle';
		}
	});

	async function handleSubmit(e: Event) {
		e.preventDefault();

		if (!name.trim()) {
			error = 'Name is required';
			return;
		}

		saveState = 'saving';
		error = '';

		try {
			await onsave({
				name: name.trim(),
				description: description.trim(),
				parentId: mode === 'create' ? parentLocation?.id || null : null,
			});

			// Show success state
			saveState = 'success';

			// Close modal after brief delay to show success
			setTimeout(() => {
				open = false;
			}, 800);
		} catch (err) {
			saveState = 'error';
			error = err instanceof Error ? err.message : 'Failed to save location';
		}
	}

	function handleClose() {
		// Prevent closing while saving or showing success
		if (saveState === 'saving' || saveState === 'success') return;
		open = false;
		onclose?.();
	}

	const title = $derived(mode === 'create' ? 'Create Location' : 'Edit Location');
	const isSaving = $derived(saveState === 'saving' || saveState === 'success');
</script>

<Modal bind:open {title} onclose={handleClose}>
	<form onsubmit={handleSubmit} class="space-y-4">
		{#if mode === 'create' && parentLocation}
			<div class="rounded-lg border border-neutral-700 bg-neutral-700 p-3">
				<p class="text-sm text-neutral-400">Creating inside:</p>
				<p class="flex items-center gap-2 font-medium text-neutral-200">
					<MapPin class="text-primary" size={16} />
					{parentLocation.name}
				</p>
			</div>
		{:else if mode === 'create'}
			<div class="rounded-lg border border-neutral-700 bg-neutral-700 p-3">
				<p class="text-sm text-neutral-400">Creating at:</p>
				<p class="flex items-center gap-2 font-medium text-neutral-200">
					<Home class="text-primary" size={16} />
					Root level
				</p>
			</div>
		{/if}

		<div>
			<label for="location-name" class="mb-1 block text-sm font-medium text-neutral-200">
				Name <span class="text-error">*</span>
			</label>
			<input
				id="location-name"
				type="text"
				bind:value={name}
				placeholder="e.g., Living Room, Drawer 1, Shelf A"
				class="placeholder:text-neutral-200-dim focus:border-primary focus:ring-primary/50 w-full rounded-xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-neutral-200 transition-colors focus:ring-2 focus:outline-none"
				disabled={isSaving}
			/>
		</div>

		<div>
			<label for="location-description" class="mb-1 block text-sm font-medium text-neutral-200">
				Description
			</label>
			<textarea
				id="location-description"
				bind:value={description}
				placeholder="e.g., Second drawer from top, left side of garage"
				rows="3"
				class="placeholder:text-neutral-200-dim focus:border-primary focus:ring-primary/50 w-full resize-none rounded-xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-neutral-200 transition-colors focus:ring-2 focus:outline-none"
				disabled={isSaving}
			></textarea>
		</div>

		{#if error}
			<div class="border-error/30 bg-error/10 rounded-lg border p-3">
				<p class="text-error text-sm">{error}</p>
			</div>
		{/if}

		<div class="flex gap-3 pt-2">
			<Button variant="secondary" full onclick={handleClose} disabled={isSaving}>Cancel</Button>
			<Button variant="primary" full type="submit" disabled={isSaving || !name.trim()}>
				{#if saveState === 'saving'}
					<div
						class="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white"
					></div>
					<span>Saving...</span>
				{:else if saveState === 'success'}
					<div class="bg-success-500/20 flex h-8 w-8 items-center justify-center rounded-full">
						<Check class="text-success-500" size={20} strokeWidth={2.5} />
					</div>
					<span>Saved!</span>
				{:else}
					<Check size={20} />
					<span>{mode === 'create' ? 'Create Location' : 'Save Changes'}</span>
				{/if}
			</Button>
		</div>
	</form>
</Modal>
