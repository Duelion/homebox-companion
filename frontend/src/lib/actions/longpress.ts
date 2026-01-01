/**
 * Long press action for Svelte components
 *
 * Triggers a callback when the element is pressed and held
 * for the specified duration (default: 500ms).
 *
 * Usage:
 *   <button use:longpress={{ onLongPress: handleLongPress }}>Hold me</button>
 *   <button use:longpress={{ onLongPress: handleLongPress, duration: 800 }}>Hold longer</button>
 */

export interface LongPressOptions {
	/** Callback to invoke when long press is detected */
	onLongPress: () => void;
	/** Duration in milliseconds before longpress fires (default: 500) */
	duration?: number;
}

export function longpress(node: HTMLElement, options: LongPressOptions) {
	let duration = options.duration ?? 500;
	let onLongPress = options.onLongPress;
	let timeoutId: ReturnType<typeof setTimeout> | null = null;
	let startX: number = 0;
	let startY: number = 0;
	const moveThreshold = 10; // pixels - cancel if finger moves too much

	// Store original styles to restore on destroy
	// Use bracket notation for vendor-prefixed properties that TypeScript doesn't recognize
	const style = node.style as CSSStyleDeclaration & Record<string, string>;
	const originalStyles = {
		userSelect: style.userSelect,
		webkitUserSelect: style['webkitUserSelect'] ?? '',
		webkitTouchCallout: style['webkitTouchCallout'] ?? '',
		touchAction: style.touchAction,
	};

	// Apply styles to prevent text selection and improve touch behavior
	style.userSelect = 'none';
	style['webkitUserSelect'] = 'none';
	style['webkitTouchCallout'] = 'none';
	style.touchAction = 'manipulation';

	function handleStart(event: TouchEvent | MouseEvent) {
		// Don't preventDefault here - it would block click events on mobile
		// CSS user-select: none handles text selection prevention

		// Record starting position for move detection
		if (event instanceof TouchEvent) {
			startX = event.touches[0].clientX;
			startY = event.touches[0].clientY;
		} else {
			startX = event.clientX;
			startY = event.clientY;
		}

		// Start the long press timer
		timeoutId = setTimeout(() => {
			// Haptic feedback on supported devices
			if (navigator.vibrate) {
				navigator.vibrate(50);
			}
			onLongPress();
			// Clear the timeout to indicate long press was triggered
			timeoutId = null;
		}, duration);
	}

	function handleEnd() {
		if (timeoutId) {
			clearTimeout(timeoutId);
			timeoutId = null;
		}
	}

	function handleMove(event: TouchEvent | MouseEvent) {
		if (!timeoutId) return;

		// Check if finger/mouse moved too far from start position
		let currentX: number, currentY: number;
		if (event instanceof TouchEvent) {
			currentX = event.touches[0].clientX;
			currentY = event.touches[0].clientY;
		} else {
			currentX = event.clientX;
			currentY = event.clientY;
		}

		const deltaX = Math.abs(currentX - startX);
		const deltaY = Math.abs(currentY - startY);

		if (deltaX > moveThreshold || deltaY > moveThreshold) {
			handleEnd();
		}
	}

	function handleContextMenu(event: Event) {
		// Prevent context menu from showing during long press
		if (timeoutId) {
			event.preventDefault();
		}
	}

	// Touch events for mobile (non-passive to allow preventDefault)
	node.addEventListener('touchstart', handleStart, { passive: false });
	node.addEventListener('touchend', handleEnd);
	node.addEventListener('touchcancel', handleEnd);
	node.addEventListener('touchmove', handleMove, { passive: false });

	// Mouse events for desktop
	node.addEventListener('mousedown', handleStart);
	node.addEventListener('mouseup', handleEnd);
	node.addEventListener('mouseleave', handleEnd);
	node.addEventListener('mousemove', handleMove);

	// Prevent context menu
	node.addEventListener('contextmenu', handleContextMenu);

	return {
		update(newOptions: LongPressOptions) {
			duration = newOptions.duration ?? 500;
			onLongPress = newOptions.onLongPress;
		},
		destroy() {
			handleEnd();

			// Restore original styles
			style.userSelect = originalStyles.userSelect;
			style['webkitUserSelect'] = originalStyles.webkitUserSelect;
			style['webkitTouchCallout'] = originalStyles.webkitTouchCallout;
			style.touchAction = originalStyles.touchAction;

			// Remove event listeners
			node.removeEventListener('touchstart', handleStart);
			node.removeEventListener('touchend', handleEnd);
			node.removeEventListener('touchcancel', handleEnd);
			node.removeEventListener('touchmove', handleMove);
			node.removeEventListener('mousedown', handleStart);
			node.removeEventListener('mouseup', handleEnd);
			node.removeEventListener('mouseleave', handleEnd);
			node.removeEventListener('mousemove', handleMove);
			node.removeEventListener('contextmenu', handleContextMenu);
		},
	};
}
