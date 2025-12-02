/**
 * Items store for detection and review flow
 */
import { writable, derived } from 'svelte/store';
import type { DetectedItem, LabelData } from '$lib/api';

// Captured images
export interface CapturedImage {
	file: File;
	dataUrl: string;
	separateItems: boolean;
	extraInstructions: string;
	additionalFiles?: File[];
	additionalDataUrls?: string[];
}

export const capturedImages = writable<CapturedImage[]>([]);

// Available labels
export const labels = writable<LabelData[]>([]);

// Detected items from AI
export interface ReviewItem extends DetectedItem {
	sourceImageIndex: number;
	additionalImages?: File[];
	originalFile?: File;
	customThumbnail?: string; // Custom cropped thumbnail data URL
}

export const detectedItems = writable<ReviewItem[]>([]);

// Current item index for review
export const currentItemIndex = writable<number>(0);

// Current item being reviewed
export const currentItem = derived(
	[detectedItems, currentItemIndex],
	([$items, $index]) => $items[$index] ?? null
);

// Confirmed items (ready to submit)
export interface ConfirmedItem extends ReviewItem {
	confirmed: true;
}

export const confirmedItems = writable<ConfirmedItem[]>([]);

// Merge state
export const isMergeReview = writable<boolean>(false);
export const mergedItemImages = writable<File[]>([]);

// Selection state for summary (for merging)
export const selectedForMerge = writable<Set<number>>(new Set());

// Reset all item state
export function resetItemState() {
	capturedImages.set([]);
	detectedItems.set([]);
	currentItemIndex.set(0);
	confirmedItems.set([]);
	isMergeReview.set(false);
	mergedItemImages.set([]);
	selectedForMerge.set(new Set());
}

// Clear captured images only
export function clearCapturedImages() {
	capturedImages.set([]);
}

// Add image to captured
export function addCapturedImage(image: CapturedImage) {
	capturedImages.update((images) => [...images, image]);
}

// Remove image from captured
export function removeCapturedImage(index: number) {
	capturedImages.update((images) => images.filter((_, i) => i !== index));
}

// Confirm current item
export function confirmCurrentItem(item: ReviewItem) {
	const confirmed: ConfirmedItem = { ...item, confirmed: true };
	confirmedItems.update((items) => [...items, confirmed]);
}

// Remove confirmed item
export function removeConfirmedItem(index: number) {
	confirmedItems.update((items) => items.filter((_, i) => i !== index));
}

// Edit a confirmed item (move it back to detectedItems for re-review)
export function editConfirmedItem(index: number): ReviewItem | null {
	let result: ReviewItem | null = null;
	
	confirmedItems.update((items) => {
		if (index >= 0 && index < items.length) {
			const item = items[index];
		// Convert back to ReviewItem
		const reviewItem: ReviewItem = {
			name: item.name,
			quantity: item.quantity,
			description: item.description,
			label_ids: item.label_ids,
			manufacturer: item.manufacturer,
			model_number: item.model_number,
			serial_number: item.serial_number,
			purchase_price: item.purchase_price,
			purchase_from: item.purchase_from,
			notes: item.notes,
			sourceImageIndex: item.sourceImageIndex,
			additionalImages: item.additionalImages,
			originalFile: item.originalFile,
			customThumbnail: item.customThumbnail,
		};
			// Set as the only item to review
			detectedItems.set([reviewItem]);
			currentItemIndex.set(0);
			result = reviewItem;
			return items.filter((_, i) => i !== index);
		}
		return items;
	});
	
	return result;
}

// Toggle item selection for merge
export function toggleMergeSelection(index: number) {
	selectedForMerge.update((set) => {
		const newSet = new Set(set);
		if (newSet.has(index)) {
			newSet.delete(index);
		} else {
			newSet.add(index);
		}
		return newSet;
	});
}

// Clear merge selection
export function clearMergeSelection() {
	selectedForMerge.set(new Set());
}

