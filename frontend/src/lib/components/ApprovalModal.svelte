<script lang="ts">
	/**
	 * ApprovalModal - Modal for batch approval of pending actions
	 *
	 * Displays all pending approvals in a clean, scannable list with
	 * individual and bulk approve/reject actions.
	 * Supports expanding items to view details or edit parameters.
	 */
	import { SvelteSet } from 'svelte/reactivity';
	import type { PendingApproval } from '../api/chat';
	import { chatStore } from '../stores/chat.svelte';
	import { showToast } from '../stores/ui.svelte';
	import Button from './Button.svelte';
	import ApprovalItemPanel from './ApprovalItemPanel.svelte';

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

	async function handleApprove(approvalId: string, modifiedParams?: Record<string, unknown>) {
		addProcessingId(approvalId);
		try {
			await chatStore.approveAction(approvalId, modifiedParams);
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
		// Note: Bulk approve uses original parameters, not any user edits in expanded panels.
		// This is intentional - users should use individual approve for edited items.
		// Capture IDs upfront since approvals array mutates as items are processed.
		const ids = approvals.map((a) => a.id);
		ids.forEach((id) => processingIds.add(id));

		// Process each item individually to handle partial failures gracefully
		for (const id of ids) {
			try {
				await chatStore.approveAction(id);
			} catch {
				// Error is already captured in chatStore.error - continue with remaining items
			} finally {
				processingIds.delete(id);
			}
		}
	}

	async function handleRejectAll() {
		// Capture IDs upfront since approvals array mutates as items are processed.
		const ids = approvals.map((a) => a.id);
		ids.forEach((id) => processingIds.add(id));

		// Process each item individually to handle partial failures gracefully
		for (const id of ids) {
			try {
				await chatStore.rejectAction(id);
			} catch {
				// Error is already captured in chatStore.error - continue with remaining items
			} finally {
				processingIds.delete(id);
			}
		}
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

	// Handle approval expiration - show toast, clear approvals, and close modal when countdown reaches 0
	$effect(() => {
		if (open && countdownSeconds === 0 && approvals.length > 0) {
			showToast('Pending actions have expired', 'warning');
			chatStore.clearExpiredApprovals();
			handleClose();
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
			<div class="max-h-96 divide-y divide-neutral-800 overflow-y-auto">
				{#each approvals as approval (approval.id)}
					<ApprovalItemPanel
						{approval}
						isProcessing={processingIds.has(approval.id)}
						onApprove={handleApprove}
						onReject={handleReject}
					/>
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
