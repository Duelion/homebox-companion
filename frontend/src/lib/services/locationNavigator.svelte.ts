/**
 * LocationNavigator - Handles location tree navigation and data fetching
 *
 * This service encapsulates all navigation logic for the location tree:
 * - Loading and refreshing location data from the API
 * - Managing navigation state (current location, loading state)
 * - Handling breadcrumb navigation
 * - Location selection and deselection
 *
 * Uses Svelte 5 runes for fine-grained reactivity.
 */
import { locations as locationsApi } from '$lib/api';
import { locationStore } from '$lib/stores/locations.svelte';
import { scanWorkflow } from '$lib/workflows/scan.svelte';
import { authStore } from '$lib/stores/auth.svelte';
import { showToast } from '$lib/stores/ui.svelte';
import { createLogger } from '$lib/utils/logger';
import type { Location } from '$lib/types';

const log = createLogger({ prefix: 'LocationNavigator' });

// =============================================================================
// LOCATION NAVIGATOR CLASS
// =============================================================================

class LocationNavigator {
	// =========================================================================
	// STATE
	// =========================================================================

	/** Loading state for navigation operations */
	private _isLoading = $state(false);

	/** Currently navigated location (the location we're viewing children of) */
	private _currentLocation = $state<Location | null>(null);
	private generation = 0;
	private operation = 0;

	/** Capture the navigation operation and session that own its data. */
	private guardOperation(start = true): () => boolean {
		const operation = start ? ++this.operation : this.operation;
		const generation = this.generation;
		const session = authStore.sessionGeneration;
		const connection = authStore.connection;
		const scope = authStore.verifiedScope;
		return () =>
			operation === this.operation &&
			generation === this.generation &&
			session === authStore.sessionGeneration &&
			connection === authStore.connection &&
			scope?.contextId === authStore.verifiedScope?.contextId &&
			scope?.groupId === authStore.verifiedScope?.groupId;
	}

	// =========================================================================
	// GETTERS
	// =========================================================================

	/** Get loading state */
	get isLoading(): boolean {
		return this._isLoading;
	}

	/** Get the currently navigated location */
	get currentLocation(): Location | null {
		return this._currentLocation;
	}

	/** Drop navigation state when the verified Homebox scope changes. */
	reset(): void {
		this.generation++;
		this._currentLocation = null;
		this._isLoading = false;
	}

	/** Persist a location and synchronize selection, breadcrumbs, search and workflow together. */
	async saveLocation(
		mode: 'create' | 'edit',
		data: { name: string; description: string; parentId: string | null }
	): Promise<void> {
		const selected = locationStore.selected;
		if (mode === 'edit' && !selected) throw new Error('Please select a location');
		const generation = this.generation;
		const session = authStore.sessionGeneration;
		const connection = authStore.connection;
		const scope = authStore.verifiedScope;
		const valid = () =>
			generation === this.generation &&
			session === authStore.sessionGeneration &&
			authStore.connection === connection &&
			authStore.verifiedScope?.contextId === scope?.contextId &&
			authStore.verifiedScope?.groupId === scope?.groupId;
		const pathIds = locationStore.path.map((part) => part.id).join('/');
		const sameView = () => locationStore.path.map((part) => part.id).join('/') === pathIds;
		const saved =
			mode === 'create'
				? await locationsApi.create({
						name: data.name,
						description: data.description,
						parent_id: data.parentId,
					})
				: await locationsApi.update(selected!.id, {
						name: data.name,
						description: data.description,
					});
		if (!valid()) return;

		if (mode === 'edit') {
			locationStore.setPath(
				locationStore.path.map((part) =>
					part.id === saved.id ? { id: saved.id, name: saved.name } : part
				)
			);
			if (this._currentLocation?.id === saved.id)
				this._currentLocation = { ...this._currentLocation, ...saved };
			if (locationStore.selected?.id === saved.id) {
				const updated = {
					...locationStore.selected,
					...saved,
					children: saved.children ?? locationStore.selected.children,
				};
				locationStore.setSelected(updated);
				scanWorkflow.setLocation(updated.id, updated.name, locationStore.selectedPath);
			}
		}

		// Saving succeeded even if this optional cache refresh fails.
		try {
			const tree = await locationsApi.tree();
			if (!valid()) return;
			locationStore.setTree(tree);
			locationStore.setFlatList(tree);
			if (sameView() && locationStore.path.length === 0) locationStore.setCurrentLevel(tree);
			const parentId = locationStore.path.at(-1)?.id;
			if (sameView() && parentId) {
				const details = await locationsApi.get(parentId);
				if (!valid() || !sameView()) return;
				this._currentLocation = details;
				locationStore.setCurrentLevel(details.children ?? []);
			}
		} catch (error) {
			if (valid()) log.warn('Failed to refresh locations after save', error);
		}
		if (valid())
			showToast(`Location "${saved.name}" ${mode === 'create' ? 'created' : 'updated'}`, 'success');
	}

	// =========================================================================
	// LOADING OPERATIONS
	// =========================================================================

	/**
	 * Load the location tree from the API.
	 * Sets the tree and current level to the root locations.
	 */
	async loadTree(): Promise<void> {
		const valid = this.guardOperation();
		log.debug('Loading location tree');
		this._isLoading = true;
		this._currentLocation = null;
		try {
			const tree = await locationsApi.tree();
			if (!valid()) return;
			log.debug('Loaded location tree, top-level count:', tree.length);
			locationStore.setTree(tree);
			locationStore.setCurrentLevel(tree);

			// Build flat list for search from the tree (preserves hierarchy for disambiguation)
			locationStore.setFlatList(tree);
		} catch (error) {
			if (!valid() || (error instanceof Error && error.name === 'AbortError')) return;
			log.error('Failed to load locations', error);
			showToast('Failed to load locations', 'error');
		} finally {
			if (valid()) this._isLoading = false;
		}
	}

	/**
	 * Refresh the current navigation level.
	 * If parentId is provided, refreshes that location's children.
	 * If parentId is null, refreshes the root level.
	 */
	async refreshCurrentLevel(parentId: string | null): Promise<void> {
		const valid = this.guardOperation();
		log.debug('Refreshing current level, parentId:', parentId);
		this._isLoading = true;
		try {
			if (parentId) {
				// Refresh children of the parent location
				const details = await locationsApi.get(parentId);
				if (!valid()) return;
				locationStore.setCurrentLevel(details.children || []);
				// Update the current navigated location with fresh data
				this._currentLocation = {
					id: details.id,
					name: details.name,
					description: details.description || '',
					itemCount: details.itemCount ?? 0,
					children: details.children || [],
				};

				// Also refresh the global tree cache to keep it in sync
				const tree = await locationsApi.tree();
				if (!valid()) return;
				locationStore.setTree(tree);
			} else {
				// Refresh top-level locations (tree fetch covers both tree cache and current level)
				const tree = await locationsApi.tree();
				if (!valid()) return;
				locationStore.setTree(tree);
				locationStore.setCurrentLevel(tree);
				this._currentLocation = null;
			}

			// Also refresh flat list for search from the refreshed tree
			locationStore.setFlatList(locationStore.tree);
		} catch (error) {
			if (!valid() || (error instanceof Error && error.name === 'AbortError')) return;
			log.error('Failed to refresh current level', error);
			showToast('Failed to refresh locations', 'error');
		} finally {
			if (valid()) this._isLoading = false;
		}
	}

	/**
	 * Update breadcrumb names by fetching fresh data for each path item.
	 * This is useful after a refresh to pick up any renamed locations.
	 */
	async updateBreadcrumbNames(): Promise<void> {
		const valid = this.guardOperation(false);
		const path = locationStore.path;
		if (path.length === 0) return;

		try {
			// Fetch all locations in path to check for name changes
			const updates = await Promise.all(
				path.map(async (item) => {
					const details = await locationsApi.get(item.id);
					return { id: item.id, name: details.name };
				})
			);

			if (!valid()) return;

			// Only update if names changed
			const hasChanges = updates.some((u, i) => u.name !== path[i].name);
			if (hasChanges) {
				locationStore.setPath(updates);
				log.debug('Updated breadcrumb names after refresh');
			}
		} catch (error) {
			if (!valid() || (error instanceof Error && error.name === 'AbortError')) return;
			log.warn('Failed to update breadcrumb names', error);
			// Don't show error toast - this is a non-critical enhancement
		}
	}

	// =========================================================================
	// NAVIGATION OPERATIONS
	// =========================================================================

	/**
	 * Navigate into a location, showing its children.
	 */
	async navigateInto(location: Location): Promise<void> {
		const valid = this.guardOperation();
		log.debug('Navigating into location:', location.name, location.id);
		this._isLoading = true;
		try {
			const details = await locationsApi.get(location.id);
			if (!valid()) return;
			log.debug('Loaded location details, children:', details.children?.length ?? 0);
			// Use API-fresh name in case the location was renamed
			locationStore.pushPath({ id: details.id, name: details.name });
			locationStore.setCurrentLevel(details.children || []);
			// Store the current location with all its data including itemCount
			this._currentLocation = {
				id: details.id,
				name: details.name,
				description: details.description || '',
				itemCount: details.itemCount ?? 0,
				children: details.children || [],
			};
		} catch (error) {
			if (!valid() || (error instanceof Error && error.name === 'AbortError')) return;
			log.error('Failed to load location details', error);
			showToast('Failed to load location details', 'error');
			// Fallback to using existing children data
			locationStore.pushPath({ id: location.id, name: location.name });
			locationStore.setCurrentLevel(location.children || []);
			this._currentLocation = location;
		} finally {
			if (valid()) this._isLoading = false;
		}
	}

	/**
	 * Navigate to a specific path index (breadcrumb navigation).
	 * Index -1 navigates to root.
	 */
	async navigateToPath(index: number): Promise<void> {
		const valid = this.guardOperation();
		if (index === -1) {
			// Navigate back to root - refresh tree to ensure it's current
			this._isLoading = true;
			this._currentLocation = null;
			try {
				const tree = await locationsApi.tree();
				if (!valid()) return;
				locationStore.setTree(tree);
				locationStore.setPath([]);
				locationStore.setCurrentLevel(tree);
			} catch (error) {
				if (!valid() || (error instanceof Error && error.name === 'AbortError')) return;
				log.error('Failed to refresh root locations', error);
				showToast('Failed to load locations', 'error');
				// Fallback to cached tree
				locationStore.setPath([]);
				locationStore.setCurrentLevel(locationStore.tree);
			} finally {
				if (valid()) this._isLoading = false;
			}
		} else {
			// Save current state before making changes (for error recovery)
			const previousPath = [...locationStore.path];
			const previousCurrentLevel = [...locationStore.currentLevel];
			const previousCurrentLocation = this._currentLocation;

			// Slice path to target index
			locationStore.slicePath(index);
			const newPath = locationStore.path;

			// Fetch fresh details for the target location to ensure children are up-to-date
			const targetId = newPath[newPath.length - 1].id;
			this._isLoading = true;
			try {
				const details = await locationsApi.get(targetId);
				if (!valid()) return;
				locationStore.setCurrentLevel(details.children || []);
				// Store the navigated location
				this._currentLocation = {
					id: details.id,
					name: details.name,
					description: details.description || '',
					itemCount: details.itemCount ?? 0,
					children: details.children || [],
				};
			} catch (error) {
				if (!valid() || (error instanceof Error && error.name === 'AbortError')) return;
				log.error('Failed to load location details', error);
				showToast('Failed to navigate back', 'error');
				// Restore previous state on error to avoid inconsistent UI
				locationStore.setPath(previousPath);
				locationStore.setCurrentLevel(previousCurrentLevel);
				this._currentLocation = previousCurrentLocation;
			} finally {
				if (valid()) this._isLoading = false;
			}
		}
	}

	// =========================================================================
	// SELECTION OPERATIONS
	// =========================================================================

	/**
	 * Select a location for the scan workflow.
	 */
	selectLocation(location: Location, pathStr: string): void {
		log.debug('Selected location:', location.name, 'itemCount:', location.itemCount ?? 'unknown');
		// Update both the location store (for UI) and the workflow (for scan flow)
		locationStore.setSelected(location);
		scanWorkflow.setLocation(location.id, location.name, pathStr);
	}

	/**
	 * Clear the current selection and restore navigation state.
	 * Optionally accepts the previous path to restore navigation context.
	 */
	async clearSelection(): Promise<void> {
		const valid = this.guardOperation();
		const previousPath = [...locationStore.path];
		locationStore.setSelected(null);
		scanWorkflow.clearLocation();

		// If we had a path (user was inside a location), restore it
		if (previousPath.length > 0) {
			// Restore the path - user will be brought back to where they were browsing
			locationStore.setPath(previousPath);

			// Fetch the location details to get current children
			const lastPathItem = previousPath[previousPath.length - 1];
			this._isLoading = true;
			try {
				const details = await locationsApi.get(lastPathItem.id);
				if (!valid()) return;
				locationStore.setCurrentLevel(details.children || []);
				// Restore the current navigated location
				this._currentLocation = {
					id: details.id,
					name: details.name,
					description: details.description || '',
					itemCount: details.itemCount ?? 0,
					children: details.children || [],
				};
			} catch (error) {
				if (!valid() || (error instanceof Error && error.name === 'AbortError')) return;
				log.error('Failed to load location details', error);
				showToast('Failed to restore navigation', 'error');
			} finally {
				if (valid()) this._isLoading = false;
			}
		} else {
			// Was at root level - refresh to show any new locations
			this._isLoading = true;
			this._currentLocation = null;
			try {
				const tree = await locationsApi.tree();
				if (!valid()) return;
				locationStore.setTree(tree);
				locationStore.setPath([]);
				locationStore.setCurrentLevel(tree);
			} catch (error) {
				if (!valid() || (error instanceof Error && error.name === 'AbortError')) return;
				log.error('Failed to refresh locations', error);
				// Fallback to cached tree
				locationStore.setPath([]);
				locationStore.setCurrentLevel(locationStore.tree);
			} finally {
				if (valid()) this._isLoading = false;
			}
		}
	}

	/**
	 * Refresh the currently selected location's details.
	 */
	async refreshSelected(): Promise<void> {
		const valid = this.guardOperation();
		if (!locationStore.selected) return;

		this._isLoading = true;
		try {
			const details = await locationsApi.get(locationStore.selected.id);
			if (!valid()) return;
			locationStore.setSelected({
				id: details.id,
				name: details.name,
				description: details.description || '',
				itemCount: details.itemCount ?? 0,
				children: details.children || [],
			});
			// Update workflow if name changed
			if (details.name !== scanWorkflow.state.locationName) {
				scanWorkflow.setLocation(details.id, details.name, locationStore.selectedPath);
			}
			// Also update breadcrumb names in case parent locations were renamed
			await this.updateBreadcrumbNames();
		} catch (error) {
			if (!valid() || (error instanceof Error && error.name === 'AbortError')) return;
			log.error('Failed to refresh selected location', error);
			showToast('Failed to refresh location', 'error');
		} finally {
			if (valid()) this._isLoading = false;
		}
	}

	// =========================================================================
	// HELPERS
	// =========================================================================

	/**
	 * Get the current parent location info (for creating child locations).
	 * Returns null if at root level.
	 */
	getCurrentParent(): { id: string; name: string } | null {
		const path = locationStore.path;
		if (path.length === 0) return null;
		const last = path[path.length - 1];
		return { id: last.id, name: last.name };
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const locationNavigator = new LocationNavigator();
