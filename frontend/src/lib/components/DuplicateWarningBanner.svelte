<!--
  DuplicateWarningBanner - Shows warning when potential duplicate items are detected

  This component displays a warning banner when items with matching serial numbers,
  manufacturer+model, or similar names are found in the existing Homebox inventory.

  Two states:
  - Warning state (yellow): Shows duplicate warning with "Update Existing" button
  - Confirmed state (green): Shows "Will update: [name]" with "Create new instead" link

  Users can choose to update the existing item (merge) or proceed with creating new.
-->
<script lang="ts">
	import type { DuplicateMatch, UpdateDecision } from '$lib/types';

	interface Props {
		/** The duplicate match to display (single item mode) */
		match: DuplicateMatch;
		/** Whether this item is marked for update (vs create new) */
		isMarkedForUpdate?: boolean;
		/** The update decision if marked for update */
		updateDecision?: UpdateDecision;
		/** Callback when user clicks "Update Existing" */
		onUpdateExisting?: () => void;
		/** Callback when user clicks "Create new instead" */
		onCreateNew?: () => void;
		/** Optional: Whether to show in compact mode */
		compact?: boolean;
	}

	let {
		match,
		isMarkedForUpdate = false,
		updateDecision,
		onUpdateExisting,
		onCreateNew,
		compact = false,
	}: Props = $props();

	/** Format the match type for display */
	function formatMatchType(matchType: string): string {
		switch (matchType) {
			case 'serial_number':
				return 'Serial number';
			case 'manufacturer_model':
				return 'Manufacturer + Model';
			case 'fuzzy_name':
				return 'Similar name';
			default:
				return matchType;
		}
	}

	/** Get the match value to display */
	function getMatchDisplay(m: DuplicateMatch): string {
		switch (m.match_type) {
			case 'serial_number':
				return m.match_value;
			case 'manufacturer_model':
				return m.match_value;
			case 'fuzzy_name':
				return `"${m.match_value}" (${Math.round(m.similarity_score * 100)}% similar)`;
			default:
				return m.match_value;
		}
	}

	/** Get confidence badge styling */
	function getConfidenceBadge(confidence: string): { class: string; label: string } {
		switch (confidence) {
			case 'high':
				return { class: 'bg-error/20 text-error', label: 'High' };
			case 'medium-high':
				return { class: 'bg-warning/20 text-warning', label: 'Medium-High' };
			case 'medium':
				return { class: 'bg-warning/20 text-warning', label: 'Medium' };
			case 'low':
				return { class: 'bg-info/20 text-info', label: 'Low' };
			default:
				return { class: 'bg-base-300 text-base-content', label: confidence };
		}
	}

	// Compute badge outside template for cleaner code
	const confidenceBadge = $derived(getConfidenceBadge(match.confidence));
</script>

{#if isMarkedForUpdate && updateDecision}
	<!-- Confirmed update state: Green banner -->
	<div
		class="bg-success/10 border border-success/30 rounded-xl {compact ? 'p-3' : 'p-4'}"
		role="status"
	>
		<div class="flex items-center gap-3">
			<svg
				class="w-5 h-5 text-success flex-shrink-0"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="2"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
				/>
			</svg>
			<div class="flex-1 min-w-0">
				<p class="text-body-sm text-success">
					<span class="font-semibold">Will update:</span>
					<span class="text-success/90">{updateDecision.targetItemName}</span>
				</p>
				{#if !compact}
					<p class="text-caption text-success/70 mt-1">
						Photos will be added, empty fields will be filled
					</p>
				{/if}
			</div>
			{#if onCreateNew}
				<button
					type="button"
					class="text-caption text-success/80 hover:text-success underline underline-offset-2 flex-shrink-0"
					onclick={onCreateNew}
				>
					Create new instead
				</button>
			{/if}
		</div>
	</div>
{:else}
	<!-- Warning state: Yellow banner with Update Existing button -->
	<div
		class="bg-warning/10 border border-warning/30 rounded-xl {compact ? 'p-3' : 'p-4'}"
		role="alert"
	>
		<div class="flex items-start gap-3">
			<svg
				class="w-5 h-5 text-warning flex-shrink-0 {compact ? 'mt-0' : 'mt-0.5'}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="2"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
				/>
			</svg>
			<div class="flex-1 min-w-0">
				{#if compact}
					<!-- Compact mode: single line -->
					<p class="text-body-sm text-warning">
						<span class="font-semibold">Potential duplicate:</span>
						matches "{match.existing_item.name}"
					</p>
				{:else}
					<!-- Full mode: detailed info -->
					<div class="flex items-center gap-2 mb-2">
						<h4 class="text-body-sm font-semibold text-warning">
							Potential Duplicate Detected
						</h4>
						<span class="text-xxs px-1.5 py-0.5 rounded-full {confidenceBadge.class}">
							{confidenceBadge.label} confidence
						</span>
					</div>

					<div class="space-y-1 text-body-sm">
						<p class="text-warning/90">
							<span class="text-warning/70">{formatMatchType(match.match_type)}:</span>
							<span class="font-mono text-warning">{getMatchDisplay(match)}</span>
						</p>
						<p class="text-warning/90">
							<span class="text-warning/70">Matches existing item:</span>
							<span class="font-semibold text-warning">"{match.existing_item.name}"</span>
							{#if match.existing_item.location_name}
								<span class="text-warning/70">in {match.existing_item.location_name}</span>
							{/if}
						</p>
					</div>

					<p class="text-caption text-warning/60 mt-3">
						You can update the existing item with new photos and fill empty fields,
						or create a new item if this is different.
					</p>
				{/if}
			</div>

			{#if onUpdateExisting}
				<button
					type="button"
					class="btn btn-sm btn-warning flex-shrink-0"
					onclick={onUpdateExisting}
				>
					Update Existing
				</button>
			{/if}
		</div>
	</div>
{/if}
