/** Start the visual transition while letting SvelteKit control the page update. */
export function startNavigationTransition(
	startTransition: (update: () => Promise<void>) => Pick<ViewTransition, 'ready'>,
	complete: Promise<void>
): Promise<void> {
	// The browser may delay its update callback until after navigation is cancelled.
	// Observe completion now; report unexpected failures from the callback below.
	const completion = complete.then(
		() => ({ ok: true as const }),
		(error: unknown) => ({ ok: false as const, error })
	);
	return new Promise<void>((resolve) => {
		const transition = startTransition(async () => {
			resolve();
			const result = await completion;
			// SvelteKit rejects complete when another navigation cancels this one.
			if (
				!result.ok &&
				!(
					result.error instanceof Error &&
					result.error.name === 'Error' &&
					result.error.message === 'navigation aborted'
				)
			) {
				throw result.error;
			}
		});
		// A newer transition skips the previous animation without cancelling its update.
		// Keep other failures visible; callback failures still surface via updateCallbackDone.
		void transition.ready.catch((error: unknown) => {
			if (!(error instanceof DOMException && error.name === 'AbortError')) throw error;
		});
	});
}
