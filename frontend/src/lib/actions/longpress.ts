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

    function handleStart(event: TouchEvent | MouseEvent) {
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
            onLongPress();
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

    // Touch events for mobile
    node.addEventListener('touchstart', handleStart, { passive: true });
    node.addEventListener('touchend', handleEnd);
    node.addEventListener('touchcancel', handleEnd);
    node.addEventListener('touchmove', handleMove, { passive: true });

    // Mouse events for desktop
    node.addEventListener('mousedown', handleStart);
    node.addEventListener('mouseup', handleEnd);
    node.addEventListener('mouseleave', handleEnd);
    node.addEventListener('mousemove', handleMove);

    return {
        update(newOptions: LongPressOptions) {
            duration = newOptions.duration ?? 500;
            onLongPress = newOptions.onLongPress;
        },
        destroy() {
            handleEnd();
            node.removeEventListener('touchstart', handleStart);
            node.removeEventListener('touchend', handleEnd);
            node.removeEventListener('touchcancel', handleEnd);
            node.removeEventListener('touchmove', handleMove);
            node.removeEventListener('mousedown', handleStart);
            node.removeEventListener('mouseup', handleEnd);
            node.removeEventListener('mouseleave', handleEnd);
            node.removeEventListener('mousemove', handleMove);
        }
    };
}
