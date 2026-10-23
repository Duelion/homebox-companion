import { assetIdError } from './assetId';

export function itemNameError(value: unknown): string | null {
	if (typeof value !== 'string' || !value.trim()) return 'Enter an item name.';
	if (value.trim().length > 255) return 'Use 255 characters or fewer for the item name.';
	return null;
}
export function itemQuantityError(value: unknown): string | null {
	return typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value) && value > 0
		? null
		: 'Enter a whole quantity of 1 or more.';
}
export function itemPriceError(value: unknown): string | null {
	return value == null || (typeof value === 'number' && Number.isFinite(value) && value >= 0)
		? null
		: 'Enter a purchase price of 0 or more, or leave it blank.';
}
export function itemValidationError(item: {
	name: unknown;
	quantity: unknown;
	purchase_price?: unknown;
	asset_id?: string | null;
}): string | null {
	return (
		itemNameError(item.name) ??
		itemQuantityError(item.quantity) ??
		itemPriceError(item.purchase_price) ??
		assetIdError(item.asset_id)
	);
}
