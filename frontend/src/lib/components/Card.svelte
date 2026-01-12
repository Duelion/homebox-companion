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
		default: 'bg-base-200 border-base-content/20 shadow-sm',
		elevated: 'bg-base-300 border-base-content/30 shadow-md',
		interactive:
			'bg-base-200 border-base-content/20 shadow-sm cursor-pointer hover:bg-base-300 hover:border-base-content/30 hover:shadow-md active:scale-[0.99]',
		selected:
			'bg-base-200 border-base-content/20 shadow-sm ring-2 ring-primary/50 border-primary',
	};

	const paddingClasses = {
		none: 'p-0',
		sm: 'p-2',
		md: 'p-4',
		lg: 'p-6',
	};
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
	class="rounded-2xl border transition-all duration-200 {variantClasses[variant]} {paddingClasses[
		padding
	]}"
	{onclick}
	role={onclick ? 'button' : undefined}
	tabindex={onclick ? 0 : undefined}
>
	{@render children()}
</div>
