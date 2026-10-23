/** Homebox v0.26.2/v0.27.0 repo.AssetID JSON contract: strip hyphens, parse int64.
 * https://github.com/sysadminsmedia/homebox/blob/v0.27.0/backend/internal/data/repo/asset_id_type.go
 * Keep zero explicit (Homebox treats it as unassigned); blank means automatic assignment.
 */
export const ASSET_ID_ERROR =
	'Enter a numeric Homebox asset ID (for example, 032-303), or leave it blank.';
export function normalizeAssetId(value: string | null | undefined): string | null {
	const input = value?.trim() ?? '';
	if (!input) return null;
	const digits = input.replaceAll('-', '');
	if (!/^\+?[0-9]+$/.test(digits)) throw new Error(ASSET_ID_ERROR);
	const number = BigInt(digits);
	if (number > 9223372036854775807n) throw new Error(ASSET_ID_ERROR);
	if (number === 0n) return '0';
	const padded = number.toString().padStart(6, '0');
	return `${padded.slice(0, 3)}-${padded.slice(3)}`;
}
export function assetIdError(value: string | null | undefined): string | null {
	try {
		normalizeAssetId(value);
		return null;
	} catch {
		return ASSET_ID_ERROR;
	}
}
