/**
 * Authentication API endpoints
 */

import { request } from './client';

export interface LoginResponse {
	token: string;
	expires_at: string;
	message: string;
}

export const auth = {
	login: (username: string, password: string) =>
		request<LoginResponse>('/login', {
			method: 'POST',
			body: JSON.stringify({ username, password }),
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
	 * Validate if the current token is still valid.
	 * Makes a lightweight request to /locations to test the token.
	 * Returns true if valid, false if expired/invalid.
	 * 
	 * Note: Uses skipAuthRetry to avoid triggering session expired modal during validation.
	 */
	validateToken: async (): Promise<boolean> => {
		try {
			await request('/locations', {
				method: 'GET',
				skipAuthRetry: true,
			});
			return true;
		} catch {
			// Any error (401, network, etc.) means token is not valid
			return false;
		}
	},
};

