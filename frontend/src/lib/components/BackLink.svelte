<script lang="ts">
	interface Props {
		href: string;
		label?: string;
		onclick?: () => void;
	}

	let { href, label = 'Go back', onclick }: Props = $props();

	function handleClick(e: MouseEvent) {
		if (onclick) {
			e.preventDefault();
			onclick();
		}
	}
</script>

<a
	{href}
	class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm text-text-muted hover:text-text bg-surface-elevated/50 hover:bg-surface-elevated border border-transparent hover:border-border/50 transition-all duration-200 mb-4 group"
	onclick={handleClick}
>
	<svg
		class="w-4 h-4 transition-transform duration-200 group-hover:-translate-x-0.5"
		fill="none"
		stroke="currentColor"
		viewBox="0 0 24 24"
	>
		<polyline points="15 18 9 12 15 6" />
	</svg>
	<span>{label}</span>
</a>

