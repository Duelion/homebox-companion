<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import QrScanner from 'qr-scanner';
	import heic2any from 'heic2any';

	interface Props {
		onScan: (decodedText: string) => void;
		onClose: () => void;
		onError?: (error: string) => void;
	}

	let { onScan, onClose, onError }: Props = $props();

	let videoElement: HTMLVideoElement;
	let fileInput: HTMLInputElement;
	let qrScanner: QrScanner | null = null;
	let error = $state<string | null>(null);
	let isStarting = $state(true);
	let hasScanned = $state(false);
	let cameraFailed = $state(false);
	let isInsecureContext = $state(false);
	let isProcessingFile = $state(false);

	async function startCamera() {
		error = null;
		isStarting = true;
		cameraFailed = false;
		hasScanned = false;

		try {
			// Check for secure context - camera APIs require HTTPS
			if (!window.isSecureContext) {
				isInsecureContext = true;
				error = 'Camera requires HTTPS. Use the upload option below.';
				isStarting = false;
				cameraFailed = true;
				onError?.(error);
				return;
			}

			qrScanner = new QrScanner(
				videoElement,
				(result) => {
					if (hasScanned) return; // Prevent multiple scans
					hasScanned = true;
					
					// Stop scanning before calling callback
					stopScanner().then(() => {
						onScan(result.data);
					});
				},
				{
					preferredCamera: 'environment',
					highlightScanRegion: true,
					highlightCodeOutline: true,
					returnDetailedScanResult: true,
				}
			);

			await qrScanner.start();
			isStarting = false;
		} catch (err) {
			console.error('QR Scanner error:', err);
			isStarting = false;
			cameraFailed = true;
			
			if (err instanceof Error) {
				const msg = err.message || '';
				const name = err.name || '';
				
				if (name === 'NotAllowedError' || msg.includes('Permission') || msg.includes('NotAllowed')) {
					error = 'Camera permission denied. Check your browser settings, or use the upload option below.';
				} else if (name === 'NotFoundError' || msg.includes('NotFound') || msg.includes('DevicesNotFound')) {
					error = 'No camera detected. Use the upload option below.';
				} else if (name === 'NotReadableError' || msg.includes('NotReadable')) {
					error = 'Camera is in use by another app. Close other apps or use the upload option below.';
				} else if (name === 'OverconstrainedError' || msg.includes('Overconstrained')) {
					error = 'Camera settings not supported. Use the upload option below.';
				} else if (name === 'NotSupportedError' || msg.includes('NotSupported')) {
					error = 'Camera not supported in this browser. Use the upload option below.';
				} else {
					error = `Camera error: ${msg || 'Unknown error'}. Use the upload option below.`;
				}
			} else {
				error = 'Failed to start camera. Use the upload option below.';
			}
			
			onError?.(error);
		}
	}

	onMount(() => {
		startCamera();
	});

	async function stopScanner() {
		if (qrScanner) {
			try {
				qrScanner.stop();
				qrScanner.destroy();
				qrScanner = null;
			} catch (err) {
				console.warn('Error stopping scanner:', err);
			}
		}
	}

	onDestroy(() => {
		stopScanner();
	});

	function handleClose() {
		stopScanner().then(() => {
			onClose();
		});
	}

	async function handleRetryCamera() {
		await stopScanner();
		startCamera();
	}

	function triggerFileUpload() {
		fileInput?.click();
	}

	// Convert HEIC images to JPEG (iOS may send HEIC format)
	async function convertHeicIfNeeded(file: File): Promise<Blob> {
		const isHeic = file.type === 'image/heic' || 
		               file.type === 'image/heif' ||
		               file.name.toLowerCase().endsWith('.heic') ||
		               file.name.toLowerCase().endsWith('.heif');
		
		if (isHeic) {
			const blob = await heic2any({ blob: file, toType: 'image/jpeg', quality: 0.92 });
			return Array.isArray(blob) ? blob[0] : blob;
		}
		return file;
	}

	// Normalize image through canvas with manual EXIF orientation correction
	// Firefox iOS doesn't auto-apply EXIF rotation, so we must do it manually
	async function normalizeImageOrientation(blob: Blob): Promise<Blob> {
		// Read EXIF orientation first
		const orientation = await readExifOrientation(blob);
		console.log('   EXIF orientation detected:', orientation);
		
		return new Promise((resolve, reject) => {
			const img = new Image();
			const url = URL.createObjectURL(blob);
			
			img.onload = () => {
				let width = img.naturalWidth;
				let height = img.naturalHeight;
				
				// Swap dimensions for 90° rotations (orientation 5, 6, 7, 8)
				const needsSwap = orientation && orientation >= 5 && orientation <= 8;
				if (needsSwap) {
					[width, height] = [height, width];
				}
				
				const canvas = document.createElement('canvas');
				canvas.width = width;
				canvas.height = height;
				const ctx = canvas.getContext('2d');
				if (!ctx) {
					URL.revokeObjectURL(url);
					reject(new Error('Canvas context not available'));
					return;
				}
				
				// Apply transformation based on EXIF orientation
				// https://sirv.com/help/articles/rotate-photos-to-be-upright/
				switch (orientation) {
					case 2: // Flip horizontal
						ctx.transform(-1, 0, 0, 1, width, 0);
						break;
					case 3: // Rotate 180°
						ctx.transform(-1, 0, 0, -1, width, height);
						break;
					case 4: // Flip vertical
						ctx.transform(1, 0, 0, -1, 0, height);
						break;
					case 5: // Transpose (flip horizontal + rotate 90° CCW)
						ctx.transform(0, 1, 1, 0, 0, 0);
						break;
					case 6: // Rotate 90° CW
						ctx.transform(0, 1, -1, 0, width, 0);
						break;
					case 7: // Transverse (flip horizontal + rotate 90° CW)
						ctx.transform(0, -1, -1, 0, width, height);
						break;
					case 8: // Rotate 90° CCW
						ctx.transform(0, -1, 1, 0, 0, height);
						break;
					default: // 1 or null - no transformation needed
						break;
				}
				
				ctx.drawImage(img, 0, 0);
				canvas.toBlob(
					(resultBlob) => {
						URL.revokeObjectURL(url);
						resultBlob ? resolve(resultBlob) : reject(new Error('Canvas conversion failed'));
					},
					'image/jpeg',
					0.92
				);
			};
			img.onerror = () => {
				URL.revokeObjectURL(url);
				reject(new Error('Failed to load image'));
			};
			img.src = url;
		});
	}

	// Helper to get full image metadata
	async function getImageMetadata(blob: Blob): Promise<Record<string, unknown>> {
		return new Promise((resolve) => {
			const img = new Image();
			const url = URL.createObjectURL(blob);
			img.onload = () => {
				URL.revokeObjectURL(url);
				resolve({
					naturalWidth: img.naturalWidth,
					naturalHeight: img.naturalHeight,
					width: img.width,
					height: img.height,
					complete: img.complete,
					currentSrc: img.currentSrc ? 'blob:...' : 'none',
				});
			};
			img.onerror = () => {
				URL.revokeObjectURL(url);
				resolve({ error: 'Failed to load image' });
			};
			img.src = url;
		});
	}

	// Read EXIF orientation from JPEG blob (returns 1-8, or null if not found)
	async function readExifOrientation(blob: Blob): Promise<number | null> {
		try {
			const buffer = await blob.slice(0, 65536).arrayBuffer(); // Read first 64KB
			const view = new DataView(buffer);
			
			// Check for JPEG magic bytes
			if (view.getUint16(0) !== 0xFFD8) return null;
			
			let offset = 2;
			while (offset < view.byteLength - 2) {
				const marker = view.getUint16(offset);
				offset += 2;
				
				// APP1 marker (EXIF)
				if (marker === 0xFFE1) {
					const length = view.getUint16(offset);
					offset += 2;
					
					// Check for "Exif\0\0"
					const exifHeader = view.getUint32(offset);
					if (exifHeader !== 0x45786966) return null;
					offset += 6;
					
					const tiffOffset = offset;
					const littleEndian = view.getUint16(offset) === 0x4949;
					offset += 8;
					
					const numEntries = view.getUint16(offset, littleEndian);
					offset += 2;
					
					for (let i = 0; i < numEntries; i++) {
						const tag = view.getUint16(offset, littleEndian);
						if (tag === 0x0112) { // Orientation tag
							return view.getUint16(offset + 8, littleEndian);
						}
						offset += 12;
					}
					return null;
				} else if ((marker & 0xFF00) === 0xFF00) {
					offset += view.getUint16(offset);
				} else {
					break;
				}
			}
			return null;
		} catch {
			return null;
		}
	}

	// Get full blob/file metadata
	async function getFullMetadata(blobOrFile: Blob | File, label: string): Promise<void> {
		const isFile = blobOrFile instanceof File;
		const imgMeta = await getImageMetadata(blobOrFile);
		const exifOrientation = await readExifOrientation(blobOrFile);
		
		const metadata: Record<string, unknown> = {
			// Blob properties
			size: blobOrFile.size,
			type: blobOrFile.type,
			// File-specific properties
			...(isFile && {
				name: (blobOrFile as File).name,
				lastModified: (blobOrFile as File).lastModified,
				lastModifiedDate: new Date((blobOrFile as File).lastModified).toISOString(),
				webkitRelativePath: (blobOrFile as File).webkitRelativePath || 'N/A',
			}),
			// Image properties
			...imgMeta,
			// EXIF
			exifOrientation: exifOrientation,
			exifOrientationMeaning: exifOrientation ? [
				'Unknown',
				'Normal (1)',
				'Flip horizontal (2)',
				'Rotate 180° (3)',
				'Flip vertical (4)',
				'Transpose (5)',
				'Rotate 90° CW (6)',
				'Transverse (7)',
				'Rotate 90° CCW (8)'
			][exifOrientation] || `Unknown (${exifOrientation})` : 'Not found',
		};
		
		console.log(`${label}:`, metadata);
	}

	async function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		isProcessingFile = true;
		error = null;

		try {
			console.log('========== QR SCAN DEBUG START ==========');
			
			// Log original file with full metadata
			await getFullMetadata(file, '1. ORIGINAL FILE');

			// Convert HEIC to JPEG if needed (iOS camera photos)
			const heicConverted = await convertHeicIfNeeded(file);
			const wasHeicConverted = heicConverted !== file;
			console.log('2. HEIC conversion:', wasHeicConverted ? 'YES - converted from HEIC' : 'NO - not HEIC');
			if (wasHeicConverted) {
				await getFullMetadata(heicConverted, '2b. AFTER HEIC CONVERSION');
			}

			// Normalize through canvas to apply EXIF orientation
			const imageBlob = await normalizeImageOrientation(heicConverted);
			await getFullMetadata(imageBlob, '3. AFTER CANVAS NORMALIZATION');
			
			const result = await QrScanner.scanImage(imageBlob, {
				returnDetailedScanResult: true,
			});
			
			console.log('4. RESULT: SUCCESS!');
			console.log('   QR Data:', result.data);
			console.log('   Corner Points:', result.cornerPoints);
			console.log('========== QR SCAN DEBUG END ============');
			
			hasScanned = true;
			await stopScanner();
			onScan(result.data);
		} catch (err) {
			console.error('4. RESULT: FAILED');
			console.error('   Error:', err instanceof Error ? err.message : String(err));
			console.error('   Error type:', err?.constructor?.name);
			if (err instanceof Error && err.stack) {
				console.error('   Stack:', err.stack);
			}
			console.log('========== QR SCAN DEBUG END ============');
			
			if (err instanceof Error && err.message.includes('No QR code found')) {
				error = 'No QR code found in image. Try a clearer photo.';
			} else {
				error = 'Could not read QR code from image. Try again.';
			}
			onError?.(error);
		} finally {
			isProcessingFile = false;
			// Reset file input so the same file can be selected again
			input.value = '';
		}
	}
</script>

<!-- Hidden file input for fallback -->
<input
	bind:this={fileInput}
	type="file"
	accept="image/jpeg,image/png,image/webp"
	onchange={handleFileSelect}
	class="hidden"
/>

<!-- Full-screen modal overlay -->
<div class="fixed inset-0 z-[100] bg-black flex flex-col">
	<!-- Header -->
	<div class="flex items-center justify-between p-4 bg-black/80">
		<h2 class="text-white font-semibold">Scan Location QR Code</h2>
		<button
			type="button"
			onclick={handleClose}
			class="p-2 text-white/70 hover:text-white transition-colors"
			aria-label="Close scanner"
		>
			<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
				<path d="M6 18L18 6M6 6l12 12" />
			</svg>
		</button>
	</div>

	<!-- Scanner area -->
	<div class="flex-1 flex items-center justify-center p-4">
		{#if cameraFailed}
			<div class="text-center p-6 max-w-sm">
				<div class="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-500/20 flex items-center justify-center">
					<svg class="w-8 h-8 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
						<path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
					</svg>
				</div>
				<p class="text-white/80 mb-6">{error}</p>
				
				<!-- Action buttons -->
				<div class="flex flex-col gap-3">
					<!-- File upload button (always available as fallback) -->
					<button
						type="button"
						onclick={triggerFileUpload}
						disabled={isProcessingFile}
						class="px-4 py-3 bg-primary hover:bg-primary/90 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
					>
						{#if isProcessingFile}
							<div class="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
							<span>Processing...</span>
						{:else}
							<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
								<path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
							</svg>
							<span>Upload QR Image</span>
						{/if}
					</button>

					<!-- Retry camera button (not shown for HTTPS issues) -->
					{#if !isInsecureContext}
						<button
							type="button"
							onclick={handleRetryCamera}
							class="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors"
						>
							Try Camera Again
						</button>
					{/if}

					<button
						type="button"
						onclick={handleClose}
						class="px-4 py-2 text-white/60 hover:text-white transition-colors"
					>
						Cancel
					</button>
				</div>
			</div>
		{:else}
			<div class="relative">
				<!-- Video element for QR scanner -->
				<video
					bind:this={videoElement}
					class="rounded-xl bg-black"
					style="width: min(90vw, 400px); height: min(90vw, 400px); object-fit: cover;"
				></video>

				<!-- Scanning overlay -->
				{#if isStarting}
					<div class="absolute inset-0 flex items-center justify-center bg-black/50 rounded-xl">
						<div class="text-center">
							<div class="w-8 h-8 border-2 border-white border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
							<p class="text-white/80 text-sm">Starting camera...</p>
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Footer with instructions -->
	<div class="p-4 bg-black/80 text-center">
		{#if cameraFailed}
			<p class="text-white/60 text-sm">
				Take a photo of the QR code or select an existing image
			</p>
		{:else}
			<p class="text-white/60 text-sm">
				Point your camera at a Homebox location QR code
			</p>
		{/if}
	</div>
</div>

<style>
	/* Style the qr-scanner overlay */
	:global(.scan-region-highlight) {
		border: 2px solid hsl(var(--primary)) !important;
		border-radius: 0.5rem;
	}
	
	:global(.scan-region-highlight-svg) {
		stroke: hsl(var(--primary)) !important;
	}
	
	:global(.code-outline-highlight) {
		stroke: hsl(var(--primary)) !important;
		stroke-width: 3px;
	}
</style>
