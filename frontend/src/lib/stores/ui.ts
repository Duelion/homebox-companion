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

function removeToast(id: number) {
	// First mark as exiting for animation
	toasts.update((t) => t.map((toast) => 
		toast.id === id ? { ...toast, exiting: true } : toast
	));
	
	// Then remove after animation completes
	setTimeout(() => {
		toasts.update((t) => t.filter((toast) => toast.id !== id));
	}, 300);
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
			setTimeout(() => removeToast(oldestId), 50);
		}
		
		return newToasts;
	});

	if (duration > 0) {
		setTimeout(() => removeToast(id), duration);
	}

	return id;
}

export function dismissToast(id: number) {
	removeToast(id);
}

// Online/offline status
export const isOnline = writable<boolean>(true);

// App version
export const appVersion = writable<string>('');

// Set loading state with message
export function setLoading(loading: boolean, message: string = '') {
	isLoading.set(loading);
	loadingMessage.set(message);
}





