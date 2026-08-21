/**
 * Authentication API endpoints
 */

import { request, NetworkError } from './client';
import type { AuthMethod } from '../stores/auth.svelte';

export interface LoginResponse {
	token: string;
	expires_at: string | null;
	auth_method: AuthMethod;
	user_email: string | null;
	message: string;
}

export const auth = {
	login: (username: string, password: string) =>
		request<LoginResponse>('/login', {
			method: 'POST',
			body: JSON.stringify({ username, password }),
		}),

	loginWithApiKey: (api_key: string) =>
		request<LoginResponse>('/login', {
			method: 'POST',
			body: JSON.stringify({ api_key }),
		}),

	/**
	 * Refresh the current token to extend its expiry.
	 * Returns new token and expiry time, throws ApiError with 401 if token is invalid.
	 *
	 * Note: Uses skipAuthRetry to prevent infinite loops - if refresh fails with 401,
	 * we don't want to try refreshing again.
	 */
	refresh: () =>
		request<LoginResponse>('/refresh', {
			method: 'POST',
			skipAuthRetry: true,
		}),

	/**
	 * Logout from Homebox, invalidating the current token on the server.
	 * Best-effort: failures are caught so local logout always proceeds.
	 */
	logout: () =>
		request('/logout', {
			method: 'POST',
			skipAuthRetry: true,
		}),

	/**
	 * Validate if the current token is still valid.
	 * Makes a lightweight request to /locations to test the token.
	 * Returns a result object indicating validity and the reason.
	 *
	 * Note: Uses skipAuthRetry to avoid triggering session expired modal during validation.
	 */
	validateToken: async (): Promise<{
		valid: boolean;
		reason: 'ok' | 'invalid' | 'network_error';
	}> => {
		try {
			await request('/locations', {
				method: 'GET',
				skipAuthRetry: true,
			});
			return { valid: true, reason: 'ok' };
		} catch (error) {
			// Use proper NetworkError class for reliable detection
			if (error instanceof NetworkError) {
				return { valid: false, reason: 'network_error' };
			}
			// ApiError (401, 403, etc.) or unknown error - treat as invalid token
			return { valid: false, reason: 'invalid' };
		}
	},
};
