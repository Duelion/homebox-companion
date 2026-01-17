/**
 * Labels Store - Svelte 5 Class-based State
 *
 * Labels are cached after the first fetch to avoid redundant API calls.
 * The cache is cleared on logout via the auth store calling clearLabelsCache.
 */
import { labels as labelsApi, type LabelData } from '$lib/api';
import { createLogger } from '$lib/utils/logger';

const log = createLogger({ prefix: 'LabelStore' });

// =============================================================================
// LABELS STORE CLASS
// =============================================================================

class LabelsStore {
	// =========================================================================
	// STATE
	// =========================================================================

	/** Cached labels data */
	private _labels = $state<LabelData[]>([]);

	/** Whether labels have been fetched at least once */
	private _fetched = $state(false);

	/** Whether labels are currently being fetched */
	private _loading = $state(false);

	/** Error message from last fetch attempt */
	private _error = $state<string | null>(null);

	/**
	 * Track pending fetch to deduplicate concurrent requests.
	 * Intentionally NOT using $state - this is internal bookkeeping only,
	 * not exposed to consumers and does not need to trigger reactivity.
	 */
	private _pendingFetch: Promise<LabelData[]> | null = null;

	/** Cached labels indexed by ID - recomputed only when _labels changes */
	private _labelsById = $derived.by(() => {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- Derived value, not mutable state
		const map = new Map<string, LabelData>();
		for (const label of this._labels) {
			map.set(label.id, label);
		}
		return map;
	});

	// =========================================================================
	// GETTERS (read-only access to state)
	// =========================================================================

	/** Get all labels */
	get labels(): LabelData[] {
		return this._labels;
	}

	/** Check if labels have been fetched */
	get fetched(): boolean {
		return this._fetched;
	}

	/** Check if labels are loading */
	get loading(): boolean {
		return this._loading;
	}

	/** Get the last error */
	get error(): string | null {
		return this._error;
	}

	/** Get labels indexed by ID (cached via $derived) */
	get labelsById(): Map<string, LabelData> {
		return this._labelsById;
	}

	// =========================================================================
	// METHODS
	// =========================================================================

	/**
	 * Fetch labels from API if not already cached.
	 * Returns cached data if available.
	 */
	async fetchLabels(forceRefresh = false): Promise<LabelData[]> {
		// Return cached data if available and not forcing refresh
		if (this._fetched && !forceRefresh) {
			return this._labels;
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
	private async doFetch(): Promise<LabelData[]> {
		try {
			const data = await labelsApi.list();
			this._labels = data;
			this._fetched = true;
			return data;
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to fetch labels';
			this._error = message;
			throw error;
		} finally {
			this._loading = false;
			this._pendingFetch = null;
		}
	}

	/**
	 * Clear the labels cache.
	 * Called on logout or when labels might have changed.
	 */
	clear(): void {
		this._labels = [];
		this._fetched = false;
		this._error = null;
		this._pendingFetch = null;
	}

	/**
	 * Get label name by ID from cache.
	 * Returns undefined if label not found.
	 */
	getLabelName(labelId: string): string | undefined {
		return this.labelsById.get(labelId)?.name;
	}

	/**
	 * Filter label IDs to only include valid ones that exist in the current cache.
	 * Logs any invalid IDs at warn level for debugging.
	 *
	 * @param ids - Array of label IDs to validate
	 * @returns Filtered array containing only valid label IDs
	 */
	validateIds(ids: string[] | null | undefined): string[] {
		if (!ids || ids.length === 0) {
			return [];
		}

		const validIds: string[] = [];
		const invalidIds: string[] = [];

		for (const id of ids) {
			if (this._labelsById.has(id)) {
				validIds.push(id);
			} else {
				invalidIds.push(id);
			}
		}

		if (invalidIds.length > 0) {
			log.warn(
				`Filtered out ${invalidIds.length} invalid label ID(s):`,
				invalidIds
			);
		}

		return validIds;
	}

}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const labelStore = new LabelsStore();

// =============================================================================
// FUNCTION EXPORTS
// =============================================================================

export const fetchLabels = (forceRefresh = false) => labelStore.fetchLabels(forceRefresh);
export const clearLabelsCache = () => labelStore.clear();
