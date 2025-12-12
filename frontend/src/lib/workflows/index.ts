/**
 * Workflows Module - State management for multi-step user flows
 *
 * The scan workflow is decomposed into focused services:
 * - CaptureService: Image capture and manipulation
 * - AnalysisService: AI detection and analysis
 * - ReviewService: Item review and confirmation
 * - SubmissionService: Homebox item submission
 *
 * The main ScanWorkflow coordinates these services and provides
 * a unified API for page components.
 */

// Main workflow (coordinator)
export { scanWorkflow } from './scan.svelte';

// Individual services (for testing or advanced use cases)
export { CaptureService } from './capture.svelte';
export { AnalysisService, type AnalysisResult } from './analysis.svelte';
export { ReviewService } from './review.svelte';
export { SubmissionService, type SubmitResult } from './submission.svelte';
