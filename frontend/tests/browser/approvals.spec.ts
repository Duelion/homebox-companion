import { expect, test } from './fixtures/test';
import { json, sse, type MockApi } from './fixtures/api';
import type { Page } from '@playwright/test';

const proposedCreate = (id: string, itemName: string) => ({
	id,
	tool: 'create_item',
	params: { name: itemName, location_id: 'loc-1', quantity: 1 },
	display_info: { item_name: itemName, location: 'Storage', action_type: 'create' as const },
	expires_at: null,
});

async function sendProposedCreate(
	page: Page,
	api: MockApi,
	approval: ReturnType<typeof proposedCreate>
) {
	api.on('POST', '/api/chat/messages', () =>
		sse([
			{ event: 'text', data: { content: `I can add ${approval.params.name}.` } },
			{ event: 'approval_required', data: approval },
			{ event: 'done', data: {} },
		])
	);

	await page.goto('/chat');
	await page.getByLabel('Chat message input').fill(`Add ${approval.params.name}`);
	await page.getByRole('button', { name: 'Send message' }).click();
	const approvalButton = page.getByRole('button', { name: '1 action requires approval' });
	await approvalButton.focus();
	await approvalButton.press('Enter');
	await expect(page.getByRole('heading', { name: '1 Action Require Approval' })).toBeVisible();
}

test('approving a proposed item creates it once', async ({ page, api }) => {
	const approval = proposedCreate('approval-desk-lamp', 'Desk Lamp');
	const createdItems: string[] = [];

	api.on('POST', `/api/chat/approve/${approval.id}`, () => {
		createdItems.push(approval.params.name);
		return json({ success: true, confirmation: 'Desk Lamp added' });
	});

	await sendProposedCreate(page, api, approval);
	await page.getByRole('button', { name: 'Approve', exact: true }).click();

	await expect(page.getByText('Desk Lamp added')).toBeVisible();
	expect(createdItems).toEqual(['Desk Lamp']);
	expect(
		api.requests.filter(
			(request) => new URL(request.url()).pathname === `/api/chat/approve/${approval.id}`
		)
	).toHaveLength(1);
});

test('rejecting a proposed item leaves it uncreated', async ({ page, api }) => {
	const approval = proposedCreate('approval-backup-battery', 'Backup Battery');
	const createdItems: string[] = [];
	const rejectedItems: string[] = [];

	api.on('POST', `/api/chat/approve/${approval.id}`, () => {
		createdItems.push(approval.params.name);
		return json({ success: true });
	});
	api.on('POST', `/api/chat/reject/${approval.id}`, () => {
		rejectedItems.push(approval.params.name);
		return json({ success: true, message: 'Action rejected' });
	});

	await sendProposedCreate(page, api, approval);
	await page.getByRole('button', { name: 'Reject', exact: true }).click();

	await expect(
		page.getByRole('paragraph').filter({ hasText: '\u2298 create_item: Backup Battery' })
	).toBeVisible();
	expect(rejectedItems).toEqual(['Backup Battery']);
	expect(createdItems).toEqual([]);
	expect(
		api.requests.filter(
			(request) => new URL(request.url()).pathname === `/api/chat/reject/${approval.id}`
		)
	).toHaveLength(1);
});

for (const selected of ['loc-1', '']) {
	test(`physical location override approval submits edited selector ${selected || 'blank as null'}`, async ({
		page,
		api,
	}) => {
		const approval = {
			id: 'override-approval',
			tool: 'update_item',
			params: { item_id: 'camera', location_override_id: 'original-room' },
			display_info: { item_name: 'Camera', action_type: 'update' },
			expires_at: null,
		};
		let submitted: unknown;
		api.on('POST', '/api/chat/messages', () =>
			sse([
				{ event: 'approval_required', data: approval },
				{ event: 'done', data: {} },
			])
		);
		api.on('POST', '/api/chat/approve/override-approval', (request) => {
			submitted = request.postDataJSON();
			return json({ success: true, confirmation: 'Camera updated' });
		});
		await page.goto('/chat');
		await page.getByLabel('Chat message input').fill('Change camera physical location');
		await page.getByRole('button', { name: 'Send message' }).click();
		const approvalButton = page.getByRole('button', { name: '1 action requires approval' });
		await approvalButton.focus();
		await approvalButton.press('Enter');
		await page.getByRole('button', { name: 'Edit', exact: true }).click();
		await page.getByLabel('Physical location override', { exact: true }).selectOption(selected);
		await expect(
			page.getByText('Keeps the parent item; changes this item’s physical location.')
		).toBeVisible();
		await page.getByRole('button', { name: 'Approve with your changes', exact: true }).click();
		await expect(page.getByText('Camera updated')).toBeVisible();
		expect(submitted).toEqual({ parameters: { location_override_id: selected || null } });
	});
}

test('override approval preserves proposal while locations load and can retry a failure', async ({
	page,
	api,
}) => {
	const gate = api.gate();
	let attempts = 0;
	api.on('GET', '/api/locations/tree', async () => {
		attempts++;
		if (attempts === 1) {
			await gate.promise;
			return json({ detail: 'Unavailable' }, 503);
		}
		return json([{ id: 'loc-1', name: 'Storage', children: [] }]);
	});
	api.on('POST', '/api/chat/messages', () =>
		sse([
			{
				event: 'approval_required',
				data: {
					id: 'loading-override',
					tool: 'update_item',
					params: { item_id: 'camera', location_override_id: 'original-room' },
					display_info: { item_name: 'Camera', action_type: 'update' },
					expires_at: null,
				},
			},
			{ event: 'done', data: {} },
		])
	);
	await page.goto('/chat');
	await page.getByLabel('Chat message input').fill('Change camera physical location');
	await page.getByRole('button', { name: 'Send message' }).click();
	const approvalButton = page.getByRole('button', { name: '1 action requires approval' });
	await approvalButton.focus();
	await approvalButton.press('Enter');
	await page.getByRole('button', { name: 'Edit', exact: true }).click();
	const selector = page.getByLabel('Physical location override', { exact: true });
	await expect(page.getByRole('status').filter({ hasText: 'Loading locations' })).toBeVisible();
	await expect(selector).toHaveValue('original-room');
	gate.release();
	await expect(
		page.getByRole('alert').filter({ hasText: 'Could not load locations.' })
	).toBeVisible();
	await expect(selector).toHaveValue('original-room');
	await page.getByRole('button', { name: 'Retry loading locations' }).click();
	await selector.selectOption('loc-1');
	await expect(selector).toHaveValue('loc-1');
	await expect(page.getByText('Could not load locations.')).toHaveCount(0);
	expect(attempts).toBe(2);
});
