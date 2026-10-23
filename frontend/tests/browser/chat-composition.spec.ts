import { test, expect } from './fixtures/test';
import { mockApi } from './fixtures/auth-api';

test('IME confirmation keeps the chat draft until a subsequent Enter sends it', async ({
	page,
}) => {
	await mockApi(page);
	await page.goto('/chat');
	const input = page.getByLabel('Chat message input');
	await input.fill('こんにちは');
	await input.dispatchEvent('keydown', { key: 'Enter', code: 'Enter', isComposing: true });
	await expect(input).toHaveValue('こんにちは');
	await expect(page.locator('.chat-bubble')).toHaveCount(0);
	await input.press('Enter');
	await expect(page.getByText('Hello', { exact: true })).toBeVisible();
	await expect(page.getByText('こんにちは', { exact: true })).toBeVisible();
});
