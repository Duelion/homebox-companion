<script lang="ts">
	import { onDestroy, untrack } from 'svelte';
	import { MapPin, Home, Check } from '@lucide/svelte';
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
	let disposed = false;
	let editorGeneration = 0;
	let closeTimeout: ReturnType<typeof setTimeout> | undefined;
	onDestroy(() => {
		disposed = true;
		editorGeneration++;
		clearTimeout(closeTimeout);
	});

	// Only open/identity changes reset a draft; a save may refresh the same location.
	const draftIdentity = $derived(JSON.stringify([mode, location?.id, parentLocation?.id]));
	$effect(() => {
		const isOpen = open;
		void draftIdentity;
		editorGeneration++;
		clearTimeout(closeTimeout);
		if (isOpen) {
			untrack(() => {
				name = mode === 'edit' && location ? location.name : '';
				description = mode === 'edit' && location ? location.description || '' : '';
			});
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

		if (saveState === 'saving' || saveState === 'success') return;
		const operation = editorGeneration;
		const isCurrent = () => !disposed && open && operation === editorGeneration;
		saveState = 'saving';
		error = '';

		try {
			await onsave({
				name: name.trim(),
				description: description.trim(),
				parentId: mode === 'create' ? parentLocation?.id || null : null,
			});
			if (!isCurrent()) return;

			// Show success state
			saveState = 'success';

			// Close modal after brief delay to show success
			closeTimeout = setTimeout(() => {
				if (isCurrent()) open = false;
			}, 800);
		} catch (err) {
			if (!isCurrent()) return;
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

<Modal bind:open {title} dismissible={!isSaving} onclose={handleClose}>
	<form onsubmit={handleSubmit} class="space-y-4">
		{#if mode === 'create' && parentLocation}
			<div class="rounded-lg border border-neutral-700 bg-neutral-700 p-3">
				<p class="text-body-sm text-neutral-400">Creating inside:</p>
				<p class="flex items-center gap-2 font-medium text-neutral-200">
					<MapPin class="text-primary" size={16} />
					{parentLocation.name}
				</p>
			</div>
		{:else if mode === 'create'}
			<div class="rounded-lg border border-neutral-700 bg-neutral-700 p-3">
				<p class="text-body-sm text-neutral-400">Creating at:</p>
				<p class="flex items-center gap-2 font-medium text-neutral-200">
					<Home class="text-primary" size={16} />
					Root level
				</p>
			</div>
		{/if}

		<div>
			<label for="location-name" class="mb-1 block text-body-sm font-medium text-neutral-200">
				Name <span class="text-error">*</span>
			</label>
			<input
				id="location-name"
				type="text"
				bind:value={name}
				placeholder="e.g., Living Room, Drawer 1, Shelf A"
				class="placeholder:text-neutral-400 w-full rounded-xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-neutral-200 transition-colors focus:border-primary focus:outline-hidden focus:ring-2 focus:ring-primary/50"
				disabled={isSaving}
			/>
		</div>

		<div>
			<label
				for="location-description"
				class="mb-1 block text-body-sm font-medium text-neutral-200"
			>
				Description
			</label>
			<textarea
				id="location-description"
				bind:value={description}
				placeholder="e.g., Second drawer from top, left side of garage"
				rows="3"
				class="placeholder:text-neutral-400 w-full resize-none rounded-xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-neutral-200 transition-colors focus:border-primary focus:outline-hidden focus:ring-2 focus:ring-primary/50"
				disabled={isSaving}></textarea>
		</div>

		{#if error}
			<div class="rounded-lg border border-error/30 bg-error/10 p-3">
				<p class="text-body-sm text-error">{error}</p>
			</div>
		{/if}

		<div class="flex gap-3 pt-2">
			<Button variant="secondary" full onclick={handleClose} disabled={isSaving}>Cancel</Button>
			<Button variant="primary" full type="submit" disabled={isSaving || !name.trim()}>
				{#if saveState === 'saving'}
					<div
						class="animate-spin rounded-full border-2 border-neutral-100/30 border-t-neutral-100 size-5"
					></div>
					<span>Saving...</span>
				{:else if saveState === 'success'}
					<div class="flex items-center justify-center rounded-full bg-success-500/20 size-8">
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
