/**
 * Authentication API endpoints
 */

import { request, NetworkError } from './client';

export interface LoginResponse {
	token: string;
	expires_at: string;
	/** 'jwt' for session tokens (refreshable), 'api_key' for Homebox API keys */
	auth_type: 'jwt' | 'api_key';
	email?: string | null;
	message: string;
}

export const auth = {
	login: (username: string, password: string) =>
		request<LoginResponse>('/login', {
			method: 'POST',
			body: JSON.stringify({ username, password }),
		}),

	/**
	 * Login with a Homebox API key (hb_-prefixed token from the Homebox
	 * profile page). API-key sessions are not refreshable and are never
	 * logged out server-side.
	 */
	loginWithApiKey: (apiKey: string) =>
		request<LoginResponse>('/login/api-key', {
			method: 'POST',
			body: JSON.stringify({ api_key: apiKey }),
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
