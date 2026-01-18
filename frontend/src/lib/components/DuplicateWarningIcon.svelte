<script lang="ts">
	/**
	 * Compact warning icon with tooltip for the Summary page.
	 *
	 * Displays a warning icon next to items that may be duplicates.
	 * Hovering or focusing the icon shows tooltip with duplicate details.
	 */
	import type { DuplicateMatch } from '$lib/types';

	interface Props {
		match: DuplicateMatch;
	}

	let { match }: Props = $props();
	let showTooltip = $state(false);
</script>

<div class="relative">
	<!-- Warning icon button -->
	<button
		type="button"
		class="text-warning-400 hover:text-warning-300 transition-colors"
		onmouseenter={() => (showTooltip = true)}
		onmouseleave={() => (showTooltip = false)}
		onfocus={() => (showTooltip = true)}
		onblur={() => (showTooltip = false)}
		aria-label="Possible duplicate item"
	>
		<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
			<path
				d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
			/>
			<line x1="12" y1="9" x2="12" y2="13" />
			<line x1="12" y1="17" x2="12.01" y2="17" />
		</svg>
	</button>

	<!-- Tooltip -->
	{#if showTooltip}
		<div class="absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2">
			<div class="rounded-lg border border-neutral-700 bg-neutral-800 p-3 text-body-sm shadow-lg">
				<p class="text-warning-300 mb-1 font-semibold">Possible Duplicate</p>
				<p class="text-neutral-300">
					Serial "<span class="text-warning-200 font-mono">{match.serial_number}</span>" already
					exists on:
				</p>
				<p class="mt-1 font-medium text-neutral-100">
					"{match.item_name}"
					{#if match.location_name}
						<span class="font-normal text-neutral-400">in {match.location_name}</span>
					{/if}
				</p>
			</div>
			<!-- Tooltip arrow -->
			<div
				class="absolute -bottom-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 border-b border-r border-neutral-700 bg-neutral-800"
			></div>
		</div>
	{/if}
</div>
