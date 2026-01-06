<!--
  DuplicateWarningBanner - Shows warning when potential duplicate items are detected

  This component displays a warning banner when items with matching serial numbers
  are found in the existing Homebox inventory. It's non-blocking - users can
  acknowledge the warning and proceed with submission.
-->
<script lang="ts">
	import type { DuplicateMatch } from '$lib/types';

	interface Props {
		/** List of duplicate matches to display */
		duplicates: DuplicateMatch[];
		/** Optional: Whether to show in compact mode (for item-level warnings) */
		compact?: boolean;
	}

	let { duplicates, compact = false }: Props = $props();
</script>

{#if duplicates.length > 0}
	<div
		class="bg-warning-500/10 border border-warning-500/30 rounded-xl p-4 {compact
			? 'p-3'
			: 'p-4'}"
		role="alert"
	>
		<div class="flex items-start gap-3">
			<svg
				class="w-5 h-5 text-warning-400 flex-shrink-0 {compact ? 'mt-0' : 'mt-0.5'}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="2"
			>
				<path
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
				/>
			</svg>
			<div class="flex-1 min-w-0">
				{#if compact}
					<!-- Compact mode: single line per duplicate -->
					<p class="text-body-sm text-warning-300">
						{#if duplicates.length === 1}
							{@const match = duplicates[0]}
							<span class="font-semibold">{match.item_name}</span> may already exist
							<span class="text-warning-400"
								>(Serial: {match.serial_number} matches "{match.existing_item
									.name}")</span
							>
						{:else}
							{duplicates.length} items may already exist in Homebox
						{/if}
					</p>
				{:else}
					<!-- Full mode: header + list -->
					<h4
						class="text-body-sm font-semibold text-warning-300 mb-2"
					>
						{duplicates.length === 1
							? 'Potential Duplicate Detected'
							: `${duplicates.length} Potential Duplicates Detected`}
					</h4>
					<ul class="space-y-2 text-body-sm text-warning-200/80">
						{#each duplicates as match}
							<li class="flex items-start gap-2">
								<span class="text-warning-400 flex-shrink-0"
									>•</span
								>
								<div>
									<span class="font-medium text-warning-200"
										>{match.item_name}</span
									>
									<span class="text-warning-300/70">
										— Serial "{match.serial_number}" matches
										existing item
									</span>
									<span class="font-medium text-warning-200"
										>"{match.existing_item.name}"</span
									>
									{#if match.existing_item.location_name}
										<span class="text-warning-300/70">
											in {match.existing_item.location_name}
										</span>
									{/if}
								</div>
							</li>
						{/each}
					</ul>
					<p class="text-caption text-warning-400/70 mt-3">
						These items may already be in your inventory. You can
						still proceed if they are intentionally different items
						with the same serial number.
					</p>
				{/if}
			</div>
		</div>
	</div>
{/if}
