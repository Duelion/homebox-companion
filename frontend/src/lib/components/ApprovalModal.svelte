<script lang="ts">
	/**
	 * ApprovalModal - Modal for batch approval of pending actions
	 *
	 * Displays all pending approvals in a clean, scannable list with
	 * individual and bulk approve/reject actions.
	 */
	import type { PendingApproval } from '../api/chat';
	import { chatStore } from '../stores/chat.svelte';
	import Button from './Button.svelte';

	interface Props {
		open: boolean;
		approvals: PendingApproval[];
		onclose?: () => void;
	}

	let { open = $bindable(), approvals, onclose }: Props = $props();

	let processingIds = $state<Set<string>>(new Set());
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
		if (e.key === 'Escape') {
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
		processingIds = new Set([...processingIds, id]);
	}

	function removeProcessingId(id: string) {
		const next = new Set(processingIds);
		next.delete(id);
		processingIds = next;
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
		processingIds = new Set(ids);
		try {
			// Process sequentially to avoid race conditions and provide better UX
			for (const id of ids) {
				await chatStore.approveAction(id);
			}
		} finally {
			processingIds = new Set();
		}
	}

	async function handleRejectAll() {
		const ids = approvals.map((a) => a.id);
		processingIds = new Set(ids);
		try {
			// Process sequentially to avoid race conditions and provide better UX
			for (const id of ids) {
				await chatStore.rejectAction(id);
			}
		} finally {
			processingIds = new Set();
		}
	}

	// Format parameter for display (truncate long values)
	function formatParam(key: string, value: unknown): string {
		const str = typeof value === 'string' ? value : JSON.stringify(value);
		const truncated = str.length > 32 ? str.slice(0, 29) + '...' : str;
		return `${key}: ${truncated}`;
	}

	// Check if any approvals remain - close modal with small delay for visual feedback
	$effect(() => {
		if (open && approvals.length === 0 && !isProcessingAny) {
			const timeout = setTimeout(() => {
				handleClose();
			}, 300);
			return () => clearTimeout(timeout);
		}
	});

	const isProcessingAny = $derived(processingIds.size > 0);
</script>

<!-- Only listen for Escape when modal is open -->
{#if open}
	<svelte:window onkeydown={handleKeydown} />
{/if}

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
				<button
					type="button"
					class="btn-icon"
					onclick={handleClose}
					aria-label="Close"
				>
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
					<div
						class="flex items-start gap-3 px-5 py-4 transition-colors {approval.is_expired
							? 'opacity-50'
							: ''}"
					>
						<!-- Tool Info -->
						<div class="min-w-0 flex-1">
							<code
								class="inline-block rounded-lg border border-neutral-700/50 bg-neutral-800/80 px-2 py-1 font-mono text-sm text-neutral-200"
							>
								{approval.tool_name}
							</code>
							{#if Object.keys(approval.parameters).length > 0}
								<div class="mt-2 space-y-0.5">
									{#each Object.entries(approval.parameters).slice(0, 2) as [key, value]}
										<p class="truncate font-mono text-xs text-neutral-500">
											{formatParam(key, value)}
										</p>
									{/each}
									{#if Object.keys(approval.parameters).length > 2}
										<p class="text-xs text-neutral-600">
											+{Object.keys(approval.parameters).length - 2} more
										</p>
									{/if}
								</div>
							{/if}
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

