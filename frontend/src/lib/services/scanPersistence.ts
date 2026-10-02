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
	private metadataScope: string | null = null;
	private revision = 0;
	private writeQueue: Promise<void> = Promise.resolve();

	resetMetadata(): void {
		this.createdAt = null;
		this.sessionId = null;
		this.metadataScope = null;
		this.revision++;
	}

	/** Snapshot once before FileReader yields; only the latest save may enqueue a write. */
	async save(readDraft: () => ScanDraft, isCurrent: () => boolean): Promise<void> {
		const scope = storage.captureSessionScope();
		if (!scope || !isCurrent()) return;
		const revision = ++this.revision;
		try {
			const draft = readDraft();
			// Copy mutable image metadata and arrays, retaining immutable File objects.
			const capturedImages = draft.images.map((image) => ({
				...image,
				additionalFiles: image.additionalFiles ? [...image.additionalFiles] : undefined,
			}));
			// JSON detaches nested Svelte proxies without attempting to clone Files.
			const { detectedItems, confirmedItems } = draft;
			const snapshot = JSON.parse(
				JSON.stringify({
					...draft,
					images: undefined,
					detectedItems: detectedItems.map(serializeReviewItem),
					confirmedItems: confirmedItems.map(serializeConfirmedItem),
				})
			);
			const images = await Promise.all(capturedImages.map(serializeImage));
			const write = this.writeQueue.then(async () => {
				if (!isCurrent() || revision !== this.revision) return;
				const scopeKey = JSON.stringify(scope);
				if (this.metadataScope !== scopeKey) {
					this.createdAt = null;
					this.sessionId = null;
					this.metadataScope = scopeKey;
				}
				const now = Date.now();
				this.createdAt ??= now;
				this.sessionId ??= crypto.randomUUID();
				const session: StoredSession = {
					...snapshot,
					id: this.sessionId,
					createdAt: this.createdAt,
					updatedAt: now,
					images,
				};
				await storage.save(session, scope);
			});
			this.writeQueue = write.catch(() => {});
			await write;
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
			this.metadataScope = JSON.stringify(scope);
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
		this.revision++;
		const clear = this.writeQueue.then(() => storage.clear(scope));
		this.writeQueue = clear.catch(() => {});
		return clear;
	}
}
