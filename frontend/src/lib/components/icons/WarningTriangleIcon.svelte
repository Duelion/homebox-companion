<script lang="ts">
	/**
	 * Warning Triangle Icon - Shared component using Lucide icons
	 *
	 * Provides a consistent warning triangle icon across the app.
	 * Uses lucide-svelte for high-quality, well-rendered SVG icons.
	 */
	import { TriangleAlert } from 'lucide-svelte';

	interface Props {
		class?: string;
		size?: number;
		strokeWidth?: number;
	}

	let { class: className = '', size = 20, strokeWidth = 2 }: Props = $props();
</script>

<TriangleAlert class="text-warning-400 {className}" {size} {strokeWidth} />
