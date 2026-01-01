<script lang="ts">
	/**
	 * StatusIcon - Shared status indicator component
	 *
	 * Shows spinner, checkmark, warning, or error based on status.
	 * Used for both AI analysis progress and submission progress.
	 */

	type Status =
		| 'pending'
		| 'processing'
		| 'creating'
		| 'analyzing'
		| 'success'
		| 'partial_success'
		| 'failed';

	interface Props {
		status: Status;
		/** Size variant */
		size?: 'sm' | 'md';
	}

	let { status, size = 'md' }: Props = $props();

	// Normalize processing states
	let isSpinning = $derived(
		status === 'processing' || status === 'creating' || status === 'analyzing'
	);
	let isSuccess = $derived(status === 'success');
	let isWarning = $derived(status === 'partial_success');
	let isFailed = $derived(status === 'failed');
	let isPending = $derived(status === 'pending');

	// Size classes
	let containerSize = $derived(size === 'sm' ? 'w-8 h-8' : 'w-10 h-10');
	let iconSize = $derived(size === 'sm' ? 'w-4 h-4' : 'w-6 h-6');
	let spinnerSize = $derived(size === 'sm' ? 'w-4 h-4' : 'w-6 h-6');
</script>

{#if isSpinning}
	<div class="{containerSize} flex items-center justify-center">
		<div
			class="{spinnerSize} animate-spin rounded-full border-2 border-primary-500/30 border-t-primary-500"
		></div>
	</div>
{:else if isSuccess}
	<div class="{containerSize} flex items-center justify-center rounded-full bg-success-500/20">
		<svg
			class="{iconSize} text-success-500"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="2.5"
		>
			<polyline points="20 6 9 17 4 12" />
		</svg>
	</div>
{:else if isWarning}
	<div
		class="{containerSize} flex items-center justify-center rounded-full bg-warning-500/20"
		title="Completed with warnings"
	>
		<svg
			class="{iconSize} text-warning-500"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="2.5"
		>
			<path
				d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
			/>
			<line x1="12" y1="9" x2="12" y2="13" />
			<line x1="12" y1="17" x2="12.01" y2="17" />
		</svg>
	</div>
{:else if isFailed}
	<div class="{containerSize} flex items-center justify-center rounded-full bg-error-500/20">
		<svg
			class="{iconSize} text-error-500"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="2.5"
		>
			<line x1="18" y1="6" x2="6" y2="18" />
			<line x1="6" y1="6" x2="18" y2="18" />
		</svg>
	</div>
{:else if isPending}
	<!-- Pending: show nothing or subtle indicator -->
	<div class="{containerSize} flex items-center justify-center">
		<div class="{spinnerSize} rounded-full bg-neutral-700/50"></div>
	</div>
{/if}
