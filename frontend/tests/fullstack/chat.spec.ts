import { test, expect } from '@playwright/test';

test('chat lists Homebox locations through LiteLLM function tools', async ({ page }) => {
	await page.goto('/chat');
	await page.getByLabel('Chat message input').fill('List my storage locations');
	await page.getByRole('button', { name: 'Send message' }).click();

	await expect(page.locator('.chat-bubble').last()).toContainText(
		'Your inventory includes Smoke storage.',
		{ timeout: 15_000 }
	);
	await expect(page.getByText('The LLM provider stream failed. Please try again.')).toHaveCount(0);
});
