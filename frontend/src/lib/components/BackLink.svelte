<script lang="ts">
	import { ChevronLeft } from 'lucide-svelte';
	import { resolveNavHref } from '$lib/navigation/config';

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

<!-- eslint-disable svelte/no-navigation-without-resolve -- resolved via resolveNavHref() -->
<a
	href={resolveNavHref(href)}
	class="group mb-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition-all duration-200 {disabled
		? 'cursor-not-allowed border border-neutral-800 bg-neutral-900/50 text-neutral-600 opacity-50'
		: 'border border-transparent bg-neutral-700/50 text-neutral-400 hover:border-neutral-700/50 hover:bg-neutral-700 hover:text-neutral-200'}"
	onclick={handleClick}
	aria-disabled={disabled}
>
	<ChevronLeft
		class="transition-transform duration-200 {disabled ? '' : 'group-hover:-translate-x-0.5'}"
		size={16}
	/>
	<span>{label}</span>
</a>
