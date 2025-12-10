/**
 * Retry utility with exponential backoff
 */

interface RetryOptions {
	maxAttempts?: number;
	baseDelay?: number;
	onRetry?: (attempt: number, error: Error) => void;
}

/**
 * Retry an async function with exponential backoff
 * @param fn - The async function to retry
 * @param options - Retry configuration
 * @returns The result of the function
 * @throws The last error if all retries are exhausted
 */
export async function withRetry<T>(
	fn: () => Promise<T>,
	options: RetryOptions = {}
): Promise<T> {
	const { maxAttempts = 3, baseDelay = 1000, onRetry } = options;

	let lastError: Error | undefined;

	for (let attempt = 1; attempt <= maxAttempts; attempt++) {
		try {
			return await fn();
		} catch (error) {
			lastError = error instanceof Error ? error : new Error(String(error));

			// Don't delay after the last attempt
			if (attempt < maxAttempts) {
				// Exponential backoff: 1s, 2s, 4s
				const delay = baseDelay * Math.pow(2, attempt - 1);

				if (onRetry) {
					onRetry(attempt, lastError);
				}

				await new Promise((resolve) => setTimeout(resolve, delay));
			}
		}
	}

	// All retries exhausted
	throw lastError || new Error('All retry attempts failed');
}

