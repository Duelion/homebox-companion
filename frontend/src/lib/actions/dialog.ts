const openDialogs: HTMLDialogElement[] = [];

/** Open a native modal, contain keyboard focus, and restore its trigger on close. */
export function modalDialog(dialog: HTMLDialogElement) {
	const previousFocus = document.activeElement;
	dialog.showModal();
	openDialogs.push(dialog);

	function controls() {
		return Array.from(
			dialog.querySelectorAll<HTMLElement>('a[href], button, input, select, textarea, [tabindex]')
		).filter(
			(element) =>
				element.tabIndex >= 0 &&
				!element.matches(':disabled, [inert], [inert] *') &&
				element.getClientRects().length > 0
		);
	}

	const initialFocus = dialog.querySelector<HTMLElement>('[autofocus]') ?? controls()[0];
	(initialFocus ?? dialog).focus();

	function keepFocus(event: KeyboardEvent) {
		if (event.key !== 'Tab' || openDialogs.at(-1) !== dialog) return;
		const focusable = controls();
		const first = focusable[0];
		const last = focusable[focusable.length - 1];
		if (!first) {
			event.preventDefault();
			dialog.focus();
		} else if (document.activeElement === dialog) {
			event.preventDefault();
			(event.shiftKey ? last : first).focus();
		} else if (event.shiftKey && document.activeElement === first) {
			event.preventDefault();
			last.focus();
		} else if (!event.shiftKey && document.activeElement === last) {
			event.preventDefault();
			first.focus();
		}
	}

	dialog.addEventListener('keydown', keepFocus);
	return {
		destroy() {
			dialog.removeEventListener('keydown', keepFocus);
			const wasTop = openDialogs.at(-1) === dialog;
			openDialogs.splice(openDialogs.indexOf(dialog), 1);
			if (dialog.open) dialog.close();
			if (wasTop && previousFocus instanceof HTMLElement && previousFocus.isConnected) {
				previousFocus.focus();
			}
		},
	};
}
