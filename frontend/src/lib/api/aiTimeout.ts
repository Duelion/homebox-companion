/** Vision request deadline supplied by the public Companion configuration. */
let aiRequestTimeoutMs = 180_000;

export function setAiRequestTimeoutSeconds(seconds: number): void {
	if (!Number.isInteger(seconds) || seconds < 1 || seconds > 86_400) {
		throw new Error('Companion returned an invalid AI request timeout');
	}
	aiRequestTimeoutMs = seconds * 1000;
}

export function getAiRequestTimeoutMs(): number {
	return aiRequestTimeoutMs;
}
