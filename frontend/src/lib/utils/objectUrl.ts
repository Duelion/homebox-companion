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
		}
	};
}
