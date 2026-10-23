import { test as base, expect, type Page } from '@playwright/test';
import { installApi, type MockApi } from './api';

type Fixtures = { api: MockApi; page: Page };

export const test = base.extend<Fixtures>({
	api: async ({ context }, use) => {
		const api = await installApi(context);
		const errors: string[] = [];
		context.on('page', (page) => page.on('pageerror', (error) => errors.push(error.message)));
		try {
			await use(api);
		} finally {
			api.releaseGates();
			expect.soft(api.unknown, 'Undeclared /api requests').toEqual([]);
			expect.soft(api.external, 'Unexpected external requests').toEqual([]);
			expect.soft(api.routeErrors, 'Mock API handler errors').toEqual([]);
			expect
				.soft(
					errors.filter((message) => !api.isAllowedPageError(message)),
					'Unhandled browser errors'
				)
				.toEqual([]);
		}
	},
	page: async ({ context, api }, use) => {
		const page = await context.newPage();
		try {
			await use(page);
		} finally {
			api.releaseGates();
			await page.close();
		}
	},
});

export { expect };
