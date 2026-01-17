/**
 * Session Persistence Service
 *
 * Provides IndexedDB-based persistence for scan workflow sessions.
 * Enables crash recovery by storing workflow state that survives page reloads.
 *
 * Key design decisions:
 * - Uses IndexedDB (via idb library) for storage > 5MB limit of localStorage
 * - Single-session pattern: only ONE session stored at a time (no accumulation)
 * - TTL-based cleanup: sessions auto-expire after 7 days
 * - Explicit persistence: no $effect watchers, manual save() calls only
 */

import { browser } from '$app/environment';
import { openDB, type IDBPDatabase } from 'idb';
import type { StoredSession } from './serialize';
import { createLogger } from '$lib/utils/logger';

const log = createLogger({ prefix: 'SessionPersistence' });

// =============================================================================
// CONSTANTS
// =============================================================================

const DB_NAME = 'hbc-scan-recovery';
const DB_VERSION = 1;
const STORE_NAME = 'sessions';
const SESSION_KEY = 'current';

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
				// Clear old data on schema change
				if (db.objectStoreNames.contains(STORE_NAME)) {
					db.deleteObjectStore(STORE_NAME);
				}
				db.createObjectStore(STORE_NAME);
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
export async function hasRecoverableSession(): Promise<boolean> {
	if (!browser) return false;

	try {
		const db = await getDb();
		const session = await db.get(STORE_NAME, SESSION_KEY);

		if (!session) return false;

		// Check TTL expiration
		if (isSessionExpired(session)) {
			log.info('Session expired (TTL), clearing');
			await clear();
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
export async function getSessionSummary(): Promise<SessionSummary | null> {
	if (!browser) return null;

	try {
		const db = await getDb();
		const session: StoredSession | undefined = await db.get(STORE_NAME, SESSION_KEY);

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
export async function load(): Promise<StoredSession | null> {
	if (!browser) return null;

	try {
		const db = await getDb();
		const session: StoredSession | undefined = await db.get(STORE_NAME, SESSION_KEY);

		if (!session) {
			log.debug('No stored session found');
			return null;
		}

		// Check TTL expiration
		if (isSessionExpired(session)) {
			const ageDays = Math.floor((Date.now() - session.createdAt) / (1000 * 60 * 60 * 24));
			log.info(`Session expired (${ageDays} days old), clearing`);
			await clear();
			return null;
		}

		// Basic validation
		if (!session.id || typeof session.status !== 'string') {
			log.warn('Session data appears corrupted, clearing');
			await clear();
			return null;
		}

		log.info(`Loaded session: status=${session.status}, images=${session.images?.length ?? 0}`);
		return session;
	} catch (error) {
		log.error('Error loading session:', error);
		// Clear corrupted data
		try {
			await clear();
		} catch (clearError) {
			log.warn('Failed to clear corrupted session during recovery:', clearError);
		}
		return null;
	}
}

/**
 * Save the current session state.
 * Overwrites any existing session (single-session guarantee).
 */
export async function save(session: StoredSession): Promise<void> {
	if (!browser) {
		return;
	}

	try {
		const db = await getDb();

		// Update the updatedAt timestamp
		session.updatedAt = Date.now();

		await db.put(STORE_NAME, session, SESSION_KEY);
		log.debug(`Saved session: status=${session.status}, images=${session.images?.length ?? 0}`);
	} catch (error) {
		log.error('Error saving session:', error);
		// Don't throw - persistence failures shouldn't break the workflow
	}
}

/**
 * Clear the stored session.
 * Called on successful submission, logout, "start fresh", etc.
 */
export async function clear(): Promise<void> {
	if (!browser) return;

	try {
		const db = await getDb();
		await db.delete(STORE_NAME, SESSION_KEY);
		log.info('Session cleared');
	} catch (error) {
		log.warn('Error clearing session:', error);
		// Don't throw - cleanup failures are non-critical
	}
}
