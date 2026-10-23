import type { ReviewItem } from '$lib/types';

/** Synchronize review photos while retaining compression only for an unchanged ordered list. */
export function prepareReviewItem(
	item: ReviewItem,
	images: readonly File[],
	originalImages: readonly File[]
): ReviewItem {
	const imagesChanged =
		images.length !== originalImages.length ||
		images.some((image, index) => image !== originalImages[index]);

	return {
		...item,
		originalFile: images[0],
		additionalImages: images.slice(1),
		customThumbnail: images.length > 0 ? item.customThumbnail : undefined,
		compressedDataUrl: imagesChanged ? undefined : item.compressedDataUrl,
		compressedAdditionalDataUrls: imagesChanged ? undefined : item.compressedAdditionalDataUrls,
	};
}
