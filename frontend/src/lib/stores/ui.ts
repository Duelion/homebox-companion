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
}

export const toasts = writable<Toast[]>([]);

let toastId = 0;

export function showToast(
	message: string,
	type: Toast['type'] = 'info',
	duration: number = 4000
) {
	const id = ++toastId;
	toasts.update((t) => [...t, { id, message, type }]);

	if (duration > 0) {
		setTimeout(() => {
			toasts.update((t) => t.filter((toast) => toast.id !== id));
		}, duration);
	}

	return id;
}

export function dismissToast(id: number) {
	toasts.update((t) => t.filter((toast) => toast.id !== id));
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

