<script lang="ts">
	import { modalDialog } from '$lib/actions/dialog';
	import { onMount, tick, untrack } from 'svelte';
	import X from '@lucide/svelte/icons/x';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import SwitchCamera from '@lucide/svelte/icons/switch-camera';
	import Upload from '@lucide/svelte/icons/upload';
	import { captureVideoFrame, describeCameraError } from '$lib/utils/cameraCapture';
	import { createLogger } from '$lib/utils/logger';

	const log = createLogger({ prefix: 'Camera' });

	interface Props {
		/**
		 * Called with each photo as it is taken; the dialog stays open for more. Resolves to the reason
		 * when the photo is turned down (too large, over the limit): toasts are hidden behind the dialog.
		 */
		onCapture: (file: File) => string | undefined | Promise<string | undefined>;
		onClose: () => void;
		/** Called when a photo taken in this dialog is deleted from its thumbnail; omit to hide delete. */
		onRemove?: (file: File) => void;
		/** Called when the user chooses an existing photo instead; the caller closes the dialog. */
		onUseFilePicker: () => void;
		/** How many photos may still be added; the dialog closes after the last one. */
		remaining?: number;
		title?: string;
	}

	let {
		onCapture,
		onRemove,
		onClose,
		onUseFilePicker,
		remaining,
		title = 'Take a photo',
	}: Props = $props();

	// The limit as it was when the dialog opened: the caller adds photos asynchronously.
	const limit = untrack(() => remaining);

	let videoElement = $state<HTMLVideoElement>();
	let shutterButton = $state<HTMLButtonElement>();
	let stream: MediaStream | null = null;
	let cameras = $state<MediaDeviceInfo[]>([]);
	let currentDeviceId = $state<string>();
	let isStarting = $state(true);
	let isCapturing = $state(false);
	let error = $state<{ message: string; code: string } | null>(null);
	// Why the last photo was not added, until the next one is.
	let rejection = $state<string>();
	// Thumbnails of the photos taken while the dialog is open. These URLs belong to the dialog: the
	// shared object-URL cache is keyed by File, and the caller may be showing the same files.
	let shots = $state<{ file: File; url: string }[]>([]);
	let shotStrip = $state<HTMLUListElement>();
	let active = true;
	// Only the latest start may touch the dialog: a second one can begin before the first settles.
	let startId = 0;

	function stopCamera() {
		stream?.getTracks().forEach((track) => track.stop());
		stream = null;
		if (videoElement) videoElement.srcObject = null;
	}

	async function startCamera(deviceId?: string) {
		const id = ++startId;
		const isCurrent = () => active && id === startId;
		stopCamera();
		error = null;
		isStarting = true;
		// The video element is not rendered while an error is shown.
		await tick();
		try {
			const started = await navigator.mediaDevices.getUserMedia({
				audio: false,
				video: {
					...(deviceId
						? { deviceId: { exact: deviceId } }
						: { facingMode: { ideal: 'environment' } }),
					width: { ideal: 1920 },
					height: { ideal: 1080 },
				},
			});
			// The dialog may have been closed while the permission prompt was open.
			if (!isCurrent() || !videoElement) {
				started.getTracks().forEach((track) => track.stop());
				return;
			}
			stream = started;
			const [track] = started.getVideoTracks();
			// The camera was unplugged, or the browser took it away; stopping it here fires no event.
			track?.addEventListener('ended', () => {
				if (!active || stream !== started) return;
				startId++;
				stopCamera();
				error = { message: 'The camera was disconnected.', code: 'ENDED' };
				isStarting = false;
			});
			videoElement.srcObject = started;
			await videoElement.play();
			if (!isCurrent()) return;
			currentDeviceId = track?.getSettings().deviceId;
			// Device labels and ids are only complete once permission has been granted.
			const devices = await navigator.mediaDevices.enumerateDevices();
			if (!isCurrent()) return;
			cameras = devices.filter((device) => device.kind === 'videoinput');
			isStarting = false;
			// Space or Enter takes the photo as soon as the picture is live.
			await tick();
			if (active) shutterButton?.focus();
		} catch (err) {
			if (!isCurrent()) return;
			stopCamera();
			error = describeCameraError(err);
			isStarting = false;
			log.error('Camera failed to start:', err);
		}
	}

	onMount(() => {
		void startCamera();
		return () => {
			active = false;
			stopCamera();
			shots.forEach((shot) => URL.revokeObjectURL(shot.url));
		};
	});

	function switchCamera() {
		if (cameras.length < 2) return;
		const index = cameras.findIndex((camera) => camera.deviceId === currentDeviceId);
		void startCamera(cameras[(index + 1) % cameras.length].deviceId);
	}

	function removeShot(shot: { file: File; url: string }) {
		shots = shots.filter((other) => other !== shot);
		URL.revokeObjectURL(shot.url);
		onRemove?.(shot.file);
		// The button that had focus is gone.
		shutterButton?.focus();
	}

	// The shutter is never disabled while a frame is being saved: a disabled button drops keyboard
	// focus, and Space or Enter would stop taking photos after the first one.
	async function takePhoto() {
		if (!videoElement || isStarting || isCapturing) return;
		isCapturing = true;
		try {
			const file = await captureVideoFrame(videoElement);
			if (!active) return;
			// Wait for the caller's answer, so a thumbnail is only shown for a photo that was added.
			rejection = await onCapture(file);
			if (!active || rejection) return;
			shots = [...shots, { file, url: URL.createObjectURL(file) }];
			if (limit !== undefined && shots.length >= limit) {
				onClose();
				return;
			}
			// Keep the newest thumbnail in view.
			await tick();
			shotStrip?.scrollTo({ left: shotStrip.scrollWidth });
		} catch (err) {
			log.error('Could not take the photo:', err);
			if (active) {
				stopCamera();
				error = describeCameraError(err);
			}
		} finally {
			isCapturing = false;
		}
	}
</script>

<dialog
	use:modalDialog
	aria-label={title}
	oncancel={(event) => {
		event.preventDefault();
		onClose();
	}}
	class="fixed inset-0 z-overlay m-0 flex max-h-none max-w-none flex-col overflow-y-auto bg-neutral-950 p-0 size-full"
>
	<div class="flex items-center justify-between bg-neutral-950/80 p-4">
		<h2 class="font-semibold text-neutral-100">{title}</h2>
		<button
			type="button"
			onclick={onClose}
			class="min-h-touch min-w-touch p-2 text-neutral-400 transition-colors hover:text-neutral-100"
			aria-label="Close camera"
		>
			<X size={24} />
		</button>
	</div>

	<div class="flex flex-1 items-center justify-center p-4">
		{#if error}
			<div class="max-w-sm p-6 text-center">
				<div
					class="mx-auto mb-4 flex items-center justify-center rounded-full bg-warning-500/20 size-16"
				>
					<TriangleAlert class="text-warning-400" size={32} />
				</div>
				<p class="mb-2 text-neutral-300" role="alert">{error.message}</p>
				<p class="mb-4 font-mono text-caption text-neutral-500">Error code: {error.code}</p>
				<div class="flex flex-col gap-3">
					<button
						type="button"
						onclick={onUseFilePicker}
						class="flex items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-3 text-neutral-100 transition-colors hover:bg-primary-500"
					>
						<Upload size={20} />
						<span>Choose a photo instead</span>
					</button>
					<button
						type="button"
						onclick={() => void startCamera()}
						class="min-h-touch rounded-lg bg-neutral-800 px-4 py-2 text-neutral-100 transition-colors hover:bg-neutral-700"
					>
						Try Camera Again
					</button>
				</div>
			</div>
		{:else}
			<div class="flex max-w-full flex-col items-center gap-3">
				<div class="relative">
					<video
						bind:this={videoElement}
						class="camera-video rounded-xl bg-neutral-950"
						playsinline
						muted
					>
						<track kind="captions" label="No captions available" />
					</video>
					{#if isStarting}
						<div
							class="absolute inset-0 flex items-center justify-center rounded-xl bg-neutral-950/50"
						>
							<div class="text-center">
								<div
									class="mx-auto mb-2 animate-spin rounded-full border-2 border-neutral-100 border-t-transparent size-8"
								></div>
								<p class="text-body-sm text-neutral-300">Starting camera...</p>
							</div>
						</div>
					{/if}
				</div>
				<!-- A fixed height, so the preview does not move when the first photo replaces the hint -->
				<div class="h-20 max-w-full">
					{#if shots.length > 0}
						<ul
							bind:this={shotStrip}
							class="scrollbar-thin flex max-w-full gap-2 overflow-x-auto"
							aria-label="Photos taken"
						>
							{#each shots as shot, index (shot.url)}
								<li
									class="group relative shrink-0 overflow-hidden rounded-xl bg-neutral-800 ring-1 ring-neutral-700 size-20"
								>
									<img
										src={shot.url}
										alt="Photo taken {index + 1}"
										class="object-cover size-full"
									/>
									{#if onRemove}
										<button
											type="button"
											class="absolute right-1 top-1 flex items-center justify-center rounded-full bg-neutral-950/70 transition-all size-6 hover:bg-error-600 focus-visible:opacity-100 group-hover:opacity-100 [@media(hover:hover)]:opacity-0"
											aria-label="Delete photo {index + 1}"
											onclick={() => removeShot(shot)}
										>
											<X class="text-neutral-100" size={14} strokeWidth={2.5} />
										</button>
									{/if}
								</li>
							{/each}
						</ul>
					{:else}
						<p class="flex h-full items-center text-body-sm text-neutral-500">
							Point the camera at the item
						</p>
					{/if}
				</div>
			</div>
		{/if}
	</div>

	<div class="bg-neutral-950/80 p-4">
		{#if rejection && !error}
			<p class="mb-3 text-center text-body-sm text-warning-400" role="alert">
				Photo not added: {rejection}
			</p>
		{/if}
		{#if !error}
			<div class="mx-auto grid max-w-sm grid-cols-3 items-center">
				<div class="justify-self-start">
					{#if cameras.length > 1}
						<button
							type="button"
							onclick={switchCamera}
							disabled={isStarting}
							class="min-h-touch min-w-touch p-2 text-neutral-400 transition-colors hover:text-neutral-100 disabled:opacity-50"
							aria-label="Switch camera"
						>
							<SwitchCamera size={24} />
						</button>
					{/if}
				</div>
				<button
					type="button"
					bind:this={shutterButton}
					onclick={takePhoto}
					onkeydown={(event) => {
						// A held Enter key repeats the click; one press is one photo.
						if (event.key === 'Enter' && event.repeat) event.preventDefault();
					}}
					disabled={isStarting}
					class="justify-self-center rounded-full border-4 border-neutral-100 bg-primary-600 transition-colors size-16 hover:bg-primary-500 disabled:opacity-50"
					aria-label="Take photo"
				></button>
				<button
					type="button"
					onclick={onClose}
					class="min-h-touch justify-self-end px-4 py-2 font-medium text-primary-400 transition-colors hover:text-primary-300"
				>
					Done
				</button>
			</div>
		{/if}
		{#if error}
			<p class="text-center text-body-sm text-neutral-500">
				Your browser could not open the camera
			</p>
		{/if}
		<p class="sr-only" aria-live="polite">
			{#if shots.length > 0}
				{shots.length} {shots.length === 1 ? 'photo' : 'photos'} added
			{/if}
		</p>
	</div>
</dialog>
