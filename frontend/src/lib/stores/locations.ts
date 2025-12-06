/**
 * Location store
 */
import { writable, derived } from 'svelte/store';
import type { LocationData, LocationTreeNode } from '$lib/api';

// All locations (flat list)
export const allLocations = writable<LocationData[]>([]);

// Location tree (hierarchical)
export const locationTree = writable<LocationTreeNode[]>([]);

// Current navigation path (breadcrumb)
export interface PathItem {
	id: string;
	name: string;
}
export const locationPath = writable<PathItem[]>([]);

// Currently displayed locations (at current level)
export const currentLevelLocations = writable<LocationData[]>([]);

// Selected location
export const selectedLocation = writable<LocationData | null>(null);

// Full path string for display
export const selectedLocationPath = derived(
	[locationPath, selectedLocation],
	([$path, $selected]) => {
		if (!$selected) return '';
		const pathNames = $path.map((p) => p.name);
		pathNames.push($selected.name);
		return pathNames.join(' / ');
	}
);

// Reset location state
export function resetLocationState() {
	locationPath.set([]);
	currentLevelLocations.set([]);
	selectedLocation.set(null);
}








