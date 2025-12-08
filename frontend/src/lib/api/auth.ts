/**
 * Authentication API endpoints
 */

import { request } from './client';

export interface LoginResponse {
	token: string;
	message: string;
}

export const auth = {
	login: (username: string, password: string) =>
		request<LoginResponse>('/login', {
			method: 'POST',
			body: JSON.stringify({ username, password }),
		}),
};

