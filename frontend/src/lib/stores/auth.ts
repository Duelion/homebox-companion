/**
 * Authentication store
 */
import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

// Token stored in sessionStorage
const storedToken = browser ? sessionStorage.getItem('hbc_token') : null;

export const token = writable<string | null>(storedToken);

// Persist token to sessionStorage
if (browser) {
	token.subscribe((value) => {
		if (value) {
			sessionStorage.setItem('hbc_token', value);
		} else {
			sessionStorage.removeItem('hbc_token');
		}
	});
}

export const isAuthenticated = derived(token, ($token) => !!$token);

export function logout() {
	token.set(null);
}

