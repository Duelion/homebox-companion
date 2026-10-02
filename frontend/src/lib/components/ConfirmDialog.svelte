<script lang="ts">
	import Button from './Button.svelte';
	import Card from './Card.svelte';
	import { modalDialog } from '$lib/actions/dialog';

	interface Props {
		open: boolean;
		title: string;
		message: string;
		confirmLabel?: string;
		cancelLabel?: string;
		onConfirm: () => void;
		onCancel: () => void;
	}

	let {
		open = false,
		title,
		message,
		confirmLabel = 'Confirm',
		cancelLabel = 'Cancel',
		onConfirm,
		onCancel,
	}: Props = $props();
	const dialogId = $props.id();

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) {
			onCancel();
		}
	}

	function handleCancel(event: Event) {
		event.preventDefault();
		onCancel();
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<dialog
		use:modalDialog
		aria-labelledby={`${dialogId}-title`}
		aria-describedby={`${dialogId}-message`}
		class="animate-in fixed inset-0 z-50 m-0 flex max-h-none max-w-none items-center justify-center bg-neutral-950/60 p-0 backdrop-blur-sm backdrop:bg-transparent size-full"
		onclick={handleBackdropClick}
		oncancel={handleCancel}
	>
		<div class="mx-4 w-full max-w-sm">
			<Card padding="lg">
				<h2 id={`${dialogId}-title`} class="mb-2 text-h3 text-neutral-100">
					{title}
				</h2>
				<p id={`${dialogId}-message`} class="mb-6 text-body text-neutral-400">
					{message}
				</p>
				<div class="flex gap-3">
					<Button variant="secondary" full onclick={onCancel}>
						{cancelLabel}
					</Button>
					<Button variant="primary" full onclick={onConfirm}>
						{confirmLabel}
					</Button>
				</div>
			</Card>
		</div>
	</dialog>
{/if}
