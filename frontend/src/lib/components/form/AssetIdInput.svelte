<script lang="ts">
	/**
	 * AssetIdInput - Input field with QR scanner for asset IDs
	 *
	 * Features:
	 * - Text input for manual entry
	 * - QR scan button to scan pre-printed QR codes
	 * - Conflict warning state (amber border + triangle) when ID exists
	 * - Parses QR URL format: https://homebox.duelion.com/a/{asset_id}
	 */
	import { QrCode, TriangleAlert, Loader2 } from 'lucide-svelte';
	import type { AssetIdConflict } from '$lib/types';
	import QrScanner from '$lib/components/QrScanner.svelte';

	interface Props {
		value: string | null;
		conflict: AssetIdConflict | null;
		/** Whether the input is disabled */
		disabled?: boolean;
		placeholder?: string;
		/** Whether conflict check is in progress */
		isChecking?: boolean;
		onChange: (value: string | null) => void;
	}

	let {
		value,
		conflict,
		disabled = false,
		placeholder = 'e.g., 000-001',
		isChecking = false,
		onChange,
	}: Props = $props();

	let showScanner = $state(false);

	// Extract asset ID from QR code URL or raw ID
	function parseAssetIdFromUrl(scannedText: string): string {
		// Try to parse Homebox asset URL format: https://homebox.duelion.com/a/{asset_id}
		// Also supports variations like /a/000-001 or just the raw ID
		const urlPattern = /\/a\/([^\/\s]+)/;
		const match = scannedText.match(urlPattern);

		if (match && match[1]) {
			return match[1];
		}

		// If no URL pattern found, treat the entire text as the asset ID
		// (after trimming whitespace)
		return scannedText.trim();
	}

	function handleScan(scannedText: string) {
		const assetId = parseAssetIdFromUrl(scannedText);
		onChange(assetId || null);
		showScanner = false;
	}

	function handleInputChange(e: Event) {
		const target = e.target as HTMLInputElement;
		const newValue = target.value;
		// Don't trim while typing - preserve exactly what user types
		// Empty string becomes null for consistency
		onChange(newValue || null);
	}

	function handleScannerClose() {
		showScanner = false;
	}

	// Determine if we should show warning styling
	const hasConflict = $derived(conflict !== null);
</script>

<div>
	<div class="mb-1 flex items-baseline gap-2">
		<label for="asset-id-input" class="text-body-sm font-medium text-neutral-300">Asset ID</label>
		<span class="text-xs text-neutral-500">Optional – auto-assigned if blank</span>
	</div>

	<div class="flex items-center gap-2">
		<div class="relative flex-1">
			<input
				type="text"
				id="asset-id-input"
				value={value ?? ''}
				oninput={handleInputChange}
				{placeholder}
				{disabled}
				class="input w-full pr-8 text-body-sm {hasConflict
					? 'border-warning-500 focus:border-warning-400 focus:ring-warning-500/20'
					: ''}"
			/>
			{#if isChecking}
				<div class="absolute right-2 top-1/2 -translate-y-1/2">
					<Loader2 class="animate-spin text-neutral-400" size={16} strokeWidth={2} />
				</div>
			{:else if hasConflict}
				<div class="absolute right-2 top-1/2 -translate-y-1/2" title="Asset ID already exists">
					<TriangleAlert class="text-warning-400" size={16} strokeWidth={2} />
				</div>
			{/if}
		</div>

		<button
			type="button"
			onclick={() => (showScanner = true)}
			{disabled}
			class="flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-600 bg-neutral-800 text-neutral-400 transition-colors hover:border-neutral-500 hover:bg-neutral-700 hover:text-neutral-200 disabled:opacity-50"
			aria-label="Scan QR code"
			title="Scan QR code"
		>
			<QrCode size={18} strokeWidth={1.5} />
		</button>
	</div>

	{#if hasConflict && conflict}
		<p class="mt-1 text-xs text-warning-200/80">
			Asset ID "{conflict.asset_id}" already used by "{conflict.item_name}"
		</p>
	{/if}
</div>

{#if showScanner}
	<QrScanner onScan={handleScan} onClose={handleScannerClose} title="Scan Asset ID QR Code" />
{/if}
