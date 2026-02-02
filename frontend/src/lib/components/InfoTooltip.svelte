<script lang="ts">
	/**
	 * A mobile-friendly info popup icon.
	 *
	 * Clicking the icon opens a compact modal with the info text.
	 * Uses the Unicode ⓘ character for minimal overhead.
	 */
	import Modal from './Modal.svelte';

	interface Props {
		/** The info text to display in the popup */
		text: string;
	}

	let { text }: Props = $props();
	let showPopup = $state(false);

	function handleOpen() {
		showPopup = true;
	}
</script>

<!-- Info icon button using Unicode character -->
<button
	type="button"
	class="-my-2 -ml-2 inline-flex min-h-touch min-w-touch shrink-0 items-center justify-center text-sm leading-none text-neutral-500 transition-colors hover:text-neutral-400"
	onclick={handleOpen}
	aria-label="Show info"
>
	ⓘ
</button>

<!-- Compact modal -->
<Modal bind:open={showPopup} compact>
	<p class="text-body-sm text-neutral-300">{text}</p>
</Modal>
