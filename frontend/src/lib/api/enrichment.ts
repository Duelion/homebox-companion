/**
 * Enrichment API endpoints
 *
 * Provides AI-powered product specification lookup using the configured AI provider.
 * Uses the AI's training knowledge to find product details - no external APIs required.
 */

import { request } from './client';

// =============================================================================
// TYPES
// =============================================================================

export interface EnrichmentRequest {
	manufacturer: string;
	model_number: string;
	product_name?: string;
}

export interface EnrichmentResponse {
	/** Whether enrichment found useful data */
	enriched: boolean;
	/** Source of data: 'ai_knowledge', 'cache', or 'none' */
	source: string;
	/** Full product name */
	name: string;
	/** Product description */
	description: string;
	/** Product features list */
	features: string[];
	/** Original MSRP if known */
	msrp: number | null;
	/** Release year if known */
	release_year: number | null;
	/** Product category */
	category: string;
	/** Confidence score 0-1 */
	confidence: number;
	/** Pre-formatted description for Homebox (combines description + features) */
	formatted_description: string;
}

export interface ClearCacheResponse {
	cleared_count: number;
	message: string;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Enrich a product with detailed specifications.
 *
 * Uses the configured AI provider to look up product details from its training data.
 * Results are cached locally to avoid repeated API calls.
 *
 * @param data - Product identification (manufacturer, model number, optional name)
 * @returns Enriched product data or empty result if not found
 */
export const enrichProduct = (data: EnrichmentRequest) =>
	request<EnrichmentResponse>('/enrichment/lookup', {
		method: 'POST',
		body: JSON.stringify(data),
	});

/**
 * Clear the enrichment cache.
 *
 * @returns Count of cleared entries
 */
export const clearEnrichmentCache = () =>
	request<ClearCacheResponse>('/enrichment/cache', {
		method: 'DELETE',
	});
