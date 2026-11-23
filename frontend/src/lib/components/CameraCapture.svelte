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
		/** Called with each photo as it is taken; the dialog stays open for more. */
		onCapture: (file: File) => void;
		onClose: () => void;
		/** Called when the user chooses an existing photo instead; the caller closes the dialog. */
		onUseFilePicker: () => void;
		/** How many photos may still be added; the dialog closes after the last one. */
		remaining?: number;
		title?: string;
	}

	let { onCapture, onClose, onUseFilePicker, remaining, title = 'Take a photo' }: Props = $props();

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
	// Thumbnails of the photos taken while the dialog is open. These URLs belong to the dialog: the
	// shared object-URL cache is keyed by File, and the caller may be showing the same files.
	let shots = $state<string[]>([]);
	let shotStrip = $state<HTMLUListElement>();
	let active = true;

	function stopCamera() {
		stream?.getTracks().forEach((track) => track.stop());
		stream = null;
		if (videoElement) videoElement.srcObject = null;
	}

	async function startCamera(deviceId?: string) {
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
			if (!active || !videoElement) {
				started.getTracks().forEach((track) => track.stop());
				return;
			}
			stream = started;
			videoElement.srcObject = started;
			await videoElement.play();
			if (!active) return;
			currentDeviceId = started.getVideoTracks()[0]?.getSettings().deviceId;
			// Device labels and ids are only complete once permission has been granted.
			const devices = await navigator.mediaDevices.enumerateDevices();
			if (!active) return;
			cameras = devices.filter((device) => device.kind === 'videoinput');
			isStarting = false;
			// Space or Enter takes the photo as soon as the picture is live.
			await tick();
			if (active) shutterButton?.focus();
		} catch (err) {
			if (!active) return;
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
			shots.forEach((url) => URL.revokeObjectURL(url));
		};
	});

	function switchCamera() {
		if (cameras.length < 2) return;
		const index = cameras.findIndex((camera) => camera.deviceId === currentDeviceId);
		void startCamera(cameras[(index + 1) % cameras.length].deviceId);
	}

	async function takePhoto() {
		if (!videoElement || isStarting || isCapturing) return;
		isCapturing = true;
		try {
			const file = await captureVideoFrame(videoElement);
			if (!active) return;
			shots = [...shots, URL.createObjectURL(file)];
			onCapture(file);
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
		{/if}
	</div>

	<div class="bg-neutral-950/80 p-4">
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
					disabled={isStarting || isCapturing}
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
		{#if shots.length > 0}
			<ul
				bind:this={shotStrip}
				class="mx-auto mt-3 flex w-fit max-w-full gap-2 overflow-x-auto"
				aria-label="Photos taken"
			>
				{#each shots as url, index (url)}
					<li class="shrink-0">
						<img src={url} alt="Photo taken {index + 1}" class="rounded-lg object-cover size-14" />
					</li>
				{/each}
			</ul>
		{/if}
		<p
			class={shots.length > 0 ? 'sr-only' : 'mt-3 text-center text-body-sm text-neutral-500'}
			aria-live="polite"
		>
			{#if error}
				Your browser could not open the camera
			{:else if shots.length === 0}
				Point the camera at the item
			{:else}
				{shots.length} {shots.length === 1 ? 'photo' : 'photos'} added
			{/if}
		</p>
	</div>
</dialog>
