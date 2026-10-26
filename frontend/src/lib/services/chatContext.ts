import { browser } from '$app/environment';
import { createUuidV4 } from '$lib/utils/uuid';

const CONTEXT_KEY = 'hbc-chat-context';

export function getChatContextId(): string {
	if (!browser) return '';
	let id = localStorage.getItem(CONTEXT_KEY);
	if (!id || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) {
		id = createUuidV4();
		localStorage.setItem(CONTEXT_KEY, id);
	}
	return id;
}

export function chatContextHeader(): Record<string, string> {
	const id = getChatContextId();
	return id ? { 'X-Companion-Chat-Context': id } : {};
}
