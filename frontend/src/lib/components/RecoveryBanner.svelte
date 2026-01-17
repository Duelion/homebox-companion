<script lang="ts">
	/**
	 * RecoveryBanner - Prompts user to recover a crashed session
	 *
	 * Shown when a recoverable session is detected (e.g., after page reload mid-workflow).
	 * Provides options to resume the session or start fresh.
	 */
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
	class="border-primary-500/30 bg-primary-500/10 mb-4 overflow-hidden rounded-xl border shadow-lg"
	role="alert"
	aria-live="polite"
>
	<div class="p-4">
		<!-- Header -->
		<div class="mb-3 flex items-start gap-3">
			<!-- Recovery icon -->
			<div
				class="bg-primary-500/20 flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
			>
				<svg
					class="text-primary-400 h-5 w-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
					/>
				</svg>
			</div>

			<div class="flex-1">
				<h3 class="text-body text-primary-100 font-semibold">Session Recovery Available</h3>
				<p class="text-body-sm text-primary-200/80 mt-1">
					You were {getStatusText(summary.status)}
					{#if summary.locationName}
						at <span class="text-primary-100 font-medium">{summary.locationName}</span>
					{/if}
					{summary.ageText}.
				</p>
			</div>
		</div>

		<!-- Session details -->
		<div class="text-caption text-primary-200/70 mb-4 flex flex-wrap gap-x-4 gap-y-2">
			{#if summary.imageCount > 0}
				<div class="flex items-center gap-1.5">
					<svg
						class="h-3.5 w-3.5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
						<circle cx="8.5" cy="8.5" r="1.5" />
						<polyline points="21 15 16 10 5 21" />
					</svg>
					<span>{summary.imageCount} photo{summary.imageCount !== 1 ? 's' : ''}</span>
				</div>
			{/if}
			{#if summary.confirmedCount > 0}
				<div class="flex items-center gap-1.5">
					<svg
						class="h-3.5 w-3.5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<polyline points="9 11 12 14 22 4" />
						<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
					</svg>
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
					<svg
						class="h-4 w-4"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<polygon points="5 3 19 12 5 21 5 3" />
					</svg>
					<span>Resume Session</span>
				{/if}
			</Button>
			<Button variant="ghost" onclick={onDismiss} disabled={loading}>
				<span>Start Fresh</span>
			</Button>
		</div>
	</div>
</div>
