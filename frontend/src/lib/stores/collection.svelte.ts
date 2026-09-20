/**
 * Collection Store - Svelte 5 Class-based State
 *
 * Manages the active Homebox group (collection) selection.
 * Persists the selected group to localStorage so it survives page refreshes.
 *
 * When the user switches collections, dependent stores (locations, tags, scan workflow)
 * must be cleared and re-fetched. This is triggered by consumers watching `selectedId`.
 */
import { browser } from '$app/environment';
import type { Group } from '$lib/types';
import { groups as groupsApi } from '$lib/api';
import { setActiveGroupId } from '$lib/api/client';
import { createLogger } from '$lib/utils/logger';

const log = createLogger({ prefix: 'CollectionStore' });

// =============================================================================
// CONSTANTS
// =============================================================================

const GROUP_ID_KEY = 'hbc_group_id';

// =============================================================================
// INITIAL STATE FROM STORAGE
// =============================================================================

const storedGroupId = browser ? localStorage.getItem(GROUP_ID_KEY) : null;

// =============================================================================
// COLLECTION STORE CLASS
// =============================================================================

class CollectionStore {
	// =========================================================================
	// STATE
	// =========================================================================

	/** All groups the user belongs to */
	private _groups = $state<Group[]>([]);

	/** Currently selected group ID (persisted in localStorage) */
	private _selectedId = $state<string | null>(storedGroupId);

	/** Whether groups are currently being fetched */
	private _loading = $state(false);
	private _error = $state<string | null>(null);
	private _ready = $state(false);

	// =========================================================================
	// DERIVED
	// =========================================================================

	/** The currently selected group object */
	private _selectedGroup = $derived.by(() => {
		if (!this._selectedId) return this._groups[0] ?? null;
		return this._groups.find((g) => g.id === this._selectedId) ?? this._groups[0] ?? null;
	});

	/** Whether the user has multiple groups (determines dropdown visibility) */
	private _hasMultiple = $derived(this._groups.length > 1);

	// =========================================================================
	// GETTERS (read-only access to state)
	// =========================================================================

	/** Get all groups */
	get groups(): Group[] {
		return this._groups;
	}

	/** Get the selected group ID */
	get selectedId(): string | null {
		return this._selectedGroup?.id ?? null;
	}

	/** Get the selected group object */
	get selectedGroup(): Group | null {
		return this._selectedGroup;
	}

	/** Check if user has multiple groups */
	get hasMultiple(): boolean {
		return this._hasMultiple;
	}

	/** Check if groups are loading */
	get loading(): boolean {
		return this._loading;
	}
	get ready(): boolean {
		return this._ready;
	}
	get error(): string | null {
		return this._error;
	}

	// =========================================================================
	// METHODS
	// =========================================================================

	/**
	 * Fetch all groups the user belongs to.
	 * Restores the previously selected group if still valid.
	 */
	async fetchGroups(defaultGroupId?: string | null): Promise<void> {
		this._loading = true;
		this._ready = false;
		this._error = null;
		setActiveGroupId(null);
		try {
			const fetchedGroups = await groupsApi.list();
			this._groups = fetchedGroups;
			if (!this._selectedId) {
				this._selectedId =
					(defaultGroupId && fetchedGroups.some((group) => group.id === defaultGroupId)
						? defaultGroupId
						: fetchedGroups[0]?.id) ?? null;
				this.persistSelection();
			}

			// Validate stored selection — if the stored group ID is no longer valid,
			// fall back to the first group
			if (this._selectedId && !fetchedGroups.some((g) => g.id === this._selectedId)) {
				log.info(`Previously selected group ${this._selectedId} no longer valid, resetting`);
				this._selectedId =
					(defaultGroupId && fetchedGroups.some((group) => group.id === defaultGroupId)
						? defaultGroupId
						: fetchedGroups[0]?.id) ?? null;
				this.persistSelection();
			}

			// Sync active group to API client for X-Group-Id header injection
			setActiveGroupId(this.selectedId);

			log.debug(`Fetched ${fetchedGroups.length} group(s)`);
			this._ready = true;
		} catch (err) {
			log.warn('Failed to fetch groups:', err);
			this._groups = [];
			this._error = err instanceof Error ? err.message : 'Failed to load collections';
			throw err;
		} finally {
			this._loading = false;
		}
	}

	/**
	 * Select a different group (collection).
	 * Returns true if the selection actually changed (so callers can trigger data refresh).
	 */
	selectGroup(id: string): boolean {
		const previousId = this._selectedId;
		this._selectedId = id;
		this.persistSelection();
		setActiveGroupId(id);

		const changed = previousId !== id;
		if (changed) {
			log.info(`Switched from ${previousId} to ${id}`);
			void import('./chat.svelte').then(({ chatStore }) => chatStore.invalidateContext());
		}
		return changed;
	}

	/** Clear all state (called on logout) */
	clear(): void {
		this._groups = [];
		this._selectedId = null;
		this._ready = false;
		this._error = null;
		setActiveGroupId(null);
		if (browser) {
			localStorage.removeItem(GROUP_ID_KEY);
		}
	}

	// =========================================================================
	// PRIVATE HELPERS
	// =========================================================================

	private persistSelection(): void {
		if (browser) {
			if (this._selectedId) {
				localStorage.setItem(GROUP_ID_KEY, this._selectedId);
			} else {
				localStorage.removeItem(GROUP_ID_KEY);
			}
		}
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const collectionStore = new CollectionStore();
