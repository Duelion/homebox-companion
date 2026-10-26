/**
 * ReviewService - Manages item review and confirmation
 *
 * Responsibilities:
 * - Detected items list management
 * - Navigation between items (prev/next)
 * - Item confirmation and confirmation list management
 * - Editing confirmed items
 */
import { createUuidV4 } from '$lib/utils/uuid';

import type { ReviewItem, ConfirmedItem } from '$lib/types';
import { copyReviewItem } from '$lib/services/reviewEditor.svelte';

// =============================================================================
// REVIEW SERVICE CLASS
// =============================================================================

export class ReviewService {
	// =========================================================================
	// STATE (private with getters for controlled access)
	// =========================================================================

	/** Items detected by AI, awaiting review */
	private _detectedItems = $state<ReviewItem[]>([]);

	/** Current index in the detected items list */
	private _currentReviewIndex = $state(0);

	/** Items confirmed by user, ready for submission */
	private _confirmedItems = $state<ConfirmedItem[]>([]);
	private _activeDraft = $state<ReviewItem | null>(null);

	get activeDraft(): ReviewItem | null {
		return this._activeDraft?.reviewId === this.currentItem?.reviewId ? this._activeDraft : null;
	}

	beginDraft(): void {
		if (this.currentItem && !this.activeDraft) this._activeDraft = copyReviewItem(this.currentItem);
	}

	updateDraft(updates: Partial<ReviewItem>, identity: string | undefined): boolean {
		if (!identity || this.activeDraft?.reviewId !== identity) return false;
		this._activeDraft = copyReviewItem({ ...this.activeDraft, ...updates, reviewId: identity });
		return true;
	}

	restoreDraft(draft: ReviewItem | undefined): void {
		this._activeDraft =
			draft?.reviewId && draft.reviewId === this.currentItem?.reviewId ? draft : null;
	}

	discardDraft(): void {
		this._activeDraft = null;
	}

	// =========================================================================
	// GETTERS (read-only access to state)
	// =========================================================================

	/** Get detected items */
	get detectedItems(): ReviewItem[] {
		return this._detectedItems;
	}

	/** Get current review index */
	get currentReviewIndex(): number {
		return this._currentReviewIndex;
	}

	/** Get confirmed items */
	get confirmedItems(): ConfirmedItem[] {
		return this._confirmedItems;
	}

	// =========================================================================
	// DETECTED ITEMS MANAGEMENT
	// =========================================================================

	/** Set detected items from analysis results */
	setDetectedItems(items: ReviewItem[]): void {
		this._activeDraft = null;
		this._detectedItems = items.map((item) => ({
			...item,
			reviewId: item.reviewId ?? createUuidV4(),
		}));
		this._currentReviewIndex = 0;
	}

	/** Set confirmed items directly (used for session recovery) */
	setConfirmedItems(items: ConfirmedItem[]): void {
		this._confirmedItems = items.map((item) => ({
			...item,
			reviewId: item.reviewId ?? createUuidV4(),
		}));
	}

	/** Set current review index (used for session recovery) */
	setCurrentReviewIndex(index: number): void {
		this._currentReviewIndex = Math.max(0, Math.min(index, this._detectedItems.length - 1));
	}

	/**
	 * Update sourceImageIndex for all detected items after images are removed.
	 * Each removed index causes all higher indices to shift down by 1.
	 * @param removedIndices - Array of image indices that were removed (must be sorted ascending)
	 */
	updateSourceImageIndices(removedIndices: number[]): void {
		if (removedIndices.length === 0) return;

		this._detectedItems = this._detectedItems.map((item) => {
			let newIndex = item.sourceImageIndex;
			// For each removed index that was below or equal to this item's source,
			// decrement the index (but only if the source wasn't the removed index itself)
			for (const removed of removedIndices) {
				if (removed < item.sourceImageIndex) {
					newIndex--;
				}
			}
			return newIndex !== item.sourceImageIndex ? { ...item, sourceImageIndex: newIndex } : item;
		});
	}

	/** Clear detected items */
	clearDetectedItems(): void {
		this.discardDraft();
		this._detectedItems = [];
		this._currentReviewIndex = 0;
	}

	/** Update the current item being reviewed */
	updateCurrentItem(updates: Partial<ReviewItem>): void {
		const index = this._currentReviewIndex;
		if (index < 0 || index >= this._detectedItems.length) return;

		this._detectedItems = this._detectedItems.map((item, i) =>
			i === index ? { ...item, ...updates } : item
		);
	}

	// =========================================================================
	// NAVIGATION
	// =========================================================================

	/** Navigate to previous item */
	previousItem(): void {
		this.discardDraft();
		if (this._currentReviewIndex > 0) {
			this._currentReviewIndex--;
		}
	}

	/** Navigate to next item */
	nextItem(): void {
		this.discardDraft();
		if (this._currentReviewIndex < this._detectedItems.length - 1) {
			this._currentReviewIndex++;
		}
	}

	/** Check if there's a previous item */
	get hasPrevious(): boolean {
		return this._currentReviewIndex > 0;
	}

	/** Check if there's a next item */
	get hasNext(): boolean {
		return this._currentReviewIndex < this._detectedItems.length - 1;
	}

	/** Check if this is the last item */
	get isLastItem(): boolean {
		return this._currentReviewIndex === this._detectedItems.length - 1;
	}

	// =========================================================================
	// CONFIRMATION
	// =========================================================================

	/**
	 * Confirm the current item and optionally advance to next
	 * @returns true if there are more items to review, false if review is complete
	 */
	confirmCurrentItem(item: ReviewItem): boolean {
		if (
			!item.reviewId ||
			item.reviewId !== this.currentItem?.reviewId ||
			this._confirmedItems.some((existing) => existing.reviewId === item.reviewId)
		)
			return this.hasNext;
		this.discardDraft();
		const confirmed: ConfirmedItem = { ...item, confirmed: true };
		this._confirmedItems = [...this._confirmedItems, confirmed];

		if (this.hasNext) {
			this.nextItem();
			return true;
		}
		return false;
	}

	/**
	 * Confirm all remaining items from the current index onwards
	 * @param currentItemOverride - Optional edited version of the current item to use instead of the detected item
	 * @returns The number of items confirmed
	 */
	confirmAllRemainingItems(currentItemOverride?: ReviewItem): number {
		if (currentItemOverride && currentItemOverride.reviewId !== this.currentItem?.reviewId)
			return 0;
		this.discardDraft();
		const newItems: ConfirmedItem[] = [];
		for (let i = this._currentReviewIndex; i < this._detectedItems.length; i++) {
			// Use the override for the current item (index matches currentReviewIndex),
			// otherwise use the detected item as-is
			const item =
				i === this._currentReviewIndex && currentItemOverride
					? currentItemOverride
					: this._detectedItems[i];
			if (this._confirmedItems.some((existing) => existing.reviewId === item.reviewId)) continue;
			const confirmed: ConfirmedItem = { ...item, confirmed: true };
			newItems.push(confirmed);
		}
		// Batch append all items at once to avoid O(n²) array spreading
		this._confirmedItems = [...this._confirmedItems, ...newItems];
		return newItems.length;
	}

	/**
	 * Skip current item and advance to next
	 * @returns 'next' if moved to next item, 'complete' if no more items, 'empty' if nothing confirmed
	 */
	skipCurrentItem(): 'next' | 'complete' | 'empty' {
		this.discardDraft();
		if (this.hasNext) {
			this.nextItem();
			return 'next';
		}

		// Last item - check if anything was confirmed
		if (this._confirmedItems.length === 0) {
			return 'empty';
		}
		return 'complete';
	}

	// =========================================================================
	// CONFIRMED ITEMS MANAGEMENT
	// =========================================================================

	/** Remove a confirmed item by index */
	removeConfirmedItem(index: number): void {
		this._confirmedItems = this._confirmedItems.filter((_, i) => i !== index);
	}

	/**
	 * Edit a confirmed item by moving it back to review mode.
	 *
	 * This method is called from the confirmation screen, after the user has already
	 * completed reviewing all detected items (confirming or skipping each one).
	 * It removes the item from the confirmed list and creates a single-item review
	 * session for focused re-editing.
	 *
	 * Note: This replaces the detectedItems array with only the item being edited.
	 * This is intentional—at the confirmation stage, all original detected items have
	 * already been processed, so no unreviewed items are lost.
	 *
	 * @returns The item converted to a ReviewItem for editing, or null if index is invalid
	 */
	editConfirmedItem(index: number): ReviewItem | null {
		this.discardDraft();
		const item = this._confirmedItems[index];
		if (!item) return null;

		// Remove from confirmed
		this._confirmedItems = this._confirmedItems.filter((_, i) => i !== index);

		// Preserve every review field, including asset IDs and custom fields.
		const reviewItem: ReviewItem = { ...item };

		// Add to detected items for re-review
		this._detectedItems = [reviewItem];
		this._currentReviewIndex = 0;

		return reviewItem;
	}

	/**
	 * Open a confirmed item in the focused editor without removing it from the
	 * confirmed list. This is used after submission so status indexes continue
	 * to refer to the same items while the user edits a failed row.
	 */
	stageConfirmedItemForEdit(index: number): ReviewItem | null {
		this.discardDraft();
		const item = this._confirmedItems[index];
		if (!item) return null;

		const reviewItem: ReviewItem = { ...item };
		this._detectedItems = [{ ...reviewItem }];
		this._currentReviewIndex = 0;
		return this._detectedItems[0];
	}

	/** Replace a confirmed item in place, preserving submission status indexes. */
	replaceConfirmedItem(index: number, item: ReviewItem): boolean {
		if (!this._confirmedItems[index]) return false;

		this._confirmedItems = this._confirmedItems.map((existing, itemIndex) =>
			itemIndex === index ? { ...item, confirmed: true } : existing
		);
		return true;
	}

	/** Clear all confirmed items */
	clearConfirmedItems(): void {
		this._confirmedItems = [];
	}

	// =========================================================================
	// RESET
	// =========================================================================

	/** Reset all review state */
	reset(): void {
		this.discardDraft();
		this._detectedItems = [];
		this._currentReviewIndex = 0;
		this._confirmedItems = [];
	}

	// =========================================================================
	// GETTERS
	// =========================================================================

	/** Get current item being reviewed */
	get currentItem(): ReviewItem | null {
		return this._detectedItems[this._currentReviewIndex] ?? null;
	}

	/** Check if review has confirmed items */
	get hasConfirmedItems(): boolean {
		return this._confirmedItems.length > 0;
	}

	/** Get count of confirmed items */
	get confirmedCount(): number {
		return this._confirmedItems.length;
	}

	/** Get count of detected items */
	get detectedCount(): number {
		return this._detectedItems.length;
	}
}
