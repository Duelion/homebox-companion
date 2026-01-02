<script lang="ts">
	/**
	 * ApprovalItemPanel - Expandable panel for viewing/editing a pending approval action
	 *
	 * Supports three action types:
	 * - create_item: Editable name, quantity, description, location, notes, tags
	 * - update_item: Editable fields that are being changed
	 * - delete_item: Read-only verification view
	 */
	import { slide } from 'svelte/transition';
	import type { PendingApproval } from '../api/chat';
	import { labelStore } from '../stores/labels.svelte';
	import { locationStore } from '../stores/locations.svelte';

	type ActionType = 'delete' | 'create' | 'update';

	interface Props {
		approval: PendingApproval;
		isProcessing: boolean;
		onApprove: (approvalId: string, modifiedParams?: Record<string, unknown>) => void;
		onReject: (approvalId: string) => void;
	}

	let { approval, isProcessing, onApprove, onReject }: Props = $props();

	// Local state
	let expanded = $state(false);

	// Track which action is being processed to show spinner on correct button
	let processingAction = $state<'approve' | 'reject' | null>(null);

	// Editable copies of parameters
	let editedName = $state('');
	let editedDescription = $state('');
	let editedQuantity = $state(1);
	let editedNotes = $state('');
	let editedLabelIds = $state<string[]>([]);
	let editedLocationId = $state('');

	// Helper to get original values with proper typing
	const originalName = $derived((approval.parameters.name as string | undefined) ?? '');
	const originalDescription = $derived(
		(approval.parameters.description as string | undefined) ?? ''
	);
	const originalQuantity = $derived((approval.parameters.quantity as number | undefined) ?? 1);
	const originalNotes = $derived((approval.parameters.notes as string | undefined) ?? '');
	const originalLabelIds = $derived((approval.parameters.label_ids as string[] | undefined) ?? []);
	const originalLocationId = $derived(
		(approval.parameters.location_id as string | undefined) ?? ''
	);

	// Track which approval we've initialized for
	let initializedForApprovalId = $state<string | null>(null);

	// Initialize edited values when expanded, reset when approval changes
	$effect(() => {
		const currentApprovalId = approval.id;

		// Reset if approval changed
		if (initializedForApprovalId !== null && initializedForApprovalId !== currentApprovalId) {
			initializedForApprovalId = null;
			expanded = false; // Collapse when switching to different approval
		}

		// Initialize when first expanded for this approval
		if (expanded && initializedForApprovalId !== currentApprovalId) {
			editedName = originalName;
			editedDescription = originalDescription;
			editedQuantity = originalQuantity;
			editedNotes = originalNotes;
			editedLabelIds = [...originalLabelIds];
			editedLocationId = originalLocationId;
			initializedForApprovalId = currentApprovalId;
		}
	});

	// Clear processing action when isProcessing becomes false
	$effect(() => {
		if (!isProcessing) {
			processingAction = null;
		}
	});

	// Get action type for styling and behavior
	const actionType = $derived.by((): ActionType => {
		if (approval.tool_name === 'delete_item') return 'delete';
		if (approval.tool_name === 'create_item') return 'create';
		if (approval.tool_name === 'update_item') return 'update';
		return 'update';
	});

	// Get human-readable action description (concise - just the item name)
	const actionDescription = $derived.by(() => {
		const toolName = approval.tool_name;
		const info = approval.display_info;

		if (toolName === 'delete_item') {
			return info?.item_name ?? 'Delete item';
		}

		if (toolName === 'update_item') {
			return info?.item_name ?? 'Update item';
		}

		if (toolName === 'create_item') {
			return info?.item_name ?? 'New item';
		}

		return toolName.replace(/_/g, ' ');
	});

	// Helper to compare label arrays
	function arraysEqual(a: string[], b: string[]): boolean {
		if (a.length !== b.length) return false;
		const sortedA = [...a].sort();
		const sortedB = [...b].sort();
		return sortedA.every((val, i) => val === sortedB[i]);
	}

	// Check if user has modified any editable parameters
	// For update actions, only considers fields in fieldsBeingChanged
	const hasModifications = $derived.by(() => {
		if (actionType === 'delete') return false;

		// For create actions, check all fields
		if (actionType === 'create') {
			return (
				editedName !== originalName ||
				editedDescription !== originalDescription ||
				editedQuantity !== originalQuantity ||
				editedNotes !== originalNotes ||
				!arraysEqual(editedLabelIds, originalLabelIds) ||
				editedLocationId !== originalLocationId
			);
		}

		// For update actions, only check fields that are being changed
		const allowed = new Set(fieldsBeingChanged);
		return (
			(allowed.has('name') && editedName !== originalName) ||
			(allowed.has('description') && editedDescription !== originalDescription) ||
			(allowed.has('quantity') && editedQuantity !== originalQuantity) ||
			(allowed.has('notes') && editedNotes !== originalNotes) ||
			(allowed.has('labels') && !arraysEqual(editedLabelIds, originalLabelIds)) ||
			(allowed.has('location') && editedLocationId !== originalLocationId)
		);
	});

	// Check which fields are being changed (for update_item)
	const fieldsBeingChanged = $derived.by(() => {
		if (actionType !== 'update') return [];
		const fields: string[] = [];
		if (approval.parameters.name !== undefined) fields.push('name');
		if (approval.parameters.description !== undefined) fields.push('description');
		if (approval.parameters.quantity !== undefined) fields.push('quantity');
		if (approval.parameters.notes !== undefined) fields.push('notes');
		if (approval.parameters.label_ids !== undefined) fields.push('labels');
		if (approval.parameters.location_id !== undefined) fields.push('location');
		return fields;
	});

	// Build modified parameters object (only changed fields)
	// For update actions, only returns fields that are in fieldsBeingChanged
	function getModifiedParams(): Record<string, unknown> | undefined {
		if (!hasModifications) return undefined;

		const mods: Record<string, unknown> = {};
		const isUpdate = actionType === 'update';
		const allowed = new Set(fieldsBeingChanged);

		// Helper to check if field can be modified
		const canModify = (field: string) => !isUpdate || allowed.has(field);

		if (editedName !== originalName && canModify('name')) {
			mods.name = editedName;
		}
		if (editedDescription !== originalDescription && canModify('description')) {
			mods.description = editedDescription;
		}
		if (editedQuantity !== originalQuantity && canModify('quantity')) {
			mods.quantity = editedQuantity;
		}
		if (editedNotes !== originalNotes && canModify('notes')) {
			mods.notes = editedNotes;
		}
		if (!arraysEqual(editedLabelIds, originalLabelIds) && canModify('labels')) {
			mods.label_ids = editedLabelIds;
		}
		if (editedLocationId !== originalLocationId && canModify('location')) {
			mods.location_id = editedLocationId;
		}

		return Object.keys(mods).length > 0 ? mods : undefined;
	}

	// Toggle a label selection
	function toggleLabel(labelId: string) {
		if (editedLabelIds.includes(labelId)) {
			editedLabelIds = editedLabelIds.filter((id) => id !== labelId);
		} else {
			editedLabelIds = [...editedLabelIds, labelId];
		}
	}

	function handleApprove() {
		processingAction = 'approve';
		const modifiedParams = expanded ? getModifiedParams() : undefined;
		onApprove(approval.id, modifiedParams);
	}

	function handleReject() {
		processingAction = 'reject';
		onReject(approval.id);
	}

	function toggleExpanded() {
		expanded = !expanded;
	}
</script>

<div class="transition-colors {approval.is_expired ? 'opacity-50' : ''}">
	<!-- Collapsed Header Row -->
	<div class="flex items-start gap-3 px-5 py-4">
		<!-- Action Icon -->
		<div
			class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl {actionType === 'delete'
				? 'bg-error-500/15'
				: actionType === 'create'
					? 'bg-success-500/15'
					: 'bg-warning-500/15'}"
		>
			{#if actionType === 'delete'}
				<svg
					class="h-4.5 w-4.5 text-error-500"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="2"
				>
					<path
						d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
					/>
				</svg>
			{:else if actionType === 'create'}
				<svg
					class="h-4.5 w-4.5 text-success-500"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="2"
				>
					<path d="M12 4v16m8-8H4" />
				</svg>
			{:else}
				<svg
					class="h-4.5 w-4.5 text-warning-500"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="2"
				>
					<path
						d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
					/>
				</svg>
			{/if}
		</div>

		<!-- Action Info -->
		<div class="min-w-0 flex-1">
			<p
				class="text-sm font-medium {actionType === 'delete'
					? 'text-error-400'
					: 'text-neutral-200'}"
			>
				{actionDescription}
			</p>
		</div>

		<!-- Action Buttons -->
		<div class="flex shrink-0 gap-1.5">
			<!-- Expand/Edit Button - always enabled unless expired (can collapse during processing) -->
			<button
				type="button"
				class="flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-700 bg-neutral-800 text-neutral-400 transition-all hover:border-primary-500/50 hover:bg-primary-500/10 hover:text-primary-400 disabled:opacity-50 {expanded
					? 'border-primary-500/50 bg-primary-500/10 text-primary-400'
					: ''}"
				disabled={approval.is_expired}
				onclick={toggleExpanded}
				aria-label={actionType === 'delete' ? 'View details' : 'Edit'}
				aria-expanded={expanded}
			>
				{#if actionType === 'delete'}
					<!-- Eye icon for delete (view details) -->
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
						/>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
						/>
					</svg>
				{:else}
					<!-- Pencil icon for create/update (edit) -->
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
						/>
					</svg>
				{/if}
			</button>

			<!-- Reject Button -->
			<button
				type="button"
				class="flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-700 bg-neutral-800 text-neutral-400 transition-all hover:border-error-500/50 hover:bg-error-500/10 hover:text-error-500 disabled:opacity-50"
				disabled={isProcessing || approval.is_expired}
				onclick={handleReject}
				aria-label="Reject"
			>
				{#if processingAction === 'reject'}
					<div
						class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
					></div>
				{:else}
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M6 18L18 6M6 6l12 12"
						/>
					</svg>
				{/if}
			</button>

			<!-- Approve Button -->
			<button
				type="button"
				class="flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-700 bg-neutral-800 text-neutral-400 transition-all hover:border-success-500/50 hover:bg-success-500/10 hover:text-success-500 disabled:opacity-50"
				disabled={isProcessing || approval.is_expired}
				onclick={handleApprove}
				aria-label="Approve"
			>
				{#if processingAction === 'approve'}
					<div
						class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
					></div>
				{:else}
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M5 13l4 4L19 7"
						/>
					</svg>
				{/if}
			</button>
		</div>
	</div>

	<!-- Expanded Content -->
	{#if expanded}
		<div
			class="border-t border-neutral-800 bg-neutral-950/30 px-5 py-4"
			transition:slide={{ duration: 200 }}
		>
			{#if actionType === 'create'}
				<!-- Create Item: Editable fields (compact styling) -->
				<div class="space-y-2.5">
					<div>
						<label for="create-name-{approval.id}" class="label-sm">Name</label>
						<input
							type="text"
							id="create-name-{approval.id}"
							bind:value={editedName}
							placeholder="Item name"
							class="input-sm"
							disabled={isProcessing}
						/>
					</div>

					<div>
						<label for="create-qty-{approval.id}" class="label-sm">Quantity</label>
						<input
							type="number"
							id="create-qty-{approval.id}"
							min="1"
							bind:value={editedQuantity}
							class="input-sm w-20"
							disabled={isProcessing}
						/>
					</div>

					<div>
						<label for="create-desc-{approval.id}" class="label-sm">Description</label>
						<textarea
							id="create-desc-{approval.id}"
							bind:value={editedDescription}
							placeholder="Optional description"
							rows="2"
							class="input-sm resize-none"
							disabled={isProcessing}
						></textarea>
					</div>

					<!-- Location Selector -->
					<div>
						<label for="create-loc-{approval.id}" class="label-sm">Location</label>
						{#if locationStore.flatList.length > 0}
							<select
								id="create-loc-{approval.id}"
								bind:value={editedLocationId}
								class="input-sm"
								disabled={isProcessing}
							>
								<option value="">Select location...</option>
								{#each locationStore.flatList as loc (loc.location.id)}
									<option value={loc.location.id}>{loc.path}</option>
								{/each}
							</select>
						{:else}
							<div class="rounded-lg bg-neutral-800/50 px-2.5 py-1.5">
								<span class="text-sm text-neutral-300"
									>{approval.display_info?.location ?? 'No location'}</span
								>
							</div>
						{/if}
					</div>

					<div>
						<label for="create-notes-{approval.id}" class="label-sm">Notes</label>
						<textarea
							id="create-notes-{approval.id}"
							bind:value={editedNotes}
							placeholder="Optional notes"
							rows="2"
							class="input-sm resize-none"
							disabled={isProcessing}
						></textarea>
					</div>

					<!-- Tags/Labels -->
					{#if labelStore.labels.length > 0}
						<div>
							<span class="label-sm">Tags</span>
							<div class="flex flex-wrap gap-1.5" role="group" aria-label="Select labels">
								{#each labelStore.labels as label (label.id)}
									{@const isSelected = editedLabelIds.includes(label.id)}
									<button
										type="button"
										class={isSelected ? 'label-chip-selected' : 'label-chip'}
										onclick={() => toggleLabel(label.id)}
										disabled={isProcessing}
									>
										{label.name}
									</button>
								{/each}
							</div>
						</div>
					{/if}

					{#if hasModifications}
						<p class="text-xs text-primary-400">You have unsaved modifications</p>
					{/if}
				</div>
			{:else if actionType === 'update'}
				<!-- Update Item: Show only fields being changed (compact styling) -->
				<div class="space-y-2.5">
					{#if approval.display_info?.item_name}
						<div class="rounded-lg bg-neutral-800/50 px-2.5 py-1.5">
							<span class="text-xs text-neutral-500">Updating:</span>
							<span class="ml-1 text-sm text-neutral-300">{approval.display_info.item_name}</span>
							{#if approval.display_info.asset_id}
								<span class="text-xs text-neutral-500">({approval.display_info.asset_id})</span>
							{/if}
						</div>
					{/if}

					{#if fieldsBeingChanged.includes('name')}
						<div>
							<label for="update-name-{approval.id}" class="label-sm">New Name</label>
							<input
								type="text"
								id="update-name-{approval.id}"
								bind:value={editedName}
								placeholder="Item name"
								class="input-sm"
								disabled={isProcessing}
							/>
						</div>
					{/if}

					{#if fieldsBeingChanged.includes('quantity')}
						<div>
							<label for="update-qty-{approval.id}" class="label-sm">New Quantity</label>
							<input
								type="number"
								id="update-qty-{approval.id}"
								min="1"
								bind:value={editedQuantity}
								class="input-sm w-20"
								disabled={isProcessing}
							/>
						</div>
					{/if}

					{#if fieldsBeingChanged.includes('description')}
						<div>
							<label for="update-desc-{approval.id}" class="label-sm">New Description</label>
							<textarea
								id="update-desc-{approval.id}"
								bind:value={editedDescription}
								placeholder="Description"
								rows="2"
								class="input-sm resize-none"
								disabled={isProcessing}
							></textarea>
						</div>
					{/if}

					{#if fieldsBeingChanged.includes('location')}
						<div>
							<label for="update-loc-{approval.id}" class="label-sm">New Location</label>
							{#if locationStore.flatList.length > 0}
								<select
									id="update-loc-{approval.id}"
									bind:value={editedLocationId}
									class="input-sm"
									disabled={isProcessing}
								>
									<option value="">Select location...</option>
									{#each locationStore.flatList as loc (loc.location.id)}
										<option value={loc.location.id}>{loc.path}</option>
									{/each}
								</select>
							{:else}
								<div class="rounded-lg bg-neutral-800/50 px-2.5 py-1.5">
									<span class="text-sm text-neutral-300"
										>{approval.display_info?.location ?? approval.parameters.location_id}</span
									>
								</div>
							{/if}
						</div>
					{/if}

					{#if fieldsBeingChanged.includes('notes')}
						<div>
							<label for="update-notes-{approval.id}" class="label-sm">New Notes</label>
							<textarea
								id="update-notes-{approval.id}"
								bind:value={editedNotes}
								placeholder="Notes"
								rows="2"
								class="input-sm resize-none"
								disabled={isProcessing}
							></textarea>
						</div>
					{/if}

					{#if fieldsBeingChanged.includes('labels')}
						{#if labelStore.labels.length > 0}
							<div>
								<span class="label-sm">New Tags</span>
								<div class="flex flex-wrap gap-1.5" role="group" aria-label="Select labels">
									{#each labelStore.labels as label (label.id)}
										{@const isSelected = editedLabelIds.includes(label.id)}
										<button
											type="button"
											class={isSelected ? 'label-chip-selected' : 'label-chip'}
											onclick={() => toggleLabel(label.id)}
											disabled={isProcessing}
										>
											{label.name}
										</button>
									{/each}
								</div>
							</div>
						{/if}
					{/if}

					{#if fieldsBeingChanged.length === 0}
						<p class="text-sm text-neutral-500">No specific fields to edit.</p>
					{/if}

					{#if hasModifications}
						<p class="text-xs text-primary-400">You have unsaved modifications</p>
					{/if}
				</div>
			{:else if actionType === 'delete'}
				<!-- Delete Item: Read-only verification -->
				<div class="space-y-2">
					<p class="text-sm text-neutral-400">
						Are you sure you want to delete this item? This action cannot be undone.
					</p>
					<div class="space-y-1 rounded-lg border border-error-500/20 bg-error-500/10 px-3 py-2">
						{#if approval.display_info?.item_name}
							<div>
								<span class="text-xs text-neutral-500">Item:</span>
								<span class="text-error-300 ml-1 text-sm">{approval.display_info.item_name}</span>
							</div>
						{/if}
						{#if approval.display_info?.asset_id}
							<div>
								<span class="text-xs text-neutral-500">Asset ID:</span>
								<span class="ml-1 text-sm text-neutral-300">{approval.display_info.asset_id}</span>
							</div>
						{/if}
						{#if approval.display_info?.location}
							<div>
								<span class="text-xs text-neutral-500">Location:</span>
								<span class="ml-1 text-sm text-neutral-300">{approval.display_info.location}</span>
							</div>
						{/if}
						{#if !approval.display_info?.item_name}
							<div>
								<span class="text-xs text-neutral-500">Item ID:</span>
								<span class="ml-1 text-sm text-neutral-300">{approval.parameters.item_id}</span>
							</div>
						{/if}
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>
