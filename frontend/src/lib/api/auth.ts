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
	 */
	refresh: () => request<LoginResponse>('/refresh'),
};

