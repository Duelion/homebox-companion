import { vision } from '$lib/api/vision';
import { authStore } from '$lib/stores/auth.svelte';
import { showToast } from '$lib/stores/ui.svelte';
import { workflowLogger as log } from '$lib/utils/logger';
import type { DeepReadonly, ReviewItem } from '$lib/types';

/** Make an independent form draft while preserving File identity for upload/cache checks. */
export function copyReviewItem(item: DeepReadonly<ReviewItem>): ReviewItem {
	return {
		...item,
		tag_ids: item.tag_ids ? [...item.tag_ids] : item.tag_ids,
		additionalImages: item.additionalImages ? [...item.additionalImages] : undefined,
		compressedAdditionalDataUrls: item.compressedAdditionalDataUrls
			? [...item.compressedAdditionalDataUrls]
			: undefined,
		thumbnailTransform: item.thumbnailTransform ? { ...item.thumbnailTransform } : undefined,
		custom_fields: item.custom_fields ? { ...item.custom_fields } : item.custom_fields,
		duplicate_match: item.duplicate_match ? { ...item.duplicate_match } : item.duplicate_match,
	};
}

/** Page-scoped correction requests; discarded responses cannot affect another review or account. */
export class ReviewEditor {
	private request: AbortController | null = null;
	private _isProcessing = $state(false);

	get isProcessing(): boolean {
		return this._isProcessing;
	}

	invalidate(): void {
		this.request?.abort();
		this.request = null;
		this._isProcessing = false;
	}

	async correct(
		item: DeepReadonly<ReviewItem>,
		image: File | undefined,
		prompt: string,
		isCurrent: () => boolean,
		apply: (updates: Partial<ReviewItem>) => void
	): Promise<boolean> {
		if (this._isProcessing) return false;
		if (!image) {
			showToast('Original image not found', 'error');
			return false;
		}
		const request = new AbortController();
		const scope = authStore.verifiedScope;
		const connection = authStore.connection;
		const valid = () =>
			this.request === request &&
			!request.signal.aborted &&
			isCurrent() &&
			authStore.connection === connection &&
			authStore.verifiedScope?.contextId === scope?.contextId &&
			authStore.verifiedScope?.groupId === scope?.groupId;
		this.request = request;
		this._isProcessing = true;
		try {
			const response = await vision.correct(
				image,
				{
					name: item.name,
					quantity: item.quantity,
					description: item.description,
					manufacturer: item.manufacturer,
					model_number: item.model_number,
					serial_number: item.serial_number,
					purchase_price: item.purchase_price,
					purchase_from: item.purchase_from,
					notes: item.notes,
				},
				prompt,
				{ signal: request.signal }
			);
			if (!valid() || !response.items.length) return false;
			const corrected = response.items[0];
			apply({
				name: corrected.name,
				quantity: corrected.quantity,
				description: corrected.description ?? null,
				tag_ids: corrected.tag_ids ?? null,
				manufacturer: corrected.manufacturer ?? null,
				model_number: corrected.model_number ?? null,
				serial_number: corrected.serial_number ?? null,
				purchase_price: corrected.purchase_price ?? null,
				purchase_from: corrected.purchase_from ?? null,
				notes: corrected.notes ?? null,
				...(corrected.custom_fields != null ? { custom_fields: corrected.custom_fields } : {}),
			});
			return true;
		} catch (error) {
			if (valid()) {
				log.error('AI correction failed:', error);
				showToast(error instanceof Error ? error.message : 'Correction failed', 'error');
			}
			return false;
		} finally {
			if (this.request === request) {
				this.request = null;
				this._isProcessing = false;
			}
		}
	}
}
