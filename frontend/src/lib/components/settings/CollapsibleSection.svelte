<script lang="ts">
	/**
	 * CollapsibleSection - Reusable collapsible card wrapper for settings sections.
	 *
	 * Provides consistent styling and collapse/expand behavior for all settings sections.
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		/** Section title */
		title: string;
		/** Icon snippet to display next to title */
		icon?: Snippet;
		/** Whether the section starts collapsed */
		defaultCollapsed?: boolean;
		/** Content to display inside the section */
		children: Snippet;
	}

	let { title, icon, defaultCollapsed = false, children }: Props = $props();

	let isCollapsed = $state(defaultCollapsed);

	function toggle() {
		isCollapsed = !isCollapsed;
	}
</script>

<section class="card overflow-hidden">
	<!-- Clickable header -->
	<button
		type="button"
		class="flex w-full items-center justify-between gap-2 text-left"
		onclick={toggle}
		aria-expanded={!isCollapsed}
	>
		<h2 class="flex items-center gap-2 text-body-lg font-semibold text-base-content">
			{#if icon}
				{@render icon()}
			{/if}
			{title}
		</h2>
		<svg
			class="h-5 w-5 flex-shrink-0 text-base-content/50 transition-transform duration-200 {isCollapsed
				? ''
				: 'rotate-180'}"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<polyline points="6 9 12 15 18 9" />
		</svg>
	</button>

	<!-- Collapsible content -->
	<div
		class="grid transition-all duration-200 ease-in-out {isCollapsed
			? 'grid-rows-[0fr] opacity-0'
			: 'grid-rows-[1fr] opacity-100'}"
	>
		<div class="overflow-hidden">
			<div class="space-y-4 pt-4">
				{@render children()}
			</div>
		</div>
	</div>
</section>
