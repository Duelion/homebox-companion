<script lang="ts">
	import { resolve } from '$app/paths';

	// Type-safe route type for dynamic paths
	type AppRoute = Parameters<typeof resolve>[0];

	interface Props {
		href: string;
		label?: string;
		onclick?: () => void;
		disabled?: boolean;
	}

	let { href, label = 'Go back', onclick, disabled = false }: Props = $props();

	function handleClick(e: MouseEvent) {
		if (disabled) {
			e.preventDefault();
			return;
		}
		if (onclick) {
			e.preventDefault();
			onclick();
		}
	}
</script>

<a
	href={resolve(href as AppRoute)}
	class="group mb-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition-all duration-200 {disabled
		? 'cursor-not-allowed border border-base-content/10 bg-base-200/50 text-base-content/30 opacity-50'
		: 'border border-transparent bg-base-300/50 text-base-content/60 hover:border-base-content/20 hover:bg-base-300 hover:text-base-content'}"
	onclick={handleClick}
	aria-disabled={disabled}
>
	<svg
		class="h-4 w-4 transition-transform duration-200 {disabled
			? ''
			: 'group-hover:-translate-x-0.5'}"
		fill="none"
		stroke="currentColor"
		viewBox="0 0 24 24"
	>
		<polyline points="15 18 9 12 15 6" />
	</svg>
	<span>{label}</span>
</a>
