/**
 * Svelte action for expandable textarea inputs.
 *
 * When unfocused: Shows content truncated to single line height
 * When focused: Expands to show full content, up to max height
 *
 * Usage: <textarea use:expandable>
 */

interface ExpandableOptions {
	/** Collapsed height in pixels (default: 48) */
	collapsedHeight?: number;
	/** Maximum expanded height in pixels (default: 300) */
	maxHeight?: number;
}

export function expandable(node: HTMLTextAreaElement, options: ExpandableOptions = {}) {
	let { collapsedHeight = 48, maxHeight = 300 } = options;

	// Store original styles to restore on destroy
	const originalStyles = {
		height: node.style.height,
		minHeight: node.style.minHeight,
		maxHeight: node.style.maxHeight,
		overflow: node.style.overflow,
		transition: node.style.transition,
	};

	// Apply base styles
	node.style.transition = 'height 0.2s ease-out';
	node.style.overflow = 'hidden';
	node.style.resize = 'none';

	function collapse() {
		node.style.height = `${collapsedHeight}px`;
		node.style.minHeight = `${collapsedHeight}px`;
		node.style.maxHeight = `${collapsedHeight}px`;
		node.style.overflow = 'hidden';
	}

	function expand() {
		// Get current height before measuring
		const currentHeight = node.offsetHeight;

		// Temporarily remove height constraints to measure content
		node.style.transition = 'none';
		node.style.height = 'auto';
		node.style.minHeight = '0';
		node.style.maxHeight = 'none';

		// Get the scroll height (content height)
		const contentHeight = node.scrollHeight;

		// Clamp to max height
		const expandedHeight = Math.min(contentHeight, maxHeight);

		// Restore current height immediately (no transition)
		node.style.height = `${currentHeight}px`;
		node.style.minHeight = `${collapsedHeight}px`;
		node.style.maxHeight = `${currentHeight}px`;

		// Use requestAnimationFrame to ensure the browser paints the initial state
		// before we apply the transition and final state
		requestAnimationFrame(() => {
			// Re-enable transition and animate to new height
			node.style.transition =
				'height 0.2s ease-out, min-height 0.2s ease-out, max-height 0.2s ease-out';
			node.style.height = `${expandedHeight}px`;
			node.style.minHeight = `${collapsedHeight}px`;
			node.style.maxHeight = `${maxHeight}px`;
			node.style.overflow = contentHeight > maxHeight ? 'auto' : 'hidden';
		});
	}

	function handleFocus() {
		expand();
	}

	function handleBlur() {
		collapse();
	}

	function handleInput() {
		// Only auto-resize if currently focused
		if (document.activeElement === node) {
			expand();
		}
	}

	// Initialize in collapsed state
	collapse();

	// Add event listeners
	node.addEventListener('focus', handleFocus);
	node.addEventListener('blur', handleBlur);
	node.addEventListener('input', handleInput);

	return {
		// Called when options change
		update(newOptions: ExpandableOptions) {
			// Update closure variables with new options
			collapsedHeight = newOptions.collapsedHeight ?? 48;
			maxHeight = newOptions.maxHeight ?? 300;

			// Re-apply state with new values
			if (document.activeElement === node) {
				expand();
			} else {
				collapse();
			}
		},

		// Cleanup on destroy
		destroy() {
			node.removeEventListener('focus', handleFocus);
			node.removeEventListener('blur', handleBlur);
			node.removeEventListener('input', handleInput);

			// Restore original styles
			node.style.height = originalStyles.height;
			node.style.minHeight = originalStyles.minHeight;
			node.style.maxHeight = originalStyles.maxHeight;
			node.style.overflow = originalStyles.overflow;
			node.style.transition = originalStyles.transition;
		},
	};
}
