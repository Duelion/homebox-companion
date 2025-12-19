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

	/** Selected parent item ID (for sub-item relationships) */
	private _parentItemId = $state<string | null>(null);

	/** Selected parent item name */
	private _parentItemName = $state<string | null>(null);

	/** Current error message */
	private _error = $state<string | null>(null);

	// =========================================================================
	// UNIFIED STATE ACCESSOR (for backward compatibility)
	// =========================================================================

	/**
	 * State proxy that allows both reading and direct property assignment.
	 * This maintains backward compatibility with code like:
	 *   workflow.state.status = 'confirming'
	 *   workflow.state.analysisProgress = null
	 */
	private _stateProxy: ScanState | null = null;

	/** Valid readable state properties */
	private static readonly READABLE_PROPS = new Set<keyof ScanState>([
		'status',
		'locationId',
		'locationName',
		'locationPath',
		'parentItemId',
		'parentItemName',
		'images',
		'analysisProgress',
		'detectedItems',
		'currentReviewIndex',
		'confirmedItems',
		'submissionProgress',
		'itemStatuses',
		'lastSubmissionResult',
		'submissionErrors',
		'error'
	]);

	/** Writable state properties */
	private static readonly WRITABLE_PROPS = new Set<keyof ScanState>([
		'status',
		'locationId',
		'locationName',
		'locationPath',
		'parentItemId',
		'parentItemName',
		'error',
		'analysisProgress'
	]);

	/**
	 * Unified state object for backward compatibility with existing pages.
	 * Returns a Proxy that intercepts property assignments.
	 * 
	 * IMPORTANT: This proxy throws errors for unknown property access to surface bugs.
	 * - Reading unknown properties throws TypeError
	 * - Writing to read-only properties throws TypeError
	 * - Writing to unknown properties throws TypeError
	 */
	get state(): ScanState {
		// Create proxy once and reuse (the proxy handlers access live service state)
		if (!this._stateProxy) {
			const workflow = this;
			this._stateProxy = new Proxy({} as ScanState, {
				get(_target, prop: string | symbol) {
					// Allow Symbol access (for iteration, etc.)
					if (typeof prop === 'symbol') {
						return undefined;
					}

					const propName = prop as keyof ScanState;

					// Check if property is valid
					if (!ScanWorkflow.READABLE_PROPS.has(propName)) {
						throw new TypeError(
							`Cannot read unknown workflow state property: '${prop}'. ` +
							`Valid properties are: ${[...ScanWorkflow.READABLE_PROPS].join(', ')}`
						);
					}

					switch (propName) {
						case 'status':
							return workflow._status;
						case 'locationId':
							return workflow._locationId;
						case 'locationName':
							return workflow._locationName;
						case 'locationPath':
							return workflow._locationPath;
						case 'parentItemId':
							return workflow._parentItemId;
						case 'parentItemName':
							return workflow._parentItemName;
						case 'images':
							return workflow.captureService.images;
						case 'analysisProgress':
							return workflow.analysisService.progress;
						case 'detectedItems':
							return workflow.reviewService.detectedItems;
						case 'currentReviewIndex':
							return workflow.reviewService.currentReviewIndex;
						case 'confirmedItems':
							return workflow.reviewService.confirmedItems;
						case 'submissionProgress':
							return workflow.submissionService.progress;
						case 'itemStatuses':
							return workflow.submissionService.itemStatuses;
						case 'lastSubmissionResult':
							return workflow.submissionService.lastResult;
						case 'submissionErrors':
							return workflow.submissionService.lastErrors;
						case 'error':
							return workflow._error;
						default:
							// TypeScript exhaustiveness check - should never reach here
							const _exhaustive: never = propName;
							throw new TypeError(`Unhandled property: ${_exhaustive}`);
					}
				},
				set(_target, prop: string | symbol, value) {
					// Reject Symbol writes
					if (typeof prop === 'symbol') {
						throw new TypeError(`Cannot set Symbol property on workflow state`);
					}

					const propName = prop as keyof ScanState;

					// Check if property exists at all
					if (!ScanWorkflow.READABLE_PROPS.has(propName)) {
						throw new TypeError(
							`Cannot set unknown workflow state property: '${prop}'. ` +
							`Valid properties are: ${[...ScanWorkflow.READABLE_PROPS].join(', ')}`
						);
					}

					// Check if property is writable
					if (!ScanWorkflow.WRITABLE_PROPS.has(propName)) {
						throw new TypeError(
							`Cannot set read-only workflow state property: '${prop}'. ` +
							`This property can only be modified through workflow methods. ` +
							`Writable properties are: ${[...ScanWorkflow.WRITABLE_PROPS].join(', ')}`
						);
					}

					switch (propName) {
						case 'status':
							workflow._status = value as ScanStatus;
							return true;
						case 'locationId':
							workflow._locationId = value as string | null;
							return true;
						case 'locationName':
							workflow._locationName = value as string | null;
							return true;
						case 'locationPath':
							workflow._locationPath = value as string | null;
							return true;
						case 'parentItemId':
							workflow._parentItemId = value as string | null;
							return true;
						case 'parentItemName':
							workflow._parentItemName = value as string | null;
							return true;
						case 'error':
							workflow._error = value as string | null;
							return true;
						case 'analysisProgress':
							workflow.analysisService.progress = value as Progress | null;
							return true;
						default:
							// TypeScript exhaustiveness check - should never reach here
							// since we validated against WRITABLE_PROPS above
							throw new TypeError(`Unhandled writable property: ${prop}`);
					}
				},
				has(_target, prop: string | symbol) {
					if (typeof prop === 'symbol') {
						return false;
					}
					return ScanWorkflow.READABLE_PROPS.has(prop as keyof ScanState);
				},
				ownKeys() {
					return [...ScanWorkflow.READABLE_PROPS];
				},
				getOwnPropertyDescriptor(_target, prop: string | symbol) {
					if (typeof prop === 'symbol' || !ScanWorkflow.READABLE_PROPS.has(prop as keyof ScanState)) {
						return undefined;
					}
					return {
						enumerable: true,
						configurable: true,
						writable: ScanWorkflow.WRITABLE_PROPS.has(prop as keyof ScanState)
					};
				}
			});
		}
		return this._stateProxy;
	}

	// =========================================================================
	// LOCATION ACTIONS
	// =========================================================================

	/** Set the selected location (clears parent item since items are location-specific) */
	setLocation(id: string, name: string, path: string): void {
		// If changing to a different location, clear parent item
		if (this._locationId !== id) {
			this._parentItemId = null;
			this._parentItemName = null;
		}
		this._locationId = id;
		this._locationName = name;
		this._locationPath = path;
		this._status = 'capturing';
		this._error = null;
	}

	/** Clear location selection (also clears parent item since it's location-specific) */
	clearLocation(): void {
		this._locationId = null;
		this._locationName = null;
		this._locationPath = null;
		this._parentItemId = null;
		this._parentItemName = null;
		this._status = 'location';
	}

	/** Set the parent item (for sub-item relationships) */
	setParentItem(id: string, name: string): void {
		this._parentItemId = id;
		this._parentItemName = name;
	}

	/** Clear parent item selection */
	clearParentItem(): void {
		this._parentItemId = null;
		this._parentItemName = null;
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
		log.info('ScanWorkflow.startAnalysis() called');

		// Prevent starting a new analysis if one is already in progress
		if (this._status === 'analyzing') {
			log.warn('Analysis already in progress (status check), ignoring duplicate request');
			this._error = 'Analysis already in progress';
			return;
		}

		if (!this.captureService.hasImages) {
			log.warn('No images to analyze, returning early');
			this._error = 'Please add at least one image';
			return;
		}

		log.info(`Starting analysis for ${this.captureService.count} image(s)`);

		// Set status BEFORE any async operations to prevent duplicate triggers
		this._status = 'analyzing';
		this._error = null;
		log.debug('Status set to "analyzing", delegating to AnalysisService');

		const result = await this.analysisService.analyze(this.captureService.images);

		// Check if cancelled (status may have changed)
		if (this._status !== 'analyzing') {
			log.debug('Analysis was cancelled or status changed during processing');
			return;
		}

		if (result.success) {
			this.reviewService.setDetectedItems(result.items);
			this._status = 'reviewing';
			log.info(`Analysis complete! Detected ${result.items.length} item(s), transitioning to review`);
		} else {
			this._error = result.error || 'Analysis failed';
			this._status = 'capturing';
			log.error(`Analysis failed: ${this._error}, returning to capture mode`);
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

		const result = await this.submissionService.submitAll(items, this._locationId, this._parentItemId, options);

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

		const result = await this.submissionService.retryFailed(items, this._locationId, this._parentItemId);

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
		this._parentItemId = null;
		this._parentItemName = null;
		this._error = null;
	}

	/** Start a new scan (keeps location and parent item if set) */
	startNew(): void {
		const locationId = this._locationId;
		const locationName = this._locationName;
		const locationPath = this._locationPath;
		const parentItemId = this._parentItemId;
		const parentItemName = this._parentItemName;

		this.reset();

		if (locationId && locationName && locationPath) {
			this._locationId = locationId;
			this._locationName = locationName;
			this._locationPath = locationPath;
			this._parentItemId = parentItemId;
			this._parentItemName = parentItemName;
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
