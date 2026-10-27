/**
 * Generate a UUID v4 in browsers with or without a secure context.
 *
 * crypto.randomUUID() is restricted to secure contexts, whereas
 * crypto.getRandomValues() also works when accessing a local server over HTTP.
 */
export function createUuidV4(): string {
	if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();

	const bytes = crypto.getRandomValues(new Uint8Array(16));
	bytes[6] = (bytes[6] & 0x0f) | 0x40;
	bytes[8] = (bytes[8] & 0x3f) | 0x80;
	const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
	return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
