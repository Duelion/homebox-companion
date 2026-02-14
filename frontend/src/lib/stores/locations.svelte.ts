/**
 * Location Store - Svelte 5 Class-based State
 *
 * Manages location tree navigation state using Svelte 5 runes for fine-grained reactivity.
 *
 * Note: Auth cleanup (clearing location state on logout) is handled explicitly
 * in the auth.svelte.ts logout() function to avoid memory leaks from unsubscribed listeners.
 */
import type { Location, LocationTreeNode } from '$lib/types';
import { SvelteMap } from 'svelte/reactivity';

// =============================================================================
// TYPES
// =============================================================================

/** Breadcrumb path item */
export interface PathItem {
	id: string;
	name: string;
}

/** Flattened location for search */
export interface FlatLocation {
	location: Location;
	path: string;
	/** Disambiguated display name (includes parent path only if duplicates exist) */
	displayName: string;
}

// =============================================================================
// LOCATION STORE CLASS
// =============================================================================

class LocationStore {
	// =========================================================================
	// STATE
	// =========================================================================

	/** Location tree (hierarchical structure from API) */
	private _tree = $state<LocationTreeNode[]>([]);

	/** Current navigation path (breadcrumb trail) */
	private _path = $state<PathItem[]>([]);

	/** Locations at current navigation level */
	private _currentLevel = $state<Location[]>([]);

	/** Currently selected location */
	private _selected = $state<Location | null>(null);

	/** Flat list of all locations for search */
	private _flatList = $state<FlatLocation[]>([]);

	// =========================================================================
	// GETTERS (read-only access to state)
	// =========================================================================

	/** Get the location tree */
	get tree(): LocationTreeNode[] {
		return this._tree;
	}

	/** Get the current navigation path */
	get path(): PathItem[] {
		return this._path;
	}

	/** Get locations at the current navigation level */
	get currentLevel(): Location[] {
		return this._currentLevel;
	}

	/** Get the selected location */
	get selected(): Location | null {
		return this._selected;
	}

	/** Get the flat list for search */
	get flatList(): FlatLocation[] {
		return this._flatList;
	}

	/** Compute the full path string for the selected location */
	get selectedPath(): string {
		if (!this._selected) return '';
		const pathNames = this._path.map((p) => p.name);
		// Only append selected name if not already the last path item
		const lastPathItem = this._path[this._path.length - 1];
		if (!lastPathItem || lastPathItem.id !== this._selected.id) {
			pathNames.push(this._selected.name);
		}
		return pathNames.join(' / ');
	}

	// =========================================================================
	// SETTERS (controlled mutations)
	// =========================================================================

	/** Set the location tree */
	setTree(tree: LocationTreeNode[]): void {
		this._tree = tree;
	}

	/** Set the current navigation path */
	setPath(path: PathItem[]): void {
		this._path = path;
	}

	/** Update path by appending a new item */
	pushPath(item: PathItem): void {
		this._path = [...this._path, item];
	}

	/** Slice path to a specific index (for breadcrumb navigation) */
	slicePath(toIndex: number): void {
		if (toIndex < 0) {
			this._path = [];
		} else {
			this._path = this._path.slice(0, toIndex + 1);
		}
	}

	/** Set locations at current navigation level */
	setCurrentLevel(locations: Location[]): void {
		this._currentLevel = locations;
	}

	/** Set the selected location */
	setSelected(location: Location | null): void {
		this._selected = location;
	}

	/** Build the flat search list from the hierarchical tree */
	setFlatList(tree: LocationTreeNode[]): void {
		const flat = this.flattenLocations(tree, '');
		this._flatList = this.computeDisambiguatedNames(flat);
	}

	// =========================================================================
	// HELPERS
	// =========================================================================

	/**
	 * Flatten a hierarchical location list into a flat list with path strings.
	 * Used for search functionality. displayName is set initially to just the name,
	 * and will be updated by computeDisambiguatedNames.
	 */
	private flattenLocations(locations: Location[], parentPath: string): FlatLocation[] {
		const result: FlatLocation[] = [];
		for (const loc of locations) {
			const currentPath = parentPath ? `${parentPath} › ${loc.name}` : loc.name;
			result.push({ location: loc, path: currentPath, displayName: loc.name });
			if (loc.children && loc.children.length > 0) {
				result.push(...this.flattenLocations(loc.children, currentPath));
			}
		}
		return result;
	}

	/**
	 * Compute disambiguated display names for locations with duplicate names.
	 * Shows parent path progressively until the name becomes unique.
	 */
	private computeDisambiguatedNames(locations: FlatLocation[]): FlatLocation[] {
		// Group locations by name to find duplicates
		const nameGroups = new SvelteMap<string, FlatLocation[]>();
		for (const loc of locations) {
			const name = loc.location.name;
			if (!nameGroups.has(name)) {
				nameGroups.set(name, []);
			}
			nameGroups.get(name)!.push(loc);
		}

		// For each location, compute display name
		return locations.map((loc) => {
			const siblings = nameGroups.get(loc.location.name)!;
			if (siblings.length === 1) {
				// Unique name - no disambiguation needed
				return loc; // displayName already set to loc.name
			}
			// Has duplicates - show progressive path until unique
			return { ...loc, displayName: this.getMinimalPath(loc, siblings) };
		});
	}

	/**
	 * Get the minimal path suffix that uniquely identifies this location
	 * among its siblings with the same name.
	 */
	private getMinimalPath(loc: FlatLocation, siblings: FlatLocation[]): string {
		const pathParts = loc.path.split(' › ');

		// Start with just the name, progressively add parents until unique
		for (let depth = 1; depth <= pathParts.length; depth++) {
			const candidate = pathParts.slice(-depth).join(' › ');
			// Count how many siblings match this suffix as a complete path segment
			// Must either be exact match OR have separator before the suffix
			const matches = siblings.filter(
				(s) => s.path === candidate || s.path.endsWith(' › ' + candidate)
			);
			if (matches.length === 1) {
				return candidate;
			}
		}
		// Full path if still not unique (edge case - shouldn't normally happen)
		return loc.path;
	}

	/** Reset navigation state (clears path, current level, and selection) */
	reset(): void {
		this._path = [];
		this._currentLevel = [];
		this._selected = null;
	}

	/** Clear all state (called on logout) */
	clear(): void {
		this._tree = [];
		this._flatList = [];
		this.reset();
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const locationStore = new LocationStore();

// =============================================================================
// BACKWARD COMPATIBILITY
// =============================================================================

/**
 * Reset location state (clears selection and navigation).
 * This is a convenience export for backward compatibility.
 */
export function resetLocationState(): void {
	locationStore.reset();
}
