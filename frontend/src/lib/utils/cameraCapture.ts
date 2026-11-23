/**
 * How the "Camera" buttons take a photo.
 *
 * `<input type="file" capture>` opens the device's camera app on mobile browsers only.
 * Desktop browsers ignore the attribute and show an ordinary file chooser, so on those
 * the app shows its own camera view (CameraCapture.svelte) built on getUserMedia.
 */

interface NavigatorLike {
	userAgent: string;
	userAgentData?: { platform?: string };
	maxTouchPoints?: number;
	mediaDevices?: { getUserMedia?: unknown };
}

interface WindowLike {
	isSecureContext: boolean;
	navigator: NavigatorLike;
}

/** Whether the browser hands `<input capture>` to a camera app (Android, iOS, iPadOS). */
export function hasNativeCameraCapture(nav: NavigatorLike): boolean {
	const platform = nav.userAgentData?.platform;
	if (platform === 'Android' || platform === 'iOS') return true;
	if (/Android|iPhone|iPad|iPod/i.test(nav.userAgent)) return true;
	// iPadOS Safari identifies itself as a Mac; only the iPad has a touch screen.
	return /Macintosh/i.test(nav.userAgent) && (nav.maxTouchPoints ?? 0) > 1;
}

/** Whether a "Camera" button should open the in-page camera instead of the file input. */
export function shouldUseInPageCamera(win: WindowLike = window): boolean {
	return (
		!hasNativeCameraCapture(win.navigator) &&
		win.isSecureContext &&
		typeof win.navigator.mediaDevices?.getUserMedia === 'function'
	);
}

/** A message for a failed getUserMedia call, and a short code for support. */
export function describeCameraError(err: unknown): { message: string; code: string } {
	// Older browsers throw an OverconstrainedError that is not an Error.
	const named = err as { name?: unknown; message?: unknown } | null | undefined;
	const name = typeof named?.name === 'string' ? named.name : '';
	const code =
		name
			.replace(/Error$/, '')
			.toUpperCase()
			.slice(0, 10) || 'UNKNOWN';
	switch (name) {
		case 'NotAllowedError':
		case 'SecurityError':
			return { message: 'Camera permission denied. Check your browser settings.', code };
		case 'NotFoundError':
		case 'OverconstrainedError':
			return { message: 'No camera detected.', code };
		case 'NotReadableError':
		case 'AbortError':
			return { message: 'The camera is in use by another app, or could not be started.', code };
		default:
			return {
				message: `Camera error: ${(typeof named?.message === 'string' && named.message) || 'unknown error'}.`,
				code,
			};
	}
}

/** File name for a photo taken at `date`, e.g. `camera-20260115-093042-007.jpg`. */
export function cameraFileName(date: Date): string {
	const pad = (value: number, length = 2) => String(value).padStart(length, '0');
	return (
		`camera-${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
		`-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}` +
		`-${pad(date.getMilliseconds(), 3)}.jpg`
	);
}

/** Save the frame a playing video is showing as a JPEG file. */
export async function captureVideoFrame(video: HTMLVideoElement): Promise<File> {
	const { videoWidth: width, videoHeight: height } = video;
	if (!width || !height) throw new Error('The camera has not produced a picture yet.');
	const canvas = document.createElement('canvas');
	canvas.width = width;
	canvas.height = height;
	const context = canvas.getContext('2d');
	if (!context) throw new Error('Could not read the camera picture.');
	context.drawImage(video, 0, 0, width, height);
	const blob = await new Promise<Blob | null>((resolve) =>
		canvas.toBlob(resolve, 'image/jpeg', 0.92)
	);
	if (!blob) throw new Error('Could not read the camera picture.');
	return new File([blob], cameraFileName(new Date()), { type: 'image/jpeg' });
}
