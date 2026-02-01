<script lang="ts">
	/**
	 * A mobile-friendly info popup icon.
	 *
	 * Clicking the icon opens a centered popup modal with the info text.
	 * Uses the Info icon from lucide-svelte.
	 */
	import { Info } from 'lucide-svelte';
	import Modal from './Modal.svelte';

	interface Props {
		/** The info text to display in the popup */
		text: string;
		/** Icon size in pixels (default: 16) */
		size?: number;
	}

	let { text, size = 16 }: Props = $props();
	let showPopup = $state(false);

	function handleOpen() {
		showPopup = true;
	}
</script>

<!-- Info icon button -->
<button
	type="button"
	class="inline-flex shrink-0 text-neutral-500 transition-colors hover:text-neutral-400"
	onclick={handleOpen}
	aria-label="Show info"
>
	<Info {size} strokeWidth={1.5} />
</button>

<!-- Reuse existing Modal component -->
<Modal bind:open={showPopup} title="Info">
	<p class="text-body-sm text-neutral-300">{text}</p>
</Modal>
