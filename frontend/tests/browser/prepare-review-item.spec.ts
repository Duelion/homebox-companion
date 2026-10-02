import { test, expect } from '@playwright/test';
import type { ReviewItem } from '../../src/lib/types';
import { prepareReviewItem } from '../../src/lib/workflows/prepare-review-item';

function file(name: string, contents = name) {
	return new File([contents], name, { type: 'image/jpeg' });
}

function reviewItem(originalFile: File, additionalImages: File[] = []): ReviewItem {
	return {
		name: 'Desk lamp',
		quantity: 1,
		description: 'Brass desk lamp',
		sourceImageIndex: 2,
		originalFile,
		additionalImages,
		compressedDataUrl: 'data:image/jpeg;base64,cHJpbWFyeQ==',
		compressedAdditionalDataUrls: ['data:image/jpeg;base64,YWRkaXRpb25hbA=='],
		customThumbnail: 'data:image/jpeg;base64,dGh1bWJuYWls',
		thumbnailTransform: {
			scale: 1.2,
			rotation: 90,
			offsetX: 4,
			offsetY: -3,
			sourceImageIndex: 1,
			dataUrl: 'data:image/jpeg;base64,dHJhbnNmb3Jt',
		},
		manufacturer: 'Acme',
		model_number: 'DL-2',
		serial_number: 'A-12',
		purchase_price: 20,
		purchase_from: 'Store',
		notes: 'Keep upright',
		asset_id: '000-042',
		custom_fields: { Warranty: 'Two years' },
	};
}

test('unchanged ordered files retain both compressed payloads and item fields', () => {
	const primary = file('primary.jpg');
	const additional = file('additional.jpg');
	const item = reviewItem(primary, [additional]);
	const originalImages = [primary, additional];

	const prepared = prepareReviewItem(item, [...originalImages], originalImages);

	expect(prepared).not.toBe(item);
	expect(prepared.originalFile).toBe(primary);
	expect(prepared.additionalImages).toEqual([additional]);
	expect(prepared.compressedDataUrl).toBe(item.compressedDataUrl);
	expect(prepared.compressedAdditionalDataUrls).toBe(item.compressedAdditionalDataUrls);
	expect(prepared.customThumbnail).toBe(item.customThumbnail);
	expect(prepared.thumbnailTransform).toBe(item.thumbnailTransform);
	expect(prepared).toMatchObject({
		manufacturer: 'Acme',
		model_number: 'DL-2',
		serial_number: 'A-12',
		purchase_price: 20,
		purchase_from: 'Store',
		notes: 'Keep upright',
		asset_id: '000-042',
		custom_fields: { Warranty: 'Two years' },
	});
});

test('adding, removing, replacing, or reordering any file clears compressed payloads', () => {
	const primary = file('primary.jpg');
	const angleA = file('angle-a.jpg');
	const angleB = file('angle-b.jpg');
	const item = reviewItem(primary, [angleA, angleB]);
	const originalImages = [primary, angleA, angleB];
	const added = file('added.jpg');
	const replacement = file('replacement.jpg');

	for (const editedImages of [
		[primary, angleA, angleB, added],
		[primary, angleB],
		[primary, angleA, replacement],
		[primary, angleB, angleA],
	]) {
		const prepared = prepareReviewItem(item, editedImages, originalImages);
		expect(prepared.compressedDataUrl).toBeUndefined();
		expect(prepared.compressedAdditionalDataUrls).toBeUndefined();
		expect(prepared.originalFile).toBe(editedImages[0]);
		expect(prepared.additionalImages).toEqual(editedImages.slice(1));
	}
});

test('empty image list clears image state and custom thumbnail while preserving other fields', () => {
	const primary = file('primary.jpg');
	const additional = file('additional.jpg');
	const item = reviewItem(primary, [additional]);

	const prepared = prepareReviewItem(item, [], [primary, additional]);

	expect(prepared.originalFile).toBeUndefined();
	expect(prepared.additionalImages).toEqual([]);
	expect(prepared.compressedDataUrl).toBeUndefined();
	expect(prepared.compressedAdditionalDataUrls).toBeUndefined();
	expect(prepared.customThumbnail).toBeUndefined();
	expect(prepared.thumbnailTransform).toBe(item.thumbnailTransform);
	expect(prepared.manufacturer).toBe('Acme');
	expect(prepared.custom_fields).toEqual({ Warranty: 'Two years' });
});

test('preparation does not mutate its item or input image arrays', () => {
	const primary = file('primary.jpg');
	const additional = file('additional.jpg');
	const replacement = file('replacement.jpg');
	const item = reviewItem(primary, [additional]);
	const inputImages = [replacement, additional];
	const originalImages = [primary, additional];
	const itemBefore = { ...item, additionalImages: [...item.additionalImages!] };

	const prepared = prepareReviewItem(item, inputImages, originalImages);

	expect(item).toEqual(itemBefore);
	expect(inputImages).toEqual([replacement, additional]);
	expect(originalImages).toEqual([primary, additional]);
	expect(prepared.additionalImages).not.toBe(inputImages);
});
