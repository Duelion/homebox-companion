import type { Page } from '@playwright/test';

export async function seedLegacySession(
	page: Page,
	token = 'valid-legacy-token',
	groupId?: string
) {
	await page.addInitScript(
		({ token, groupId }) => {
			localStorage.setItem('hbc_token', token);
			localStorage.setItem('hbc_token_expires', new Date(Date.now() + 3_600_000).toISOString());
			if (groupId) localStorage.setItem('hbc_group_id', groupId);
		},
		{ token, groupId }
	);
}
