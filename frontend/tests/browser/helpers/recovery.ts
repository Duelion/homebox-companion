import type { Page } from '@playwright/test';

const databaseName = 'hbc-scan-recovery';

// This only seeds the targeted legacy regression. The sessionStorage marker survives
// reload in the same tab, so a broken app recovery path cannot be hidden by reseeding.
export async function seedDraftOnce(page: Page, scope: string, draft: Record<string, unknown>) {
	await page.addInitScript(
		async ({ scope, draft }) => {
			if (location.origin !== 'http://127.0.0.1:4173') return;
			const marker = `hbc-test-seeded-${scope}`;
			if (sessionStorage.getItem(marker)) return;
			const db = await new Promise<IDBDatabase>((resolve, reject) => {
				const open = indexedDB.open('hbc-scan-recovery', 2);
				open.onupgradeneeded = () => {
					if (!open.result.objectStoreNames.contains('sessions')) {
						open.result.createObjectStore('sessions');
					}
				};
				open.onsuccess = () => resolve(open.result);
				open.onerror = () => reject(open.error);
			});
			try {
				await new Promise<void>((resolve, reject) => {
					const tx = db.transaction('sessions', 'readwrite');
					tx.objectStore('sessions').put(draft, scope);
					tx.oncomplete = () => resolve();
					tx.onerror = () => reject(tx.error);
				});
				sessionStorage.setItem(marker, '1');
			} finally {
				db.close();
			}
		},
		{ scope, draft }
	);
}

export async function readDrafts(page: Page): Promise<Record<string, unknown>[]> {
	return page.evaluate(async (name) => {
		const db = await new Promise<IDBDatabase>((resolve, reject) => {
			const open = indexedDB.open(name, 2);
			open.onsuccess = () => resolve(open.result);
			open.onerror = () => reject(open.error);
		});
		try {
			return await new Promise<Record<string, unknown>[]>((resolve, reject) => {
				const request = db.transaction('sessions').objectStore('sessions').getAll();
				request.onsuccess = () => resolve(request.result);
				request.onerror = () => reject(request.error);
			});
		} finally {
			db.close();
		}
	}, databaseName);
}

export async function putDraft(page: Page, scope: string, draft: Record<string, unknown>) {
	await page.evaluate(
		async ({ scope, draft, name }) => {
			const db = await new Promise<IDBDatabase>((resolve, reject) => {
				const open = indexedDB.open(name, 2);
				open.onupgradeneeded = () => {
					if (!open.result.objectStoreNames.contains('sessions')) {
						open.result.createObjectStore('sessions');
					}
				};
				open.onsuccess = () => resolve(open.result);
				open.onerror = () => reject(open.error);
			});
			try {
				await new Promise<void>((resolve, reject) => {
					const tx = db.transaction('sessions', 'readwrite');
					tx.objectStore('sessions').put(draft, scope);
					tx.oncomplete = () => resolve();
					tx.onerror = () => reject(tx.error);
				});
			} finally {
				db.close();
			}
		},
		{ scope, draft, name: databaseName }
	);
}
