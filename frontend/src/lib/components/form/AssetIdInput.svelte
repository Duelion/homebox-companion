<script lang="ts">
	/**
	 * AssetIdInput - Input field with QR scanner for asset IDs
	 *
	 * Features:
	 * - Text input for manual entry
	 * - QR scan button to scan pre-printed QR codes
	 * - Parses QR URL format: https://homebox.duelion.com/a/{asset_id}
	 */
	import { onDestroy } from 'svelte';
	import { QrCode } from '@lucide/svelte';
	import QrScanner from '$lib/components/QrScanner.svelte';
	import { resolveQrUrl } from '$lib/utils/qrUrl';

	interface Props {
		value: string | null;
		/** Stable item identity when this field is reused between drafts. */
		identity?: unknown;
		/** Whether the input is disabled */
		disabled?: boolean;
		placeholder?: string;
		/** Whether to show the label (default: true) */
		showLabel?: boolean;
		onChange: (value: string | null) => void;
	}

	let {
		value,
		identity,
		disabled = false,
		placeholder = 'e.g., 000-001',
		showLabel = true,
		onChange,
	}: Props = $props();

	const fieldId = $props.id();
	let scanGeneration = 0;
	let scanController: AbortController | undefined;
	let disposed = false;
	function invalidateScan() {
		scanGeneration++;
		scanController?.abort();
	}
	$effect(() => {
		void value;
		void identity;
		void disabled;
		invalidateScan();
	});
	onDestroy(() => {
		disposed = true;
		invalidateScan();
	});

	let showScanner = $state(false);

	// Extract asset ID from QR code URL or raw ID
	function parseAssetIdFromUrl(scannedText: string): string {
		// Try to parse Homebox asset URL format: https://homebox.duelion.com/a/{asset_id}
		// Also supports variations like /a/000-001 or just the raw ID
		const urlPattern = /\/a\/([^/\s]+)/;
		const match = scannedText.match(urlPattern);

		if (match && match[1]) {
			return match[1];
		}

		// If no URL pattern found, treat the entire text as the asset ID
		// (after trimming whitespace)
		return scannedText.trim();
	}

	async function handleScan(scannedText: string) {
		invalidateScan();
		const operation = scanGeneration;
		const initialValue = value;
		const initialIdentity = identity;
		const change = onChange;
		const controller = new AbortController();
		scanController = controller;
		const resolvedUrl = await resolveQrUrl(scannedText, controller.signal);
		if (
			disposed ||
			controller.signal.aborted ||
			operation !== scanGeneration ||
			disabled ||
			value !== initialValue ||
			identity !== initialIdentity
		)
			return;
		const assetId = parseAssetIdFromUrl(resolvedUrl);
		change(assetId || null);
		showScanner = false;
	}

	function handleInputChange(e: Event) {
		invalidateScan();
		const target = e.target as HTMLInputElement;
		const newValue = target.value;
		// Don't trim while typing - preserve exactly what user types
		// Empty string becomes null for consistency
		onChange(newValue || null);
	}

	function handleScannerClose() {
		invalidateScan();
		showScanner = false;
	}
</script>

<div>
	{#if showLabel}
		<div class="mb-1 flex items-baseline gap-2">
			<label for={fieldId} class="text-body-sm font-medium text-neutral-300">Asset ID</label>
			<span class="text-caption text-neutral-500">Optional – auto-assigned if blank</span>
		</div>
	{/if}

	<div class="flex items-center gap-2">
		<div class="relative flex-1">
			<input
				type="text"
				id={fieldId}
				aria-label={showLabel ? undefined : 'Asset ID'}
				value={value ?? ''}
				oninput={handleInputChange}
				{placeholder}
				{disabled}
				class="input w-full text-body-sm"
			/>
		</div>

		<button
			type="button"
			onclick={() => (showScanner = true)}
			{disabled}
			class="flex items-center justify-center rounded-lg border border-neutral-600 bg-neutral-800 text-neutral-400 transition-colors hover:border-neutral-500 hover:bg-neutral-700 hover:text-neutral-200 disabled:opacity-50 size-9"
			aria-label="Scan QR code"
			title="Scan QR code"
		>
			<QrCode size={18} strokeWidth={1.5} />
		</button>
	</div>
</div>

{#if showScanner}
	<QrScanner onScan={handleScan} onClose={handleScannerClose} title="Scan Asset ID QR Code" />
{/if}
