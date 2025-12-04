/**
 * Labels store with caching
 * 
 * Labels are cached after the first fetch to avoid redundant API calls.
 * The cache is cleared on logout or can be manually refreshed.
 */
import { writable, derived, get } from 'svelte/store';
import { labels as labelsApi, type LabelData } from '$lib/api';
import { token } from './auth';

// Cached labels data
const labelsData = writable<LabelData[]>([]);
const labelsFetched = writable<boolean>(false);
const labelsLoading = writable<boolean>(false);
const labelsError = writable<string | null>(null);

// Derived store for label lookup by ID
export const labelsById = derived(labelsData, ($labels) => {
	const map = new Map<string, LabelData>();
	for (const label of $labels) {
		map.set(label.id, label);
	}
	return map;
});

// Export the labels array
export const labels = {
	subscribe: labelsData.subscribe,
};

// Export loading state
export const isLabelsLoading = {
	subscribe: labelsLoading.subscribe,
};

/**
 * Fetch labels from API if not already cached.
 * Returns cached data if available.
 */
export async function fetchLabels(forceRefresh = false): Promise<LabelData[]> {
	// Return cached data if available and not forcing refresh
	if (get(labelsFetched) && !forceRefresh) {
		return get(labelsData);
	}

	// Don't fetch if already loading
	if (get(labelsLoading)) {
		// Wait for current fetch to complete
		return new Promise((resolve) => {
			const unsubscribe = labelsLoading.subscribe((loading) => {
				if (!loading) {
					unsubscribe();
					resolve(get(labelsData));
				}
			});
		});
	}

	labelsLoading.set(true);
	labelsError.set(null);

	try {
		const data = await labelsApi.list();
		labelsData.set(data);
		labelsFetched.set(true);
		return data;
	} catch (error) {
		const message = error instanceof Error ? error.message : 'Failed to fetch labels';
		labelsError.set(message);
		throw error;
	} finally {
		labelsLoading.set(false);
	}
}

/**
 * Clear the labels cache.
 * Called on logout or when labels might have changed.
 */
export function clearLabelsCache(): void {
	labelsData.set([]);
	labelsFetched.set(false);
	labelsError.set(null);
}

/**
 * Get label name by ID from cache.
 * Returns undefined if label not found.
 */
export function getLabelName(labelId: string): string | undefined {
	return get(labelsById).get(labelId)?.name;
}

// Clear cache when user logs out
token.subscribe((value) => {
	if (!value) {
		clearLabelsCache();
	}
});

