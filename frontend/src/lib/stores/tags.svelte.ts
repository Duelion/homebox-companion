/**
 * Tags Store - Svelte 5 Class-based State
 *
 * Tags are cached after the first fetch to avoid redundant API calls.
 * The cache is cleared on logout via the auth store calling clearTagsCache.
 */
import { tags as tagsApi } from '$lib/api';
import type { Tag } from '$lib/types';
import { createLogger } from '$lib/utils/logger';

const log = createLogger({ prefix: 'TagStore' });

// =============================================================================
// TAGS STORE CLASS
// =============================================================================

class TagsStore {
	// =========================================================================
	// STATE
	// =========================================================================

	/** Cached tags data */
	private _tags = $state<Tag[]>([]);

	/** Whether tags have been fetched at least once */
	private _fetched = $state(false);

	/** Whether tags are currently being fetched */
	private _loading = $state(false);

	/** Error message from last fetch attempt */
	private _error = $state<string | null>(null);

	/**
	 * Track pending fetch to deduplicate concurrent requests.
	 * Intentionally NOT using $state - this is internal bookkeeping only,
	 * not exposed to consumers and does not need to trigger reactivity.
	 */
	private _pendingFetch: Promise<Tag[]> | null = null;

	/** Cached tags indexed by ID - recomputed only when _tags changes */
	private _tagsById = $derived.by(() => {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- Derived value, not mutable state
		const map = new Map<string, Tag>();
		for (const tag of this._tags) {
			map.set(tag.id, tag);
		}
		return map;
	});

	// =========================================================================
	// GETTERS (read-only access to state)
	// =========================================================================

	/** Get all tags */
	get tags(): Tag[] {
		return this._tags;
	}

	/** Check if tags have been fetched */
	get fetched(): boolean {
		return this._fetched;
	}

	/** Check if tags are loading */
	get loading(): boolean {
		return this._loading;
	}

	/** Get the last error */
	get error(): string | null {
		return this._error;
	}

	/** Get tags indexed by ID (cached via $derived) */
	get tagsById(): Map<string, Tag> {
		return this._tagsById;
	}

	// =========================================================================
	// METHODS
	// =========================================================================

	/**
	 * Fetch tags from API if not already cached.
	 * Returns cached data if available.
	 */
	async fetchTags(forceRefresh = false): Promise<Tag[]> {
		// Return cached data if available and not forcing refresh
		if (this._fetched && !forceRefresh) {
			return this._tags;
		}

		// Return existing fetch promise if one is in progress (deduplication)
		if (this._pendingFetch) {
			return this._pendingFetch;
		}

		this._loading = true;
		this._error = null;

		this._pendingFetch = this.doFetch();
		return this._pendingFetch;
	}

	/** Internal fetch implementation */
	private async doFetch(): Promise<Tag[]> {
		try {
			const data = await tagsApi.list();
			this._tags = data;
			this._fetched = true;
			return data;
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to fetch tags';
			this._error = message;
			throw error;
		} finally {
			this._loading = false;
			this._pendingFetch = null;
		}
	}

	/**
	 * Clear the tags cache.
	 * Called on logout or when tags might have changed.
	 */
	clear(): void {
		this._tags = [];
		this._fetched = false;
		this._error = null;
		this._pendingFetch = null;
	}

	/**
	 * Get tag name by ID from cache.
	 * Returns undefined if tag not found.
	 */
	getTagName(tagId: string): string | undefined {
		return this.tagsById.get(tagId)?.name;
	}

	/**
	 * Filter tag IDs to only include valid ones that exist in the current cache.
	 * Logs any invalid IDs at warn level for debugging.
	 *
	 * @param ids - Array of tag IDs to validate
	 * @returns Filtered array containing only valid tag IDs
	 */
	validateIds(ids: string[] | null | undefined): string[] {
		if (!ids || ids.length === 0) {
			return [];
		}

		const validIds: string[] = [];
		const invalidIds: string[] = [];

		for (const id of ids) {
			if (this._tagsById.has(id)) {
				validIds.push(id);
			} else {
				invalidIds.push(id);
			}
		}

		if (invalidIds.length > 0) {
			log.warn(`Filtered out ${invalidIds.length} invalid tag ID(s):`, invalidIds);
		}

		return validIds;
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const tagStore = new TagsStore();

// =============================================================================
// FUNCTION EXPORTS
// =============================================================================

export const fetchTags = (forceRefresh = false) => tagStore.fetchTags(forceRefresh);
export const clearTagsCache = () => tagStore.clear();
