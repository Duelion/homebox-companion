/**
 * ScanWorkflow - Coordinates the entire scan-to-submit workflow
 *
 * This class acts as a facade/coordinator that:
 * - Manages overall workflow status and transitions
 * - Manages location state
 * - Delegates to specialized services for each phase
 * - Maintains backward compatibility for existing page components
 *
 * Services:
 * - CaptureService: Image management
 * - AnalysisService: AI detection
 * - ReviewService: Item review and confirmation
 * - SubmissionService: Homebox submission
 */

import { workflowLogger as log } from '$lib/utils/logger';
import { CaptureService } from './capture.svelte';
import { AnalysisService } from './analysis.svelte';
import { ReviewService } from './review.svelte';
import { SubmissionService } from './submission.svelte';
import type {
	ScanState,
	ScanStatus,
	CapturedImage,
	ReviewItem,
	ConfirmedItem,
	Progress,
	ItemSubmissionStatus,
	SubmissionResult
} from '$lib/types';

// =============================================================================
// SCAN WORKFLOW CLASS
// =============================================================================

class ScanWorkflow {
	// =========================================================================
	// SERVICES
	// =========================================================================

	private captureService = new CaptureService();
	private analysisService = new AnalysisService();
	private reviewService = new ReviewService();
	private submissionService = new SubmissionService();

	// =========================================================================
	// WORKFLOW STATE
	// =========================================================================

	/** Current workflow status */
	private _status = $state<ScanStatus>('idle');

	/** Selected location ID */
	private _locationId = $state<string | null>(null);

	/** Selected location name */
	private _locationName = $state<string | null>(null);

	/** Selected location path */
	private _locationPath = $state<string | null>(null);

	/** Current error message */
	private _error = $state<string | null>(null);

	// =========================================================================
	// UNIFIED STATE ACCESSOR (for backward compatibility)
	// =========================================================================

	/**
	 * Unified state object for backward compatibility with existing pages.
	 * Provides a single reactive object that mirrors the old ScanState interface.
	 */
	get state(): ScanState {
		return {
			status: this._status,
			locationId: this._locationId,
			locationName: this._locationName,
			locationPath: this._locationPath,
			images: this.captureService.images,
			analysisProgress: this.analysisService.progress,
			detectedItems: this.reviewService.detectedItems,
			currentReviewIndex: this.reviewService.currentReviewIndex,
			confirmedItems: this.reviewService.confirmedItems,
			submissionProgress: this.submissionService.progress,
			itemStatuses: this.submissionService.itemStatuses,
			lastSubmissionResult: this.submissionService.lastResult,
			error: this._error
		};
	}

	/**
	 * Setter for state (supports direct property assignment for backward compatibility)
	 * Note: This is a compatibility shim - prefer using specific methods
	 */
	set state(newState: Partial<ScanState>) {
		if (newState.status !== undefined) this._status = newState.status;
		if (newState.locationId !== undefined) this._locationId = newState.locationId;
		if (newState.locationName !== undefined) this._locationName = newState.locationName;
		if (newState.locationPath !== undefined) this._locationPath = newState.locationPath;
		if (newState.error !== undefined) this._error = newState.error;
		if (newState.analysisProgress !== undefined) {
			this.analysisService.progress = newState.analysisProgress;
		}
	}

	// =========================================================================
	// LOCATION ACTIONS
	// =========================================================================

	/** Set the selected location */
	setLocation(id: string, name: string, path: string): void {
		this._locationId = id;
		this._locationName = name;
		this._locationPath = path;
		this._status = 'capturing';
		this._error = null;
	}

	/** Clear location selection */
	clearLocation(): void {
		this._locationId = null;
		this._locationName = null;
		this._locationPath = null;
		this._status = 'location';
	}

	// =========================================================================
	// IMAGE CAPTURE ACTIONS (delegated to CaptureService)
	// =========================================================================

	/** Add a captured image */
	addImage(image: CapturedImage): void {
		this.captureService.addImage(image);
	}

	/** Remove an image by index */
	removeImage(index: number): void {
		this.captureService.removeImage(index);
	}

	/** Update image options (separateItems, extraInstructions) */
	updateImageOptions(
		index: number,
		options: Partial<Pick<CapturedImage, 'separateItems' | 'extraInstructions'>>
	): void {
		this.captureService.updateImageOptions(index, options);
	}

	/** Add additional images to a captured image */
	addAdditionalImages(imageIndex: number, files: File[], dataUrls: string[]): void {
		this.captureService.addAdditionalImages(imageIndex, files, dataUrls);
	}

	/** Remove an additional image */
	removeAdditionalImage(imageIndex: number, additionalIndex: number): void {
		this.captureService.removeAdditionalImage(imageIndex, additionalIndex);
	}

	/** Clear all captured images */
	clearImages(): void {
		this.captureService.clear();
	}

	// =========================================================================
	// ANALYSIS (delegated to AnalysisService)
	// =========================================================================

	/** Start image analysis - coordinates with AnalysisService */
	async startAnalysis(): Promise<void> {
		// Prevent starting a new analysis if one is already in progress
		if (this._status === 'analyzing') {
			log.warn('Analysis already in progress, ignoring duplicate request');
			this._error = 'Analysis already in progress';
			return;
		}

		if (!this.captureService.hasImages) {
			this._error = 'Please add at least one image';
			return;
		}

		log.debug(`Starting analysis for ${this.captureService.count} image(s)`);

		// Set status BEFORE any async operations to prevent duplicate triggers
		this._status = 'analyzing';
		this._error = null;

		const result = await this.analysisService.analyze(this.captureService.images);

		// Check if cancelled (status may have changed)
		if (this._status !== 'analyzing') {
			return;
		}

		if (result.success) {
			this.reviewService.setDetectedItems(result.items);
			this._status = 'reviewing';
			log.debug(`Analysis complete! Detected ${result.items.length} item(s)`);
		} else {
			this._error = result.error || 'Analysis failed';
			this._status = 'capturing';
		}
	}

	/** Cancel ongoing analysis */
	cancelAnalysis(): void {
		this.analysisService.cancel();
		if (this._status === 'analyzing') {
			this._status = 'capturing';
			this.analysisService.clearProgress();
		}
	}

	/** Check if analysis is in progress */
	get isAnalyzing(): boolean {
		return this._status === 'analyzing';
	}

	// =========================================================================
	// REVIEW ACTIONS (delegated to ReviewService)
	// =========================================================================

	/** Get current item being reviewed */
	get currentItem(): ReviewItem | null {
		return this.reviewService.currentItem;
	}

	/** Update the current item being reviewed */
	updateCurrentItem(updates: Partial<ReviewItem>): void {
		this.reviewService.updateCurrentItem(updates);
	}

	/** Navigate to previous item */
	previousItem(): void {
		this.reviewService.previousItem();
	}

	/** Navigate to next item */
	nextItem(): void {
		this.reviewService.nextItem();
	}

	/** Skip current item and move to next */
	skipItem(): void {
		const result = this.reviewService.skipCurrentItem();
		if (result === 'empty') {
			this.backToCapture();
		} else if (result === 'complete') {
			this.finishReview();
		}
	}

	/** Confirm current item and move to next */
	confirmItem(item: ReviewItem): void {
		const hasMore = this.reviewService.confirmCurrentItem(item);
		if (!hasMore) {
			this.finishReview();
		}
	}

	/** Finish review and move to confirmation */
	finishReview(): void {
		if (!this.reviewService.hasConfirmedItems) {
			this._error = 'Please confirm at least one item';
			return;
		}
		this._status = 'confirming';
	}

	/** Return to capture mode from review */
	backToCapture(): void {
		this._status = 'capturing';
		this.reviewService.reset();
		this._error = null;
	}

	// =========================================================================
	// CONFIRMATION ACTIONS (delegated to ReviewService)
	// =========================================================================

	/** Remove a confirmed item */
	removeConfirmedItem(index: number): void {
		this.reviewService.removeConfirmedItem(index);
		if (!this.reviewService.hasConfirmedItems) {
			this._status = 'capturing';
		}
	}

	/** Edit a confirmed item (move back to review) */
	editConfirmedItem(index: number): void {
		const item = this.reviewService.editConfirmedItem(index);
		if (item) {
			this._status = 'reviewing';
		}
	}

	/** Go back to add more images */
	addMoreImages(): void {
		this._status = 'capturing';
	}

	// =========================================================================
	// SUBMISSION (delegated to SubmissionService)
	// =========================================================================

	/**
	 * Submit all confirmed items to Homebox.
	 * @param options.validateAuth - If true, validate auth token before submitting (default: true)
	 * @returns Object with success, counts, and sessionExpired flag
	 */
	async submitAll(options?: { validateAuth?: boolean }): Promise<{
		success: boolean;
		successCount: number;
		partialSuccessCount: number;
		failCount: number;
		sessionExpired: boolean;
	}> {
		const items = this.reviewService.confirmedItems;

		if (items.length === 0) {
			this._error = 'No items to submit';
			return {
				success: false,
				successCount: 0,
				partialSuccessCount: 0,
				failCount: 0,
				sessionExpired: false
			};
		}

		this._status = 'submitting';
		this._error = null;

		const result = await this.submissionService.submitAll(items, this._locationId, options);

		if (result.sessionExpired) {
			return result;
		}

		// Handle results
		if (result.failCount > 0 && result.successCount === 0 && result.partialSuccessCount === 0) {
			this._error = 'All items failed to create';
			this._status = 'confirming';
		} else if (result.failCount > 0) {
			this._error = `Created ${result.successCount + result.partialSuccessCount} items, ${result.failCount} failed`;
			// Keep status as 'submitting' to show per-item status UI
		} else if (result.partialSuccessCount > 0) {
			this._error = `${result.partialSuccessCount} item(s) created with missing attachments`;
			this.submissionService.saveResult(items, this._locationName, this._locationId);
			this._status = 'complete';
		} else if (result.success) {
			this.submissionService.saveResult(items, this._locationName, this._locationId);
			this._status = 'complete';
		}

		return result;
	}

	/**
	 * Retry only failed items.
	 * @returns Object with success flag, counts, and sessionExpired flag
	 */
	async retryFailed(): Promise<{
		success: boolean;
		successCount: number;
		partialSuccessCount: number;
		failCount: number;
		sessionExpired: boolean;
	}> {
		const items = this.reviewService.confirmedItems;

		if (!this.submissionService.hasFailedItems()) {
			return {
				success: true,
				successCount: 0,
				partialSuccessCount: 0,
				failCount: 0,
				sessionExpired: false
			};
		}

		this._error = null;

		const result = await this.submissionService.retryFailed(items, this._locationId);

		if (result.sessionExpired) {
			return result;
		}

		// Check if all items are now successful
		if (this.submissionService.allItemsSuccessful()) {
			this.submissionService.saveResult(items, this._locationName, this._locationId);
			this._status = 'complete';
		} else if (result.failCount > 0) {
			this._error = `Retried: ${result.successCount + result.partialSuccessCount} succeeded, ${result.failCount} still failing`;
		}

		return result;
	}

	/** Check if there are any failed items */
	hasFailedItems(): boolean {
		return this.submissionService.hasFailedItems();
	}

	/** Check if all items were successfully submitted */
	allItemsSuccessful(): boolean {
		return this.submissionService.allItemsSuccessful();
	}

	// =========================================================================
	// RESET
	// =========================================================================

	/** Reset workflow to initial state */
	reset(): void {
		this.cancelAnalysis();
		this.captureService.clear();
		this.reviewService.reset();
		this.submissionService.reset();
		this._status = 'idle';
		this._locationId = null;
		this._locationName = null;
		this._locationPath = null;
		this._error = null;
	}

	/** Start a new scan (keeps location if set) */
	startNew(): void {
		const locationId = this._locationId;
		const locationName = this._locationName;
		const locationPath = this._locationPath;

		this.reset();

		if (locationId && locationName && locationPath) {
			this._locationId = locationId;
			this._locationName = locationName;
			this._locationPath = locationPath;
			this._status = 'capturing';
		} else {
			this._status = 'location';
		}
	}

	// =========================================================================
	// HELPERS
	// =========================================================================

	/** Clear error */
	clearError(): void {
		this._error = null;
	}

	/** Get source image for a review/confirmed item */
	getSourceImage(item: ReviewItem | ConfirmedItem): CapturedImage | null {
		return this.captureService.getImage(item.sourceImageIndex);
	}

	/** Get last submission result (preserved after workflow completion) */
	get submissionResult(): SubmissionResult | null {
		return this.submissionService.lastResult;
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const scanWorkflow = new ScanWorkflow();
