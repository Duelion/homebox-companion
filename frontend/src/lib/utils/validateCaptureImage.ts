/** Validate image contents before capture state or preview URLs are created. */
export async function validateCaptureImage(file: File, maxSizeMb: number): Promise<File> {
	const maxBytes = maxSizeMb * 1024 * 1024;
	if (file.size > maxBytes) throw new Error(`Image is too large (max ${maxSizeMb}MB).`);
	if (file.size === 0) throw new Error('Image is empty. Choose another photo.');
	const bytes = new Uint8Array(await file.slice(0, 64).arrayBuffer());
	const ascii = (start: number, end: number) => String.fromCharCode(...bytes.slice(start, end));
	let mime: string;
	if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) mime = 'image/jpeg';
	else if (bytes[0] === 0x89 && ascii(1, 4) === 'PNG') mime = 'image/png';
	else if (ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP') mime = 'image/webp';
	else if (['GIF87a', 'GIF89a'].includes(ascii(0, 6))) mime = 'image/gif';
	else if (ascii(4, 8) === 'ftyp' && /^(heic|heix|hevc|hevx|mif1|msf1)$/.test(ascii(8, 12))) {
		try {
			const { default: heic2any } = await import('heic2any');
			const converted = await heic2any({ blob: file, toType: 'image/jpeg', quality: 0.9 });
			const blob = Array.isArray(converted) ? converted[0] : converted;
			return await validateCaptureImage(
				new File([blob], file.name.replace(/\.(heic|heif)$/i, '') + '.jpg', { type: 'image/jpeg' }),
				maxSizeMb
			);
		} catch {
			throw new Error('Unable to read this HEIC/HEIF photo. Try exporting it as JPEG.');
		}
	} else
		throw new Error(
			'Invalid or unsupported image. Choose a JPEG, PNG, WebP, GIF or HEIC/HEIF photo.'
		);
	const normalized = new File([file], file.name, { type: mime, lastModified: file.lastModified });
	try {
		const bitmap = await createImageBitmap(normalized);
		bitmap.close();
	} catch {
		throw new Error('Unable to read this image. Choose a valid photo.');
	}
	return normalized;
}
