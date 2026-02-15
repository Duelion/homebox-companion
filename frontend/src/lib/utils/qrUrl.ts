/**
 * QR URL resolution utility.
 *
 * Resolves shortened URLs (bit.ly, etc.) by following redirects server-side,
 * then returns the final URL for local parsing of location/asset IDs.
 *
 * Direct Homebox URLs are returned as-is (no server call needed).
 */

import { request } from '$lib/api/client';
import { createLogger } from '$lib/utils/logger';

const log = createLogger({ prefix: 'QrUrl' });

/** Patterns that indicate a direct Homebox URL (no resolution needed) */
const HOMEBOX_PATTERNS = [/\/location\/[a-f0-9-]+/i, /\/a\/[^\s/]+/];

/**
 * Resolve a QR code URL, following redirects if needed.
 *
 * - If the text already matches a Homebox URL pattern, returns it as-is.
 * - If it looks like a URL, calls the server to follow redirects.
 * - Otherwise, returns the raw text unchanged.
 */
export async function resolveQrUrl(rawText: string): Promise<string> {
	const trimmed = rawText.trim();

	// Already a Homebox URL — no resolution needed
	if (HOMEBOX_PATTERNS.some((pattern) => pattern.test(trimmed))) {
		log.debug('URL already matches Homebox pattern, skipping resolution');
		return trimmed;
	}

	// Not a URL at all — return as-is
	if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
		log.debug('Not a URL, returning raw text');
		return trimmed;
	}

	// Likely a shortened URL — resolve via server
	log.info(`Resolving shortened URL: ${trimmed}`);
	try {
		const result = await request<{ resolved_url: string }>('/qr/resolve', {
			method: 'POST',
			body: JSON.stringify({ url: trimmed }),
		});
		log.info(`Resolved to: ${result.resolved_url}`);
		return result.resolved_url;
	} catch (error) {
		log.warn('Failed to resolve URL, using original:', error);
		// Fall back to original text — let the caller's parser handle it
		return trimmed;
	}
}
