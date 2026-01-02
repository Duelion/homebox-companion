<script lang="ts">
	/**
	 * ApprovalModal - Modal for batch approval of pending actions
	 *
	 * Displays all pending approvals in a clean, scannable list with
	 * individual and bulk approve/reject actions.
	 * Now shows human-readable display info (item name, location, etc.)
	 */
	import { SvelteSet } from 'svelte/reactivity';
	import type { PendingApproval } from '../api/chat';
	import { chatStore } from '../stores/chat.svelte';
	import Button from './Button.svelte';

	interface Props {
		open: boolean;
		approvals: PendingApproval[];
		onclose?: () => void;
	}

	let { open = $bindable(), approvals, onclose }: Props = $props();

	let processingIds = new SvelteSet<string>();
	let now = $state(Date.now());

	// Live countdown timer
	$effect(() => {
		if (!open || approvals.length === 0) return;

		const interval = setInterval(() => {
			now = Date.now();
		}, 1000);

		return () => clearInterval(interval);
	});

	function handleClose() {
		open = false;
		onclose?.();
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			handleClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (open && e.key === 'Escape') {
			handleClose();
		}
	}

	// Get earliest expiry time for header countdown
	const earliestExpiry = $derived.by(() => {
		const validExpiries = approvals
			.filter((a) => a.expires_at && !a.is_expired)
			.map((a) => new Date(a.expires_at!).getTime());
		if (validExpiries.length === 0) return null;
		return Math.min(...validExpiries);
	});

	const countdownSeconds = $derived.by(() => {
		if (!earliestExpiry) return null;
		return Math.max(0, Math.floor((earliestExpiry - now) / 1000));
	});

	function addProcessingId(id: string) {
		processingIds.add(id);
	}

	function removeProcessingId(id: string) {
		processingIds.delete(id);
	}

	async function handleApprove(approvalId: string) {
		addProcessingId(approvalId);
		try {
			await chatStore.approveAction(approvalId);
		} finally {
			removeProcessingId(approvalId);
		}
	}

	async function handleReject(approvalId: string) {
		addProcessingId(approvalId);
		try {
			await chatStore.rejectAction(approvalId);
		} finally {
			removeProcessingId(approvalId);
		}
	}

	async function handleApproveAll() {
		const ids = approvals.map((a) => a.id);
		ids.forEach((id) => processingIds.add(id));
		try {
			for (const id of ids) {
				await chatStore.approveAction(id);
			}
		} finally {
			processingIds.clear();
		}
	}

	async function handleRejectAll() {
		const ids = approvals.map((a) => a.id);
		ids.forEach((id) => processingIds.add(id));
		try {
			for (const id of ids) {
				await chatStore.rejectAction(id);
			}
		} finally {
			processingIds.clear();
		}
	}

	// Get human-readable action description
	function getActionDescription(approval: PendingApproval): string {
		const toolName = approval.tool_name;
		const info = approval.display_info;

		if (toolName === 'delete_item') {
			if (info?.item_name) {
				let desc = `Delete "${info.item_name}"`;
				if (info.asset_id) desc += ` (${info.asset_id})`;
				if (info.location) desc += ` from ${info.location}`;
				return desc;
			}
			return 'Delete item';
		}

		if (toolName === 'update_item') {
			if (info?.item_name) {
				let desc = `Update "${info.item_name}"`;
				if (info.asset_id) desc += ` (${info.asset_id})`;
				return desc;
			}
			return 'Update item';
		}

		if (toolName === 'create_item') {
			if (info?.item_name) {
				let desc = `Create "${info.item_name}"`;
				if (info.location) desc += ` in ${info.location}`;
				return desc;
			}
			return 'Create new item';
		}

		// Fallback: format tool name
		return toolName.replace(/_/g, ' ');
	}

	// Get action type for styling
	function getActionType(toolName: string): 'delete' | 'create' | 'update' {
		if (toolName === 'delete_item') return 'delete';
		if (toolName === 'create_item') return 'create';
		if (toolName === 'update_item') return 'update';
		// Default to 'update' styling for other write tools (e.g., ensure_asset_ids)
		return 'update';
	}

	const isProcessingAny = $derived(processingIds.size > 0);

	// Check if any approvals remain - close modal with small delay for visual feedback
	$effect(() => {
		if (open && approvals.length === 0 && !isProcessingAny) {
			const timeout = setTimeout(() => {
				handleClose();
			}, 300);
			return () => clearTimeout(timeout);
		}
	});
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open && approvals.length > 0}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
		onclick={handleBackdropClick}
	>
		<div
			class="flex w-full max-w-md animate-scale-in flex-col overflow-hidden rounded-2xl border border-warning-500/30 bg-neutral-900 shadow-xl"
		>
			<!-- Header -->
			<div
				class="flex items-center gap-3 border-b border-warning-500/20 bg-warning-500/10 px-5 py-4"
			>
				<div class="flex h-10 w-10 items-center justify-center rounded-xl bg-warning-500/20">
					<svg
						class="h-5 w-5 text-warning-500"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
						/>
					</svg>
				</div>
				<div class="flex-1">
					<h3 class="text-h4 text-neutral-100">
						{approvals.length}
						{approvals.length === 1 ? 'Action' : 'Actions'} Require Approval
					</h3>
					{#if countdownSeconds !== null}
						<p class="text-body-sm text-warning-500/80">
							Expires in {countdownSeconds}s
						</p>
					{/if}
				</div>
				<button type="button" class="btn-icon" onclick={handleClose} aria-label="Close">
					<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M6 18L18 6M6 6l12 12"
						/>
					</svg>
				</button>
			</div>

			<!-- Approval List -->
			<div class="max-h-80 divide-y divide-neutral-800 overflow-y-auto">
				{#each approvals as approval (approval.id)}
					{@const isProcessing = processingIds.has(approval.id)}
					{@const actionType = getActionType(approval.tool_name)}
					<div
						class="flex items-start gap-3 px-5 py-4 transition-colors {approval.is_expired
							? 'opacity-50'
							: ''}"
					>
						<!-- Action Icon -->
						<div
							class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl {actionType ===
							'delete'
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
								{getActionDescription(approval)}
							</p>
							<p class="mt-0.5 text-xs text-neutral-500">
								{approval.tool_name}
							</p>
						</div>

						<!-- Individual Actions -->
						<div class="flex shrink-0 gap-1.5">
							<button
								type="button"
								class="flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-700 bg-neutral-800 text-neutral-400 transition-all hover:border-error-500/50 hover:bg-error-500/10 hover:text-error-500 disabled:opacity-50"
								disabled={isProcessing || approval.is_expired}
								onclick={() => handleReject(approval.id)}
								aria-label="Reject"
							>
								{#if isProcessing}
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
							<button
								type="button"
								class="flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-700 bg-neutral-800 text-neutral-400 transition-all hover:border-success-500/50 hover:bg-success-500/10 hover:text-success-500 disabled:opacity-50"
								disabled={isProcessing || approval.is_expired}
								onclick={() => handleApprove(approval.id)}
								aria-label="Approve"
							>
								{#if isProcessing}
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
				{/each}
			</div>

			<!-- Footer with Bulk Actions -->
			<div class="flex gap-3 border-t border-neutral-800 bg-neutral-950/50 px-5 py-4">
				<Button
					variant="secondary"
					size="sm"
					full
					disabled={isProcessingAny}
					loading={isProcessingAny}
					onclick={handleRejectAll}
				>
					Reject All
				</Button>
				<Button
					variant="warning"
					size="sm"
					full
					disabled={isProcessingAny}
					loading={isProcessingAny}
					onclick={handleApproveAll}
				>
					Approve All
				</Button>
			</div>
		</div>
	</div>
{/if}
