<script lang="ts">
	/**
	 * RecoveryBanner - Prompts user to recover a crashed session
	 *
	 * Shown when a recoverable session is detected (e.g., after page reload mid-workflow).
	 * Provides options to resume the session or start fresh.
	 */
	import { RefreshCw, ImageIcon, CheckSquare, Play } from 'lucide-svelte';
	import type { SessionSummary } from '$lib/services/sessionPersistence';
	import Button from './Button.svelte';

	interface Props {
		/** Summary of the recoverable session */
		summary: SessionSummary;
		/** Callback when user chooses to resume the session */
		onResume: () => void;
		/** Callback when user chooses to dismiss and start fresh */
		onDismiss: () => void;
		/** Whether a recovery operation is in progress */
		loading?: boolean;
	}

	let { summary, onResume, onDismiss, loading = false }: Props = $props();

	// Human-readable status
	function getStatusText(status: string): string {
		switch (status) {
			case 'location':
				return 'selecting a location';
			case 'capturing':
				return 'capturing photos';
			case 'analyzing':
				return 'analyzing photos';
			case 'partial_analysis':
				return 'analyzing photos';
			case 'reviewing':
				return 'reviewing items';
			case 'confirming':
				return 'confirming items';
			case 'submitting':
				return 'submitting items';
			default:
				return 'in progress';
		}
	}
</script>

<div
	class="mb-4 overflow-hidden rounded-xl border border-primary-500/30 bg-primary-500/10 shadow-lg"
	role="alert"
	aria-live="polite"
>
	<div class="p-4">
		<!-- Header -->
		<div class="mb-3 flex items-start gap-3">
			<!-- Recovery icon -->
			<div
				class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-500/20"
			>
				<RefreshCw class="text-primary-400" size={20} strokeWidth={1.5} />
			</div>

			<div class="flex-1">
				<h3 class="text-body font-semibold text-primary-100">Session Recovery Available</h3>
				<p class="mt-1 text-body-sm text-primary-200/80">
					You were {getStatusText(summary.status)}
					{#if summary.locationName}
						at <span class="font-medium text-primary-100">{summary.locationName}</span>
					{/if}
					{summary.ageText}.
				</p>
			</div>
		</div>

		<!-- Session details -->
		<div class="mb-4 flex flex-wrap gap-x-4 gap-y-2 text-caption text-primary-200/70">
			{#if summary.imageCount > 0}
				<div class="flex items-center gap-1.5">
					<ImageIcon size={14} strokeWidth={1.5} />
					<span>{summary.imageCount} photo{summary.imageCount !== 1 ? 's' : ''}</span>
				</div>
			{/if}
			{#if summary.confirmedCount > 0}
				<div class="flex items-center gap-1.5">
					<CheckSquare size={14} strokeWidth={1.5} />
					<span
						>{summary.confirmedCount} item{summary.confirmedCount !== 1 ? 's' : ''} confirmed</span
					>
				</div>
			{/if}
		</div>

		<div class="flex flex-col gap-2 sm:flex-row">
			<Button variant="primary" onclick={onResume} disabled={loading}>
				{#if loading}
					<div
						class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
					></div>
					<span>Recovering...</span>
				{:else}
					<Play size={16} strokeWidth={1.5} />
					<span>Resume Session</span>
				{/if}
			</Button>
			<Button variant="ghost" onclick={onDismiss} disabled={loading}>
				<span>Start Fresh</span>
			</Button>
		</div>
	</div>
</div>
