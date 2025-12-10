/**
 * Authentication API endpoints
 */

import { request } from './client';

export interface LoginResponse {
	token: string;
	message: string;
}

export interface ValidateResponse {
	valid: boolean;
}

export const auth = {
	login: (username: string, password: string) =>
		request<LoginResponse>('/login', {
			method: 'POST',
			body: JSON.stringify({ username, password }),
		}),
	
	/**
	 * Validate the current token against the server.
	 * Returns { valid: true } if valid, throws ApiError with 401 if invalid.
	 */
	validate: () => request<ValidateResponse>('/validate'),
};

