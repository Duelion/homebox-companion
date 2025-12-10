/**
 * JWT token utilities for client-side token validation
 */

import { get } from 'svelte/store';
import { token, markSessionExpired } from '../stores/auth';

/**
 * Decode a JWT token and extract its payload
 * Note: This does NOT verify the signature - only decodes the payload
 */
function decodeJwt(token: string): { exp?: number } | null {
	try {
		const parts = token.split('.');
		if (parts.length !== 3) return null;
		
		const payload = parts[1];
		const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
		return JSON.parse(decoded);
	} catch {
		return null;
	}
}

/**
 * Check if a JWT token is expired (or will expire within the buffer time)
 * @param token - The JWT token string
 * @param bufferSeconds - Number of seconds before expiration to consider token expired (default: 30)
 * @returns true if token is expired or will expire soon
 */
export function isTokenExpired(token: string | null, bufferSeconds: number = 30): boolean {
	if (!token) return true;
	
	const payload = decodeJwt(token);
	if (!payload || !payload.exp) return true;
	
	const now = Math.floor(Date.now() / 1000);
	const expiresAt = payload.exp - bufferSeconds;
	
	return now >= expiresAt;
}

/**
 * Check if the current auth token is valid
 * If expired, triggers the session expired modal
 * @returns true if token is valid, false if expired
 */
export function checkAuth(): boolean {
	const currentToken = get(token);
	
	if (isTokenExpired(currentToken)) {
		markSessionExpired();
		return false;
	}
	
	return true;
}

