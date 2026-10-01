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
	const dialogId = $props.id();

	function showModal(dialog: HTMLDialogElement) {
		const previousFocus = document.activeElement;
		dialog.showModal();
		function keepFocus(event: KeyboardEvent) {
			if (event.key !== 'Tab') return;
			const buttons = dialog.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');
			const first = buttons[0];
			const last = buttons[buttons.length - 1];
			if (event.shiftKey && document.activeElement === first) {
				event.preventDefault();
				last?.focus();
			} else if (!event.shiftKey && document.activeElement === last) {
				event.preventDefault();
				first?.focus();
			}
		}
		dialog.addEventListener('keydown', keepFocus);
		return {
			destroy() {
				dialog.removeEventListener('keydown', keepFocus);
				dialog.close();
				if (previousFocus instanceof HTMLElement && previousFocus.isConnected) {
					previousFocus.focus();
				}
			},
		};
	}

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
		use:showModal
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
