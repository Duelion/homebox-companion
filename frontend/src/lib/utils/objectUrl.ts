/**
 * Utility for managing object URLs with proper cleanup.
 *
 * Object URLs created via URL.createObjectURL() hold references to underlying
 * file data and must be explicitly revoked to avoid memory leaks.
 */

/**
 * Cache for object URLs keyed by File reference.
 * Uses WeakMap so entries are automatically cleaned up when File objects
 * are garbage collected.
 */
const urlCache = new WeakMap<File, string>();

/**
 * Registry for tracking fetched blob URLs by their endpoint/key.
 * Unlike File-based URLs, fetched URLs need explicit key management.
 *
 * Uses a Map with LRU eviction to prevent unbounded memory growth
 * in long-running sessions. When the registry exceeds MAX_REGISTRY_SIZE,
 * the oldest entries are revoked and removed.
 */
const fetchedUrlRegistry = new Map<string, string>();

/** Maximum number of entries in the fetched URL registry before LRU eviction */
const MAX_REGISTRY_SIZE = 100;

/** Number of entries to evict when registry is full (batch eviction for efficiency) */
const EVICTION_BATCH_SIZE = 20;

/**
 * Get or create an object URL for a File.
 * The URL is cached per File reference to avoid creating duplicates.
 *
 * @param file - The File to create a URL for
 * @returns The object URL string
 */
export function getObjectUrl(file: File): string {
	let url = urlCache.get(file);
	if (!url) {
		url = URL.createObjectURL(file);
		urlCache.set(file, url);
	}
	return url;
}

/**
 * Revoke an object URL for a File and remove it from the cache.
 *
 * @param file - The File whose URL should be revoked
 */
export function revokeObjectUrl(file: File): void {
	const url = urlCache.get(file);
	if (url) {
		URL.revokeObjectURL(url);
		urlCache.delete(file);
	}
}

/**
 * Revoke object URLs for multiple Files.
 *
 * @param files - Array of Files whose URLs should be revoked
 */
export function revokeObjectUrls(files: File[]): void {
	for (const file of files) {
		revokeObjectUrl(file);
	}
}

/**
 * Create an object URL manager for component-scoped cleanup.
 * Tracks all URLs created in the component and provides a cleanup function.
 *
 * Usage in Svelte 5:
 * ```
 * const urlManager = createObjectUrlManager();
 *
 * $effect(() => {
 *   return () => urlManager.cleanup();
 * });
 *
 * // Get URLs - they're automatically tracked
 * const url = urlManager.getUrl(file);
 * ```
 */
export function createObjectUrlManager() {
	const trackedFiles = new Set<File>();

	return {
		/**
		 * Get or create an object URL for a File, tracking it for cleanup.
		 */
		getUrl(file: File): string {
			trackedFiles.add(file);
			return getObjectUrl(file);
		},

		/**
		 * Revoke a specific file's URL and stop tracking it.
		 */
		revoke(file: File): void {
			if (trackedFiles.has(file)) {
				revokeObjectUrl(file);
				trackedFiles.delete(file);
			}
		},

		/**
		 * Revoke all tracked URLs. Call this in cleanup/destroy.
		 */
		cleanup(): void {
			for (const file of trackedFiles) {
				revokeObjectUrl(file);
			}
			trackedFiles.clear();
		},

		/**
		 * Update tracking: revoke URLs for files no longer in use.
		 * Call this when the file list changes to clean up removed files.
		 */
		sync(currentFiles: File[]): void {
			const currentSet = new Set(currentFiles);
			for (const file of trackedFiles) {
				if (!currentSet.has(file)) {
					revokeObjectUrl(file);
					trackedFiles.delete(file);
				}
			}
		},
	};
}

/**
 * Register a fetched blob URL for a given key (typically an API endpoint).
 * If there's an existing URL for this key, it will be revoked first.
 *
 * Implements LRU eviction: when the registry exceeds MAX_REGISTRY_SIZE,
 * the oldest entries are revoked and removed to prevent memory leaks.
 *
 * @param key - Unique identifier for this URL (e.g., API endpoint)
 * @param url - The blob URL to register
 */
export function registerFetchedBlobUrl(key: string, url: string): void {
	// Revoke any existing URL for this key to prevent leaks
	const existingUrl = fetchedUrlRegistry.get(key);
	if (existingUrl) {
		URL.revokeObjectURL(existingUrl);
		// Delete and re-add to move to end (most recently used)
		fetchedUrlRegistry.delete(key);
	}

	// LRU eviction: if registry is at capacity, evict oldest entries
	if (fetchedUrlRegistry.size >= MAX_REGISTRY_SIZE) {
		let evicted = 0;
		for (const [oldKey, oldUrl] of fetchedUrlRegistry) {
			if (evicted >= EVICTION_BATCH_SIZE) break;
			URL.revokeObjectURL(oldUrl);
			fetchedUrlRegistry.delete(oldKey);
			evicted++;
		}
	}

	fetchedUrlRegistry.set(key, url);
}

/**
 * Revoke a fetched blob URL by its key.
 *
 * @param key - The key used when registering the URL
 */
export function revokeFetchedBlobUrl(key: string): void {
	const url = fetchedUrlRegistry.get(key);
	if (url) {
		URL.revokeObjectURL(url);
		fetchedUrlRegistry.delete(key);
	}
}

/**
 * Revoke a blob URL directly (without needing the key).
 * Searches the registry for the URL and removes it.
 *
 * @param url - The blob URL to revoke
 */
export function revokeBlobUrl(url: string): void {
	URL.revokeObjectURL(url);
	// Also remove from registry if tracked
	for (const [key, registeredUrl] of fetchedUrlRegistry) {
		if (registeredUrl === url) {
			fetchedUrlRegistry.delete(key);
			break;
		}
	}
}

/**
 * Create a manager for tracking fetched blob URLs with component-scoped cleanup.
 * Similar to createObjectUrlManager but for URLs fetched via API calls.
 *
 * Usage in Svelte 5:
 * ```
 * const blobManager = createFetchedBlobUrlManager();
 *
 * onDestroy(() => blobManager.cleanup());
 *
 * // Register URLs as they're fetched
 * const url = await fetchThumbnail(itemId);
 * blobManager.track(itemId, url);
 * ```
 */
export function createFetchedBlobUrlManager() {
	const trackedUrls = new Map<string, string>();

	return {
		/**
		 * Track a fetched blob URL. If a URL already exists for this key,
		 * the old one is revoked first.
		 */
		track(key: string, url: string): void {
			const existingUrl = trackedUrls.get(key);
			if (existingUrl) {
				URL.revokeObjectURL(existingUrl);
			}
			trackedUrls.set(key, url);
		},

		/**
		 * Get a tracked URL by key.
		 */
		get(key: string): string | undefined {
			return trackedUrls.get(key);
		},

		/**
		 * Revoke and remove a specific URL by key.
		 */
		revoke(key: string): void {
			const url = trackedUrls.get(key);
			if (url) {
				URL.revokeObjectURL(url);
				trackedUrls.delete(key);
			}
		},

		/**
		 * Revoke all tracked URLs. Call this in cleanup/destroy.
		 */
		cleanup(): void {
			for (const url of trackedUrls.values()) {
				URL.revokeObjectURL(url);
			}
			trackedUrls.clear();
		},

		/**
		 * Get the number of tracked URLs (useful for debugging).
		 */
		get size(): number {
			return trackedUrls.size;
		},
	};
}
