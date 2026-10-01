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
