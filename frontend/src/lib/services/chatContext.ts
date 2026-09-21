import { browser } from '$app/environment';

const CONTEXT_KEY = 'hbc-chat-context';

function createContextId(): string {
	if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();

	const bytes = crypto.getRandomValues(new Uint8Array(16));
	bytes[6] = (bytes[6] & 0x0f) | 0x40;
	bytes[8] = (bytes[8] & 0x3f) | 0x80;
	const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
	return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function getChatContextId(): string {
	if (!browser) return '';
	let id = localStorage.getItem(CONTEXT_KEY);
	if (!id || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) {
		id = createContextId();
		localStorage.setItem(CONTEXT_KEY, id);
	}
	return id;
}

export function chatContextHeader(): Record<string, string> {
	const id = getChatContextId();
	return id ? { 'X-Companion-Chat-Context': id } : {};
}
