<script lang="ts">
	/**
	 * StatusIcon - Shared status indicator component
	 *
	 * Shows spinner, checkmark, warning, or error based on status.
	 * Used for both AI analysis progress and submission progress.
	 */
	import { Check, TriangleAlert, X } from 'lucide-svelte';

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
	let iconSize = $derived(size === 'sm' ? 16 : 24);
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
		<Check class="text-success-500" size={iconSize} strokeWidth={2.5} />
	</div>
{:else if isWarning}
	<div
		class="{containerSize} flex items-center justify-center rounded-full bg-warning-500/20"
		title="Completed with warnings"
	>
		<TriangleAlert class="text-warning-500" size={iconSize} strokeWidth={2.5} />
	</div>
{:else if isFailed}
	<div class="{containerSize} flex items-center justify-center rounded-full bg-error-500/20">
		<X class="text-error-500" size={iconSize} strokeWidth={2.5} />
	</div>
{:else if isPending}
	<!-- Pending: show nothing or subtle indicator -->
	<div class="{containerSize} flex items-center justify-center">
		<div class="{spinnerSize} rounded-full bg-neutral-700/50"></div>
	</div>
{/if}
