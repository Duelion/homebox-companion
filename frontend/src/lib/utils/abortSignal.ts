/**
 * AbortSignal utilities with fallbacks for older browsers.
 *
 * AbortSignal.any() was added in Chrome 116, Firefox 124, Safari 17.4 (March 2024).
 * AbortSignal.timeout() was added in Chrome 103, Firefox 100, Safari 16.0 (May-Sep 2022).
 * This module provides fallbacks for older browsers.
 */

/**
 * Combines multiple AbortSignals into one that aborts when any of them abort.
 * Uses native AbortSignal.any() when available, falls back to manual implementation.
 *
 * @param signals - Array of AbortSignals to combine
 * @returns A signal that aborts when any input signal aborts
 */
export function abortSignalAny(signals: AbortSignal[]): AbortSignal {
	// Filter out undefined/null signals
	const validSignals = signals.filter((s): s is AbortSignal => s != null);

	if (validSignals.length === 0) {
		// No signals provided - return a signal that never aborts
		return new AbortController().signal;
	}

	if (validSignals.length === 1) {
		// Single signal - return it directly
		return validSignals[0];
	}

	// Use native AbortSignal.any if available (Chrome 116+, Firefox 124+, Safari 17.4+)
	if (typeof AbortSignal.any === 'function') {
		return AbortSignal.any(validSignals);
	}

	// Fallback implementation for older browsers
	const controller = new AbortController();

	// Check if any signal is already aborted
	for (const signal of validSignals) {
		if (signal.aborted) {
			controller.abort(signal.reason);
			return controller.signal;
		}
	}

	// Listen for abort on all signals
	const onAbort = (event: Event) => {
		const signal = event.target as AbortSignal;
		controller.abort(signal.reason);

		// Clean up listeners from all signals
		for (const s of validSignals) {
			s.removeEventListener('abort', onAbort);
		}
	};

	for (const signal of validSignals) {
		signal.addEventListener('abort', onAbort);
	}

	return controller.signal;
}

/**
 * Creates an AbortSignal that aborts after a specified timeout.
 * Uses native AbortSignal.timeout() when available, falls back to manual implementation.
 *
 * @param ms - Timeout in milliseconds
 * @returns A signal that aborts after the specified timeout
 */
export function abortSignalTimeout(ms: number): AbortSignal {
	// Use native AbortSignal.timeout if available (Chrome 103+, Firefox 100+, Safari 16.0+)
	if (typeof AbortSignal.timeout === 'function') {
		return AbortSignal.timeout(ms);
	}

	// Fallback implementation for older browsers
	const controller = new AbortController();
	const timerId = setTimeout(() => {
		// Use DOMException with 'TimeoutError' name to match native behavior
		controller.abort(new DOMException('The operation timed out', 'TimeoutError'));
	}, ms);

	// Clear timeout if signal is aborted externally to prevent memory leak
	controller.signal.addEventListener(
		'abort',
		() => {
			clearTimeout(timerId);
		},
		{ once: true }
	);

	return controller.signal;
}

