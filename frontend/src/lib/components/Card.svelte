<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		variant?: 'default' | 'elevated' | 'interactive' | 'selected';
		padding?: 'none' | 'sm' | 'md' | 'lg';
		onclick?: () => void;
		children: Snippet;
	}

	let { variant = 'default', padding = 'md', onclick, children }: Props = $props();

	const variantClasses = {
		default: 'bg-neutral-900 border-neutral-700 shadow-sm',
		elevated: 'bg-neutral-800 border-neutral-600 shadow-md',
		interactive:
			'bg-neutral-900 border-neutral-700 shadow-sm cursor-pointer hover:bg-neutral-800 hover:border-neutral-600 hover:shadow-md active:scale-[0.99]',
		selected:
			'bg-neutral-900 border-neutral-700 shadow-sm ring-2 ring-primary-500/50 border-primary-600',
	};

	const paddingClasses = {
		none: 'p-0',
		sm: 'p-2',
		md: 'p-4',
		lg: 'p-6',
	};

	/**
	 * Handle keyboard events for interactive cards.
	 * Triggers onclick on Enter or Space key press for accessibility compliance.
	 */
	function handleKeydown(e: KeyboardEvent) {
		if (onclick && (e.key === 'Enter' || e.key === ' ')) {
			e.preventDefault();
			onclick();
		}
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
	class="rounded-2xl border transition-all duration-200 {variantClasses[variant]} {paddingClasses[
		padding
	]}"
	{onclick}
	onkeydown={onclick ? handleKeydown : undefined}
	role={onclick ? 'button' : undefined}
	tabindex={onclick ? 0 : undefined}
>
	{@render children()}
</div>
