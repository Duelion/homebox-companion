<script lang="ts">
	/**
	 * ApprovalItemPanel - Expandable panel for viewing/editing a pending approval action
	 *
	 * Supports three action types across items, labels, and locations:
	 * - create: Full editable form (items get extended fields, labels/locations get name + description)
	 * - update: Shows only fields being changed (editable)
	 * - delete: Read-only verification view with entity-specific labeling
	 */
	import { slide } from 'svelte/transition';
	import type { PendingApproval } from '../api/chat';
	import {
		ItemCoreFields,
		ItemExtendedFields,
		LabelSelector,
		LocationSelector,
		UpdateFieldEditor,
	} from './form';

	type ActionType = 'delete' | 'create' | 'update';

	// Fallback action type mapping for backwards compatibility (before backend sends action_type)
	const FALLBACK_ACTION_TYPE_MAP: Record<string, ActionType> = {
		delete_item: 'delete',
		delete_label: 'delete',
		delete_location: 'delete',
		create_item: 'create',
		create_label: 'create',
		create_location: 'create',
	};

	/**
	 * Get action type from display_info (preferred) or derive from tool name (fallback).
	 * The backend now provides action_type in display_info, but we keep the fallback
	 * for backwards compatibility with older sessions.
	 */
	function getActionType(toolName: string, displayInfo?: { action_type?: ActionType }): ActionType {
		// Prefer backend-provided action_type
		if (displayInfo?.action_type) {
			return displayInfo.action_type;
		}
		// Fallback to map, then default to 'update'
		return FALLBACK_ACTION_TYPE_MAP[toolName] ?? 'update';
	}

	interface Props {
		approval: PendingApproval;
		isProcessing: boolean;
		onApprove: (approvalId: string, modifiedParams?: Record<string, unknown>) => void;
		onReject: (approvalId: string) => void;
		expanded?: boolean;
		onToggleExpand?: () => void;
		onParamsChange?: (
			approvalId: string,
			modifiedParams: Record<string, unknown> | undefined
		) => void;
	}

	let {
		approval,
		isProcessing,
		onApprove,
		onReject,
		expanded = false,
		onToggleExpand,
		onParamsChange,
	}: Props = $props();

	// UI state
	let showExtendedFields = $state(false);
	let processingAction = $state<'approve' | 'reject' | null>(null);

	// Core fields state
	let editedName = $state('');
	let editedDescription = $state<string | null>('');
	let editedQuantity = $state(1);
	let editedLocationId = $state('');
	let editedLabelIds = $state<string[]>([]);
	let editedNotes = $state<string | null>('');

	// Extended fields state
	let editedManufacturer = $state<string | null>(null);
	let editedModelNumber = $state<string | null>(null);
	let editedSerialNumber = $state<string | null>(null);
	let editedPurchasePrice = $state<number | null>(null);
	let editedPurchaseFrom = $state<string | null>(null);

	// Label fields state (for update_label)
	let editedColor = $state<string | null>(null);

	// Location fields state (for update_location)
	let editedParentId = $state<string | null>(null);

	// Helper to safely extract original values from approval parameters
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
	const originalManufacturer = $derived(
		(approval.parameters.manufacturer as string | undefined) ?? null
	);
	const originalModelNumber = $derived(
		(approval.parameters.model_number as string | undefined) ?? null
	);
	const originalSerialNumber = $derived(
		(approval.parameters.serial_number as string | undefined) ?? null
	);
	const originalPurchasePrice = $derived(
		(approval.parameters.purchase_price as number | undefined) ?? null
	);
	const originalPurchaseFrom = $derived(
		(approval.parameters.purchase_from as string | undefined) ?? null
	);

	// Label field originals (for update_label)
	const originalColor = $derived((approval.parameters.color as string | undefined) ?? null);

	// Location field originals (for update_location)
	const originalParentId = $derived((approval.parameters.parent_id as string | undefined) ?? null);

	// Track which approval we've initialized for
	let initializedForApprovalId = $state<string | null>(null);

	// Initialize edited values when expanded, reset when approval changes
	$effect(() => {
		const currentApprovalId = approval.id;

		// Reset if approval changed
		if (initializedForApprovalId !== null && initializedForApprovalId !== currentApprovalId) {
			initializedForApprovalId = null;
			showExtendedFields = false;
		}

		// Initialize when first expanded for this approval
		if (expanded && initializedForApprovalId !== currentApprovalId) {
			// Core fields
			editedName = originalName;
			editedDescription = originalDescription;
			editedQuantity = originalQuantity;
			editedNotes = originalNotes;
			editedLabelIds = [...originalLabelIds];
			editedLocationId = originalLocationId;
			// Extended fields
			editedManufacturer = originalManufacturer;
			editedModelNumber = originalModelNumber;
			editedSerialNumber = originalSerialNumber;
			editedPurchasePrice = originalPurchasePrice;
			editedPurchaseFrom = originalPurchaseFrom;
			// Label fields
			editedColor = originalColor;
			// Location fields
			editedParentId = originalParentId;
			// Auto-expand if any extended field has data
			showExtendedFields = hasAnyExtendedData();
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
	// Prefers backend-provided action_type, falls back to tool name derivation
	const actionType = $derived(getActionType(approval.tool_name, approval.display_info));

	// Get human-readable action description
	const actionDescription = $derived.by(() => {
		const toolName = approval.tool_name;
		const info = approval.display_info;
		const params = approval.parameters;

		// Use generic target_name if available (unified field from backend)
		if (info?.target_name) return info.target_name;

		// Items - fallback to item_name for backward compatibility
		if (toolName === 'delete_item') return info?.item_name ?? 'Delete item';
		if (toolName === 'update_item') return info?.item_name ?? 'Update item';
		if (toolName === 'create_item') return info?.item_name ?? 'New item';
		// Labels - use params.name as fallback since labels don't have display_info
		if (toolName === 'create_label') return (params?.name as string) ?? 'New label';
		if (toolName === 'update_label') return (params?.name as string) ?? 'Update label';
		if (toolName === 'delete_label') return (params?.name as string) ?? 'Delete label';
		// Locations
		if (toolName === 'create_location') return (params?.name as string) ?? 'New location';
		if (toolName === 'update_location') return (params?.name as string) ?? 'Update location';
		if (toolName === 'delete_location') return (params?.name as string) ?? 'Delete location';

		return toolName.replace(/_/g, ' ');
	});

	// Determine entity type from tool name for proper labeling
	const entityType = $derived.by(() => {
		if (approval.tool_name.endsWith('_item')) return 'item';
		if (approval.tool_name.endsWith('_label')) return 'label';
		if (approval.tool_name.endsWith('_location')) return 'location';
		return 'item';
	});

	// Get the correct ID parameter based on entity type
	const entityIdParam = $derived.by(() => {
		if (entityType === 'label') return (approval.parameters.label_id as string) ?? 'Unknown';
		if (entityType === 'location') return (approval.parameters.location_id as string) ?? 'Unknown';
		return (approval.parameters.item_id as string) ?? 'Unknown';
	});

	// Check which fields are being changed (for update actions)
	const fieldsBeingChanged = $derived.by(() => {
		if (actionType !== 'update') return [];
		const fields: string[] = [];
		if (approval.parameters.name !== undefined) fields.push('name');
		if (approval.parameters.description !== undefined) fields.push('description');
		if (approval.parameters.quantity !== undefined) fields.push('quantity');
		if (approval.parameters.notes !== undefined) fields.push('notes');
		if (approval.parameters.label_ids !== undefined) fields.push('labels');
		// Only add 'location' for item tools, not for location tools
		// (update_location uses location_id as the entity identifier, not a field to change)
		// Using endsWith('_location') for defensive future-proofing against new location tools
		if (
			approval.parameters.location_id !== undefined &&
			!approval.tool_name.endsWith('_location')
		) {
			fields.push('location');
		}
		// Extended fields
		if (approval.parameters.manufacturer !== undefined) fields.push('manufacturer');
		if (approval.parameters.model_number !== undefined) fields.push('model_number');
		if (approval.parameters.serial_number !== undefined) fields.push('serial_number');
		if (approval.parameters.purchase_price !== undefined) fields.push('purchase_price');
		if (approval.parameters.purchase_from !== undefined) fields.push('purchase_from');
		// Label fields (for update_label)
		if (approval.parameters.color !== undefined) fields.push('color');
		// Location fields (for update_location)
		if (approval.parameters.parent_id !== undefined) fields.push('parent_id');
		return fields;
	});

	// Helper to compare string arrays
	function arraysEqual(a: string[], b: string[]): boolean {
		if (a.length !== b.length) return false;
		const sortedA = [...a].sort();
		const sortedB = [...b].sort();
		return sortedA.every((val, i) => val === sortedB[i]);
	}

	// Check if any extended field has data in original params
	function hasAnyExtendedData(): boolean {
		return !!(
			originalManufacturer ||
			originalModelNumber ||
			originalSerialNumber ||
			originalPurchasePrice ||
			originalPurchaseFrom
		);
	}

	// Shared helper: check if a field can be modified based on action type
	const allowedFields = $derived(new Set(fieldsBeingChanged));
	function canModifyField(field: string): boolean {
		return actionType !== 'update' || allowedFields.has(field);
	}

	// Check if user has modified any editable parameters
	const hasModifications = $derived.by(() => {
		if (actionType === 'delete') return false;

		return (
			(canModifyField('name') && editedName !== originalName) ||
			(canModifyField('description') && editedDescription !== originalDescription) ||
			(canModifyField('quantity') && editedQuantity !== originalQuantity) ||
			(canModifyField('notes') && editedNotes !== originalNotes) ||
			(canModifyField('labels') && !arraysEqual(editedLabelIds, originalLabelIds)) ||
			(canModifyField('location') && editedLocationId !== originalLocationId) ||
			(canModifyField('manufacturer') && editedManufacturer !== originalManufacturer) ||
			(canModifyField('model_number') && editedModelNumber !== originalModelNumber) ||
			(canModifyField('serial_number') && editedSerialNumber !== originalSerialNumber) ||
			(canModifyField('purchase_price') && editedPurchasePrice !== originalPurchasePrice) ||
			(canModifyField('purchase_from') && editedPurchaseFrom !== originalPurchaseFrom) ||
			(canModifyField('color') && editedColor !== originalColor) ||
			(canModifyField('parent_id') && editedParentId !== originalParentId)
		);
	});

	// Build modified parameters object (only changed fields)
	function getModifiedParams(): Record<string, unknown> | undefined {
		if (!hasModifications) return undefined;

		const mods: Record<string, unknown> = {};

		if (editedName !== originalName && canModifyField('name')) mods.name = editedName;
		if (editedDescription !== originalDescription && canModifyField('description'))
			mods.description = editedDescription;
		if (editedQuantity !== originalQuantity && canModifyField('quantity'))
			mods.quantity = editedQuantity;
		if (editedNotes !== originalNotes && canModifyField('notes')) mods.notes = editedNotes;
		if (!arraysEqual(editedLabelIds, originalLabelIds) && canModifyField('labels'))
			mods.label_ids = editedLabelIds;
		if (editedLocationId !== originalLocationId && canModifyField('location'))
			mods.location_id = editedLocationId;
		if (editedManufacturer !== originalManufacturer && canModifyField('manufacturer'))
			mods.manufacturer = editedManufacturer;
		if (editedModelNumber !== originalModelNumber && canModifyField('model_number'))
			mods.model_number = editedModelNumber;
		if (editedSerialNumber !== originalSerialNumber && canModifyField('serial_number'))
			mods.serial_number = editedSerialNumber;
		if (editedPurchasePrice !== originalPurchasePrice && canModifyField('purchase_price'))
			mods.purchase_price = editedPurchasePrice;
		if (editedPurchaseFrom !== originalPurchaseFrom && canModifyField('purchase_from'))
			mods.purchase_from = editedPurchaseFrom;
		if (editedColor !== originalColor && canModifyField('color')) mods.color = editedColor;
		if (editedParentId !== originalParentId && canModifyField('parent_id'))
			mods.parent_id = editedParentId;

		return Object.keys(mods).length > 0 ? mods : undefined;
	}

	// Notify parent when modifications change (for Approve All functionality)
	// Only notify after the panel has been initialized to avoid false positives
	$effect(() => {
		if (onParamsChange && initializedForApprovalId === approval.id) {
			const currentMods = getModifiedParams();
			onParamsChange(approval.id, currentMods);
		}
	});

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
		if (onToggleExpand) {
			onToggleExpand();
		}
	}

	function toggleExtendedFieldsPanel() {
		showExtendedFields = !showExtendedFields;
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
			<p class="text-sm font-medium text-neutral-200">
				<span
					class="mr-1.5 text-xs font-semibold uppercase tracking-wide {actionType === 'delete'
						? 'text-error-400'
						: actionType === 'create'
							? 'text-success-400'
							: 'text-warning-400'}"
				>
					{actionType}:
				</span>
				<span class={actionType === 'delete' ? 'text-error-300' : ''}>
					{actionDescription}
				</span>
			</p>
		</div>

		<!-- Action Buttons -->
		<div class="flex shrink-0 gap-1.5">
			<!-- Expand/Edit Button -->
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
				class="flex h-9 w-9 items-center justify-center rounded-lg border transition-all disabled:opacity-50 {expanded &&
				hasModifications
					? 'border-primary-500/50 bg-primary-500/20 text-primary-400 shadow-primary-glow-sm hover:border-primary-400 hover:bg-primary-500/30 hover:text-primary-300'
					: 'border-neutral-700 bg-neutral-800 text-neutral-400 hover:border-success-500/50 hover:bg-success-500/10 hover:text-success-500'}"
				disabled={isProcessing || approval.is_expired}
				onclick={handleApprove}
				aria-label={expanded && hasModifications ? 'Approve with your changes' : 'Approve'}
				title={expanded && hasModifications ? 'Apply your edits and approve' : 'Approve action'}
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
				{#if approval.tool_name === 'create_item'}
					<!-- Create Item: Full editable form -->
					<div class="space-y-3">
						<ItemCoreFields
							bind:name={editedName}
							bind:quantity={editedQuantity}
							bind:description={editedDescription}
							size="sm"
							disabled={isProcessing}
							idPrefix="create-{approval.id}"
						/>

						<LocationSelector
							bind:value={editedLocationId}
							size="sm"
							disabled={isProcessing}
							idPrefix="create-{approval.id}"
							fallbackDisplay={approval.display_info?.location ?? 'No location'}
						/>

						<LabelSelector
							selectedIds={editedLabelIds}
							size="sm"
							disabled={isProcessing}
							onToggle={toggleLabel}
						/>

						<ItemExtendedFields
							bind:manufacturer={editedManufacturer}
							bind:modelNumber={editedModelNumber}
							bind:serialNumber={editedSerialNumber}
							bind:purchasePrice={editedPurchasePrice}
							bind:purchaseFrom={editedPurchaseFrom}
							bind:notes={editedNotes}
							expanded={showExtendedFields}
							size="sm"
							disabled={isProcessing}
							idPrefix="create-{approval.id}"
							onToggle={toggleExtendedFieldsPanel}
						/>
					</div>
				{:else}
					<!-- Create Label/Location: Restricted form (Name + Description only) -->
					<div class="space-y-3">
						<div>
							<label for="create-name-{approval.id}" class="label-sm">Name</label>
							<input
								type="text"
								id="create-name-{approval.id}"
								bind:value={editedName}
								placeholder="Name"
								class="input-sm"
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
					</div>
				{/if}
			{:else if actionType === 'update'}
				<!-- Update Entity: Using extracted UpdateFieldEditor component -->
				<UpdateFieldEditor
					{fieldsBeingChanged}
					idPrefix="update-{approval.id}"
					disabled={isProcessing}
					displayInfo={approval.display_info}
					fallbackLocationId={approval.parameters.location_id as string}
					bind:name={editedName}
					bind:quantity={editedQuantity}
					bind:description={editedDescription}
					bind:notes={editedNotes}
					bind:locationId={editedLocationId}
					bind:labelIds={editedLabelIds}
					bind:manufacturer={editedManufacturer}
					bind:modelNumber={editedModelNumber}
					bind:serialNumber={editedSerialNumber}
					bind:purchasePrice={editedPurchasePrice}
					bind:purchaseFrom={editedPurchaseFrom}
					bind:color={editedColor}
					bind:parentId={editedParentId}
					onToggleLabel={toggleLabel}
				/>
			{:else if actionType === 'delete'}
				<!-- Delete Entity: Read-only verification -->
				<div class="space-y-2">
					<p class="text-sm text-neutral-400">
						Are you sure you want to delete this {entityType}? This action cannot be undone.
					</p>
					<div class="space-y-1 rounded-lg border border-error-500/20 bg-error-500/10 px-3 py-2">
						{#if approval.display_info?.target_name || approval.display_info?.item_name}
							<div>
								<span class="text-xs capitalize text-neutral-500">{entityType}:</span>
								<span class="text-error-300 ml-1 text-sm"
									>{approval.display_info.target_name ?? approval.display_info.item_name}</span
								>
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
						{#if !approval.display_info?.target_name && !approval.display_info?.item_name}
							<div>
								<span class="text-xs capitalize text-neutral-500">{entityType} ID:</span>
								<span class="ml-1 text-sm text-neutral-300">{entityIdParam}</span>
							</div>
						{/if}
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>
