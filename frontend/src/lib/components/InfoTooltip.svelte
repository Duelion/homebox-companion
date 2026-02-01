<script lang="ts">
	/**
	 * A mobile-friendly info tooltip icon.
	 *
	 * Shows on hover (desktop) or tap (mobile).
	 * Uses the Info icon from lucide-svelte.
	 */
	import { Info } from 'lucide-svelte';

	interface Props {
		/** The tooltip text to display */
		text: string;
		/** Icon size in pixels (default: 16) */
		size?: number;
	}

	let { text, size = 16 }: Props = $props();
	let showTooltip = $state(false);

	function handleToggle() {
		showTooltip = !showTooltip;
	}

	function handleMouseEnter() {
		showTooltip = true;
	}

	function handleMouseLeave() {
		showTooltip = false;
	}

	function handleBlur() {
		showTooltip = false;
	}
</script>

<div class="relative inline-flex">
	<!-- Info icon button - works on tap (mobile) and hover (desktop) -->
	<button
		type="button"
		class="shrink-0 cursor-help text-neutral-500 transition-colors hover:text-neutral-400"
		onclick={handleToggle}
		onmouseenter={handleMouseEnter}
		onmouseleave={handleMouseLeave}
		onblur={handleBlur}
		aria-label="Show tip"
	>
		<Info {size} strokeWidth={1.5} />
	</button>

	<!-- Tooltip -->
	{#if showTooltip}
		<div class="absolute bottom-full left-1/2 z-50 mb-2 w-48 -translate-x-1/2">
			<div
				class="rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-2 text-caption shadow-lg"
			>
				<p class="text-neutral-200">{text}</p>
			</div>
			<!-- Tooltip arrow -->
			<div
				class="absolute -bottom-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rotate-45 border-b border-r border-neutral-700 bg-neutral-800"
			></div>
		</div>
	{/if}
</div>
