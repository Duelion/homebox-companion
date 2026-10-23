import type { CapturedImage, ReviewItem, ConfirmedItem } from '$lib/types';
import {
	type StoredSession,
	serializeImage,
	serializeReviewItem,
	serializeConfirmedItem,
	serializeReviewPhotos,
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
	| 'id'
	| 'createdAt'
	| 'updatedAt'
	| 'images'
	| 'detectedItems'
	| 'confirmedItems'
	| 'activeReviewDraft'
> {
	images: CapturedImage[];
	detectedItems: ReviewItem[];
	confirmedItems: ConfirmedItem[];
	activeReviewDraft?: ReviewItem;
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
	async save(readDraft: () => ScanDraft, isCurrent: () => boolean): Promise<boolean> {
		const scope = storage.captureSessionScope();
		if (!scope || !isCurrent()) return false;
		const revision = ++this.revision;
		let saved = false;
		try {
			const draft = readDraft();
			// Copy mutable image metadata and arrays, retaining immutable File objects.
			const capturedImages = draft.images.map((image) => ({
				...image,
				additionalFiles: image.additionalFiles ? [...image.additionalFiles] : undefined,
			}));
			// JSON detaches nested Svelte proxies without attempting to clone Files.
			const { detectedItems, confirmedItems, activeReviewDraft } = draft;
			const reviewItems = [
				...detectedItems,
				...confirmedItems,
				...(activeReviewDraft ? [activeReviewDraft] : []),
			].map((item) => ({
				...item,
				additionalImages: item.additionalImages ? [...item.additionalImages] : undefined,
			}));
			const snapshot = JSON.parse(
				JSON.stringify({
					...draft,
					images: undefined,
					detectedItems: detectedItems.map(serializeReviewItem),
					confirmedItems: confirmedItems.map(serializeConfirmedItem),
					activeReviewDraft: activeReviewDraft ? serializeReviewItem(activeReviewDraft) : undefined,
				})
			);
			const images = await Promise.all(capturedImages.map(serializeImage));
			const photos = await Promise.all(reviewItems.map(serializeReviewPhotos));
			let photoIndex = 0;
			for (const item of [
				...snapshot.detectedItems,
				...snapshot.confirmedItems,
				...(snapshot.activeReviewDraft ? [snapshot.activeReviewDraft] : []),
			]) {
				item.photos = photos[photoIndex++];
			}
			const write = this.writeQueue.then(async () => {
				if (
					!isCurrent() ||
					revision !== this.revision ||
					JSON.stringify(storage.captureSessionScope()) !== JSON.stringify(scope)
				)
					return;
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
				saved = await storage.save(session, scope);
			});
			this.writeQueue = write.catch(() => {});
			await write;
		} catch (error) {
			// A failed autosave must not interrupt the user's workflow.
			log.error('Failed to persist scan session:', error);
		}
		return saved;
	}

	/** Hydrate a complete draft before exposing it to workflow services. */
	async recover(
		scope: storage.SessionScope,
		isCurrent: () => boolean
	): Promise<RecoveredScan | null> {
		this.revision++;
		const current = () =>
			isCurrent() && JSON.stringify(storage.captureSessionScope()) === JSON.stringify(scope);
		const session = await storage.load(scope);
		if (!session || !current()) return null;
		const images: CapturedImage[] = [];
		let recovered = false;
		try {
			// Track completed images so a corrupt later image cannot leak their URLs.
			for (const storedImage of session.images) {
				images.push(await deserializeImage(storedImage));
				if (!current()) return null;
			}
			if (!current()) return null;
			const detectedItems = await Promise.all(session.detectedItems.map(deserializeReviewItem));
			if (!current()) return null;
			const confirmedItems = await Promise.all(
				session.confirmedItems.map(deserializeConfirmedItem)
			);
			// Old sessions did not store raw selected files. Reuse captured source photos
			// only when no explicit photo list exists (including an intentional empty list).
			const hydrateLegacy = (item: ReviewItem, stored: { photos?: unknown; reviewId?: string }) => {
				item.reviewId ??= crypto.randomUUID();
				if (stored.photos === undefined && !item.originalFile) {
					item.originalFile = images[item.sourceImageIndex]?.file;
					item.additionalImages ??= images[item.sourceImageIndex]?.additionalFiles;
				}
			};
			detectedItems.forEach((item, index) => hydrateLegacy(item, session.detectedItems[index]));
			confirmedItems.forEach((item, index) => hydrateLegacy(item, session.confirmedItems[index]));
			let activeReviewDraft = session.activeReviewDraft
				? await deserializeReviewItem(session.activeReviewDraft)
				: undefined;
			if (
				activeReviewDraft &&
				activeReviewDraft.reviewId !== detectedItems[session.currentReviewIndex]?.reviewId
			) {
				// An overlay for another item is never allowed to replace the current draft.
				activeReviewDraft = undefined;
			}
			if (!current()) return null;
			this.metadataScope = JSON.stringify(scope);
			this.createdAt = session.createdAt;
			this.sessionId = session.id;
			recovered = true;
			return { ...session, images, detectedItems, confirmedItems, activeReviewDraft };
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
