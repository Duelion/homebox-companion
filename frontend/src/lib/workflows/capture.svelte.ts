/**
 * CaptureService - Manages image capture state and operations
 *
 * Responsibilities:
 * - Image collection management (add, remove, update, clear)
 * - Additional images per capture (multi-angle shots)
 * - Image options (separateItems, extraInstructions)
 */

import type { CapturedImage } from '$lib/types';

// =============================================================================
// CAPTURE SERVICE CLASS
// =============================================================================

export class CaptureService {
	/** Captured images ready for analysis */
	images = $state<CapturedImage[]>([]);

	// =========================================================================
	// IMAGE OPERATIONS
	// =========================================================================

	/** Add a captured image */
	addImage(image: CapturedImage): void {
		this.images = [...this.images, image];
	}

	/** Remove an image by index */
	removeImage(index: number): void {
		this.images = this.images.filter((_, i) => i !== index);
	}

	/** Update image options (separateItems, extraInstructions) */
	updateImageOptions(
		index: number,
		options: Partial<Pick<CapturedImage, 'separateItems' | 'extraInstructions'>>
	): void {
		this.images = this.images.map((img, i) => (i === index ? { ...img, ...options } : img));
	}

	/** Add additional images to a captured image (multi-angle shots) */
	addAdditionalImages(imageIndex: number, files: File[], dataUrls: string[]): void {
		this.images = this.images.map((img, i) => {
			if (i !== imageIndex) return img;
			return {
				...img,
				additionalFiles: [...(img.additionalFiles || []), ...files],
				additionalDataUrls: [...(img.additionalDataUrls || []), ...dataUrls]
			};
		});
	}

	/** Remove an additional image from a captured image */
	removeAdditionalImage(imageIndex: number, additionalIndex: number): void {
		this.images = this.images.map((img, i) => {
			if (i !== imageIndex) return img;
			return {
				...img,
				additionalFiles: img.additionalFiles?.filter((_, j) => j !== additionalIndex),
				additionalDataUrls: img.additionalDataUrls?.filter((_, j) => j !== additionalIndex)
			};
		});
	}

	/** Clear all captured images */
	clear(): void {
		this.images = [];
	}

	// =========================================================================
	// GETTERS
	// =========================================================================

	/** Check if there are any captured images */
	get hasImages(): boolean {
		return this.images.length > 0;
	}

	/** Get the count of captured images */
	get count(): number {
		return this.images.length;
	}

	/** Get an image by index */
	getImage(index: number): CapturedImage | null {
		return this.images[index] ?? null;
	}
}
