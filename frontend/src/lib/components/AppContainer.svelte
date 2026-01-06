<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		children: Snippet;
		/** Additional CSS classes to merge */
		class?: string;
	}

	let { children, class: className = '' }: Props = $props();
</script>

<div class="mx-auto w-full max-w-lg sm:max-w-xl md:max-w-2xl {className}">
	{@render children()}
</div>


