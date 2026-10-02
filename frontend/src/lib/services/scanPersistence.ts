import type { CapturedImage, ReviewItem, ConfirmedItem } from '$lib/types';
import {
	type StoredSession,
	serializeImage,
	serializeReviewItem,
	serializeConfirmedItem,
	deserializeImage,
	deserializeReviewItem,
	deserializeConfirmedItem,
	revokeImageObjectUrls,
} from './serialize';
import * as storage from './sessionPersistence';
import { workflowLogger as log } from '$lib/utils/logger';

export { captureSessionScope } from './sessionPersistence';
export type { SessionSummary } from './sessionPersistence';

/** Runtime data crossing the storage boundary; save timing remains in the workflow. */
export interface ScanDraft extends Omit<
	StoredSession,
	'id' | 'createdAt' | 'updatedAt' | 'images' | 'detectedItems' | 'confirmedItems'
> {
	images: CapturedImage[];
	detectedItems: ReviewItem[];
	confirmedItems: ConfirmedItem[];
}
type RecoveredScan = ScanDraft & Pick<StoredSession, 'id' | 'createdAt' | 'updatedAt'>;

export class ScanPersistence {
	private createdAt: number | null = null;
	private sessionId: string | null = null;

	resetMetadata(): void {
		this.createdAt = null;
		this.sessionId = null;
	}

	/** Read live fields after image conversion and reject invalidated contexts. */
	async save(readDraft: () => ScanDraft, isCurrent: () => boolean): Promise<void> {
		const scope = storage.captureSessionScope();
		if (!scope) return;
		try {
			const images = await Promise.all(readDraft().images.map(serializeImage));
			if (!isCurrent()) return;
			const draft = readDraft();
			const now = Date.now();
			this.createdAt ??= now;
			this.sessionId ??= crypto.randomUUID();
			// IndexedDB cannot clone Svelte proxies nested in item fields or status maps.
			const session: StoredSession = {
				...draft,
				id: this.sessionId,
				createdAt: this.createdAt,
				updatedAt: now,
				images,
				detectedItems: JSON.parse(JSON.stringify(draft.detectedItems.map(serializeReviewItem))),
				confirmedItems: JSON.parse(
					JSON.stringify(draft.confirmedItems.map(serializeConfirmedItem))
				),
				imageStatuses: draft.imageStatuses
					? JSON.parse(JSON.stringify(draft.imageStatuses))
					: undefined,
			};
			if (!isCurrent()) return;
			await storage.save(session, scope);
		} catch (error) {
			// A failed autosave must not interrupt the user's workflow.
			log.error('Failed to persist scan session:', error);
		}
	}

	/** Hydrate a complete draft before exposing it to workflow services. */
	async recover(
		scope: storage.SessionScope,
		isCurrent: () => boolean
	): Promise<RecoveredScan | null> {
		const session = await storage.load(scope);
		if (!session || !isCurrent()) return null;
		const images: CapturedImage[] = [];
		let recovered = false;
		try {
			// Track completed images so a corrupt later image cannot leak their URLs.
			for (const storedImage of session.images) {
				images.push(await deserializeImage(storedImage));
				if (!isCurrent()) return null;
			}
			if (!isCurrent()) return null;
			const detectedItems = await Promise.all(session.detectedItems.map(deserializeReviewItem));
			if (!isCurrent()) return null;
			const confirmedItems = await Promise.all(
				session.confirmedItems.map(deserializeConfirmedItem)
			);
			if (!isCurrent()) return null;
			this.createdAt = session.createdAt;
			this.sessionId = session.id;
			recovered = true;
			return { ...session, images, detectedItems, confirmedItems };
		} finally {
			if (!recovered) images.forEach(revokeImageObjectUrls);
		}
	}

	hasRecoverableSession(): Promise<boolean> {
		return storage.hasRecoverableSession();
	}
	getRecoverySummary(): Promise<storage.SessionSummary | null> {
		return storage.getSessionSummary();
	}
	clear(scope: storage.SessionScope): Promise<void> {
		return storage.clear(scope);
	}
}
