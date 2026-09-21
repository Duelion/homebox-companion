/**
 * Session Persistence Service
 *
 * Provides IndexedDB-based persistence for scan workflow sessions.
 * Enables crash recovery by storing workflow state that survives page reloads.
 *
 * Key design decisions:
 * - Uses IndexedDB (via idb library) for storage > 5MB limit of localStorage
 * - One session per verified Homebox identity and collection
 * - TTL-based cleanup: expired sessions are removed when accessed after 7 days
 * - Storage operations are called by the workflow's autosave and explicit checkpoints
 */

import { browser } from '$app/environment';
import { openDB, type IDBPDatabase } from 'idb';
import type { StoredSession } from './serialize';
import { createLogger } from '$lib/utils/logger';
import { authStore } from '$lib/stores/auth.svelte';
import { collectionStore } from '$lib/stores/collection.svelte';

const log = createLogger({ prefix: 'SessionPersistence' });

// =============================================================================
// CONSTANTS
// =============================================================================

const DB_NAME = 'hbc-scan-recovery';
const DB_VERSION = 2;
const STORE_NAME = 'sessions';

export interface SessionScope {
	contextId: string;
	groupId: string;
}

export function captureSessionScope(): SessionScope | null {
	// Reconnection must reconcile old in-memory work before a new scope can persist it.
	if (
		authStore.phase === 'initializing' ||
		authStore.phase === 'connecting' ||
		authStore.phase === 'connection_error' ||
		!collectionStore.ready
	) {
		return null;
	}
	const context = authStore.contextId;
	const group = collectionStore.selectedId;
	return context && group ? { contextId: context, groupId: group } : null;
}

function sessionKey(scope: SessionScope): string {
	return `${scope.contextId}:${scope.groupId}`;
}

/** Session TTL in milliseconds (7 days) */
const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;

/**
 * Check if a session has exceeded its TTL.
 * @param session - The session to check
 * @returns true if expired, false otherwise
 */
function isSessionExpired(session: StoredSession): boolean {
	const age = Date.now() - session.createdAt;
	return age > SESSION_TTL_MS;
}

// =============================================================================
// DATABASE INITIALIZATION
// =============================================================================

let dbPromise: Promise<IDBPDatabase> | null = null;

/**
 * Get or create the IndexedDB database connection.
 * Uses lazy initialization pattern.
 */
function getDb(): Promise<IDBPDatabase> {
	if (!browser) {
		return Promise.reject(new Error('IndexedDB not available in SSR'));
	}

	if (!dbPromise) {
		dbPromise = openDB(DB_NAME, DB_VERSION, {
			upgrade(db, oldVersion) {
				log.info(`Upgrading database from version ${oldVersion} to ${DB_VERSION}`);
				// Keep context-free records quarantined under their old key.
				if (!db.objectStoreNames.contains(STORE_NAME)) db.createObjectStore(STORE_NAME);
			},
			blocked() {
				log.warn('Database upgrade blocked by another tab');
			},
			blocking() {
				log.warn('This tab is blocking a database upgrade');
			},
		});
	}

	return dbPromise;
}

// =============================================================================
// SESSION SUMMARY (for recovery UI)
// =============================================================================

export interface SessionSummary {
	/** Age of session in human-readable format (e.g., "2 hours ago") */
	ageText: string;
	/** Number of captured images */
	imageCount: number;
	/** Location name if set */
	locationName: string | null;
	/** Current workflow status */
	status: string;
	/** Number of confirmed items (if in review/confirm stage) */
	confirmedCount: number;
}

/**
 * Format a timestamp as a human-readable relative time.
 */
function formatAge(timestamp: number): string {
	const now = Date.now();
	const diffMs = now - timestamp;
	const diffMins = Math.floor(diffMs / (1000 * 60));
	const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
	const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

	if (diffMins < 1) return 'just now';
	if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
	if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
	return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
}

// =============================================================================
// PUBLIC API
// =============================================================================

/**
 * Check if there's a recoverable session available.
 * Fast check for recovery UI - doesn't load the full session.
 */
export async function hasRecoverableSession(scope = captureSessionScope()): Promise<boolean> {
	if (!browser) return false;
	if (!scope) return false;

	try {
		const db = await getDb();
		const key = sessionKey(scope);
		const session = await db.get(STORE_NAME, key);

		if (!session) return false;

		// Check TTL expiration
		if (isSessionExpired(session)) {
			log.info('Session expired (TTL), clearing');
			await clear(scope);
			return false;
		}

		// Don't recover complete or idle sessions
		if (session.status === 'complete' || session.status === 'idle') {
			log.debug('Session in terminal state, not recoverable');
			return false;
		}

		// Must have some meaningful state to recover
		const hasImages = session.images && session.images.length > 0;
		const hasItems =
			(session.detectedItems && session.detectedItems.length > 0) ||
			(session.confirmedItems && session.confirmedItems.length > 0);

		return hasImages || hasItems;
	} catch (error) {
		log.warn('Error checking for recoverable session:', error);
		return false;
	}
}

/**
 * Get a summary of the stored session for the recovery UI.
 */
export async function getSessionSummary(
	scope = captureSessionScope()
): Promise<SessionSummary | null> {
	if (!browser) return null;
	if (!scope) return null;

	try {
		const db = await getDb();
		const key = sessionKey(scope);
		const session: StoredSession | undefined = await db.get(STORE_NAME, key);

		if (!session) return null;

		return {
			ageText: formatAge(session.updatedAt),
			imageCount: session.images?.length ?? 0,
			locationName: session.locationName,
			status: session.status,
			confirmedCount: session.confirmedItems?.length ?? 0,
		};
	} catch (error) {
		log.warn('Error getting session summary:', error);
		return null;
	}
}

/**
 * Load the stored session.
 * Returns null if no session exists, session is expired, or data is corrupted.
 */
export async function load(scope = captureSessionScope()): Promise<StoredSession | null> {
	if (!browser) return null;
	if (!scope) return null;

	try {
		const db = await getDb();
		const key = sessionKey(scope);
		const session: StoredSession | undefined = await db.get(STORE_NAME, key);

		if (!session) {
			log.debug('No stored session found');
			return null;
		}

		// Check TTL expiration
		if (isSessionExpired(session)) {
			const ageDays = Math.floor((Date.now() - session.createdAt) / (1000 * 60 * 60 * 24));
			log.info(`Session expired (${ageDays} days old), clearing`);
			await clear(scope);
			return null;
		}

		// Basic validation
		if (!session.id || typeof session.status !== 'string') {
			log.warn('Session data appears corrupted, clearing');
			await clear(scope);
			return null;
		}

		log.info(`Loaded session: status=${session.status}, images=${session.images?.length ?? 0}`);
		return session;
	} catch (error) {
		log.error('Error loading session:', error);
		// Clear corrupted data
		try {
			await clear(scope);
		} catch (clearError) {
			log.warn('Failed to clear corrupted session during recovery:', clearError);
		}
		return null;
	}
}

/**
 * Save the current session state.
 * Overwrites the existing session for the supplied identity and collection.
 */
export async function save(session: StoredSession, scope = captureSessionScope()): Promise<void> {
	if (!browser) {
		return;
	}
	if (!scope) {
		log.warn('Refusing to persist a scan without a verified context and collection');
		return;
	}

	try {
		const db = await getDb();
		const key = sessionKey(scope);

		// Update the updatedAt timestamp
		session.updatedAt = Date.now();

		await db.put(STORE_NAME, session, key);
		log.debug(`Saved session: status=${session.status}, images=${session.images?.length ?? 0}`);
	} catch (error) {
		// Extract meaningful error info for logging (avoids minified stack traces)
		const errorMessage = error instanceof Error ? error.message : String(error);
		const errorName = error instanceof Error ? error.name : 'Unknown';
		log.error(`Error saving session: [${errorName}] ${errorMessage}`);
		// Don't throw - persistence failures shouldn't break the workflow
	}
}

/**
 * Clear the stored session.
 * Called on successful submission, logout, "start fresh", etc.
 */
export async function clear(scope = captureSessionScope()): Promise<void> {
	if (!browser) return;
	if (!scope) return;

	try {
		const db = await getDb();
		await db.delete(STORE_NAME, sessionKey(scope));
		log.info('Session cleared');
	} catch (error) {
		log.warn('Error clearing session:', error);
		// Don't throw - cleanup failures are non-critical
	}
}
