/**
 * UI state store
 */
import { writable } from 'svelte/store';

// Loading states
export const isLoading = writable<boolean>(false);
export const loadingMessage = writable<string>('');

// Toast notifications
export interface Toast {
	id: number;
	message: string;
	type: 'info' | 'success' | 'warning' | 'error';
	exiting?: boolean;
}

const MAX_VISIBLE_TOASTS = 2;

export const toasts = writable<Toast[]>([]);

let toastId = 0;

// Track all active timers per toast for cleanup
const toastTimers = new Map<number, Set<ReturnType<typeof setTimeout>>>();

/** Register a timer for a toast (for cleanup tracking) */
function registerTimer(id: number, timerId: ReturnType<typeof setTimeout>): void {
	let timers = toastTimers.get(id);
	if (!timers) {
		timers = new Set();
		toastTimers.set(id, timers);
	}
	timers.add(timerId);
}

/** Clear all timers for a toast */
function clearToastTimers(id: number): void {
	const timers = toastTimers.get(id);
	if (timers) {
		for (const timerId of timers) {
			clearTimeout(timerId);
		}
		toastTimers.delete(id);
	}
}

function removeToast(id: number) {
	// Clear any pending timers for this toast first
	clearToastTimers(id);
	
	// First mark as exiting for animation
	toasts.update((t) => t.map((toast) => 
		toast.id === id ? { ...toast, exiting: true } : toast
	));
	
	// Then remove after animation completes
	const animationTimer = setTimeout(() => {
		toasts.update((t) => t.filter((toast) => toast.id !== id));
	}, 300);
	// Track the animation timer (no id to clear since toast is already exiting)
	registerTimer(id, animationTimer);
}

export function showToast(
	message: string,
	type: Toast['type'] = 'info',
	duration: number = 4000
) {
	const id = ++toastId;
	
	toasts.update((t) => {
		const newToasts = [...t, { id, message, type }];
		
		// If we exceed max, mark oldest non-exiting toast for removal
		const visibleToasts = newToasts.filter((toast) => !toast.exiting);
		if (visibleToasts.length > MAX_VISIBLE_TOASTS) {
			const oldestId = visibleToasts[0].id;
			// Schedule removal of oldest toast
			const overflowTimer = setTimeout(() => removeToast(oldestId), 50);
			registerTimer(oldestId, overflowTimer);
		}
		
		return newToasts;
	});

	if (duration > 0) {
		const dismissTimer = setTimeout(() => removeToast(id), duration);
		registerTimer(id, dismissTimer);
	}

	return id;
}

export function dismissToast(id: number) {
	removeToast(id);
}

/** Clear all toasts and their timers (useful for cleanup/reset) */
export function clearAllToasts() {
	// Clear all tracked timers
	for (const id of toastTimers.keys()) {
		clearToastTimers(id);
	}
	toasts.set([]);
}

// Online/offline status
export const isOnline = writable<boolean>(true);

// App version
export const appVersion = writable<string>('');

// Update notification
export const latestVersion = writable<string | null>(null);
export const updateDismissed = writable<boolean>(false);

// Set loading state with message
export function setLoading(loading: boolean, message: string = '') {
	isLoading.set(loading);
	loadingMessage.set(message);
}





