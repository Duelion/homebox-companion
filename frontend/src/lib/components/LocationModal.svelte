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
					<svg class="h-4 w-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
						<circle cx="12" cy="10" r="3" />
					</svg>
					{parentLocation.name}
				</p>
			</div>
		{:else if mode === 'create'}
			<div class="rounded-lg border border-neutral-700 bg-neutral-700 p-3">
				<p class="text-sm text-neutral-400">Creating at:</p>
				<p class="flex items-center gap-2 font-medium text-neutral-200">
					<svg class="h-4 w-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
						<polyline points="9 22 9 12 15 12 15 22" />
					</svg>
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
				class="placeholder:text-neutral-200-dim w-full rounded-xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-neutral-200 transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
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
				class="placeholder:text-neutral-200-dim w-full resize-none rounded-xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-neutral-200 transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
				disabled={isSaving}
			></textarea>
		</div>

		{#if error}
			<div class="rounded-lg border border-error/30 bg-error/10 p-3">
				<p class="text-sm text-error">{error}</p>
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
					<div class="flex h-8 w-8 items-center justify-center rounded-full bg-success-500/20">
						<svg
							class="h-5 w-5 text-success-500"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="2.5"
						>
							<polyline points="20 6 9 17 4 12" />
						</svg>
					</div>
					<span>Saved!</span>
				{:else}
					<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<polyline points="20 6 9 17 4 12" />
					</svg>
					<span>{mode === 'create' ? 'Create Location' : 'Save Changes'}</span>
				{/if}
			</Button>
		</div>
	</form>
</Modal>
