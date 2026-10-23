import { test, expect } from './fixtures/test';
import { json } from './fixtures/api';
import { mockApi } from './fixtures/auth-api';

for (const viewport of ['desktop', 'mobile'] as const) {
	test(`wrong credentials show a useful error and allow retry ${viewport === 'mobile' ? '@mobile' : ''}`, async ({
		page,
	}) => {
		const api = await mockApi(page, { mode: 'legacy' });
		let attempts = 0;
		api.on('POST', '/api/login', (request) => {
			attempts++;
			if (attempts === 1) {
				return json({ detail: 'Invalid email or password.', code: 'AUTH_FAILED' }, 401);
			}
			expect(request.postDataJSON()).toEqual({
				username: 'demo@example.com',
				password: 'correct-password',
			});
			return json({
				token: 'fresh-token',
				expires_at: new Date(Date.now() + 3_600_000).toISOString(),
				message: 'ok',
			});
		});
		await page.goto('/');
		await page.getByLabel('Email').fill('demo@example.com');
		await page.locator('#password').fill('wrong-password');
		await page.getByRole('button', { name: 'Sign In' }).click();
		await expect(page.getByText('Invalid email or password.', { exact: true })).toBeVisible();
		await expect(page.getByLabel('Email')).toHaveValue('demo@example.com');
		await page.locator('#password').fill('correct-password');
		await page.getByRole('button', { name: 'Sign In' }).click();
		await expect(page).toHaveURL(/\/location$/);
		await expect(page.getByRole('heading', { name: 'Select Location' })).toBeVisible();
		expect(attempts).toBe(2);
	});
}
