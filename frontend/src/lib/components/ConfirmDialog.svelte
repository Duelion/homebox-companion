<script lang="ts">
	import Button from './Button.svelte';
	import Card from './Card.svelte';

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

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) {
			onCancel();
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			onCancel();
		}
	}
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="animate-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
		onclick={handleBackdropClick}
	>
		<div class="mx-4 w-full max-w-sm">
			<Card padding="lg">
				<h2 id="dialog-title" class="mb-2 text-h3 text-neutral-100">
					{title}
				</h2>
				<p class="mb-6 text-body text-neutral-400">
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
	</div>
{/if}
