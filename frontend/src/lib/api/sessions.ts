/**
 * Sessions API endpoints for crash recovery
 */

import { request } from './client';

// =============================================================================
// TYPES
// =============================================================================

export interface SessionSummary {
	session_id: string;
	status: string;
	created_at: string;
	location_name: string | null;
	image_count: number;
	pending_count: number;
	failed_count: number;
	completed_count: number;
}

export interface SessionImage {
	image_id: string;
	status: string;
	image_path: string;
	original_filename: string | null;
	attempts: number;
	result: Record<string, unknown> | null;
	error: string | null;
}

export interface SessionDetail {
	session_id: string;
	status: string;
	created_at: string;
	homebox_url: string;
	location_id: string | null;
	location_name: string | null;
	images: SessionImage[];
	can_recover: boolean;
}

export interface SessionCreateRequest {
	homebox_url: string;
	location_id?: string;
	location_name?: string;
}

export interface SessionCreateResponse {
	session_id: string;
	created_at: string;
}

export interface RecoveryResponse {
	session_id: string;
	recovered_images: SessionImage[];
	failed_images: SessionImage[];
	pending_images: SessionImage[];
}

export interface ActiveSessionCheck {
	has_recoverable: boolean;
	session: SessionSummary | null;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Check if there's an active recoverable session
 * Lightweight endpoint for checking on page load
 */
export const checkActiveSession = () =>
	request<ActiveSessionCheck>('/sessions/check/active');

/**
 * List all recoverable sessions
 */
export const listRecoverableSessions = () =>
	request<SessionSummary[]>('/sessions/recoverable');

/**
 * List all sessions
 */
export const listAllSessions = () =>
	request<SessionSummary[]>('/sessions/all');

/**
 * Get detailed session information
 */
export const getSession = (sessionId: string) =>
	request<SessionDetail>(`/sessions/${sessionId}`);

/**
 * Create a new session
 */
export const createSession = (data: SessionCreateRequest) =>
	request<SessionCreateResponse>('/sessions', {
		method: 'POST',
		body: JSON.stringify(data),
	});

/**
 * Recover a session for resuming work
 */
export const recoverSession = (sessionId: string) =>
	request<RecoveryResponse>(`/sessions/${sessionId}/recover`, {
		method: 'POST',
	});

/**
 * Mark a session as completed
 */
export const completeSession = (sessionId: string) =>
	request<{ status: string; session_id: string }>(`/sessions/${sessionId}/complete`, {
		method: 'POST',
	});

/**
 * Delete/abandon a session
 */
export const deleteSession = (sessionId: string) =>
	request<{ status: string; session_id: string }>(`/sessions/${sessionId}`, {
		method: 'DELETE',
	});

/**
 * Add an image to a session
 */
export const addSessionImage = (sessionId: string, imagePath: string, originalFilename?: string) =>
	request<{ image_id: string; status: string }>(`/sessions/${sessionId}/images`, {
		method: 'POST',
		body: JSON.stringify({
			image_path: imagePath,
			original_filename: originalFilename,
		}),
	});

/**
 * Mark image processing as started
 */
export const startImageProcessing = (sessionId: string, imageId: string) =>
	request<{ status: string; image_id: string }>(`/sessions/${sessionId}/process/start`, {
		method: 'POST',
		body: JSON.stringify({ image_id: imageId }),
	});

/**
 * Mark image processing as complete
 */
export const completeImageProcessing = (
	sessionId: string,
	imageId: string,
	result: Record<string, unknown>
) =>
	request<{ status: string; image_id: string; has_result: boolean }>(
		`/sessions/${sessionId}/process/complete`,
		{
			method: 'POST',
			body: JSON.stringify({ image_id: imageId, result }),
		}
	);

/**
 * Mark image processing as failed
 */
export const failImageProcessing = (sessionId: string, imageId: string, error: string) =>
	request<{ status: string; image_id: string; attempts: number; can_retry: boolean }>(
		`/sessions/${sessionId}/process/fail`,
		{
			method: 'POST',
			body: JSON.stringify({ image_id: imageId, error }),
		}
	);
