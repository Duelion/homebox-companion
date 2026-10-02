import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { type Page } from '@playwright/test';
import { expect, test } from './fixtures/test';
import { json, sse, type MockApi } from './fixtures/api';

async function openApproval(page: Page, api: MockApi) {
	api.on('POST', '/api/chat/messages', () =>
		sse([
			{ event: 'text', data: { content: 'I can add the lamp.' } },
			{
				event: 'approval_required',
				data: {
					id: 'lamp-approval',
					tool: 'create_item',
					params: { name: 'Desk Lamp', location_id: 'loc-1', quantity: 1 },
					display_info: {
						item_name: 'Desk Lamp',
						location: 'Storage',
						action_type: 'create',
					},
					expires_at: null,
				},
			},
			{ event: 'done', data: {} },
		])
	);
	await page.goto('/chat');
	await page.getByLabel('Chat message input').fill('Add a desk lamp');
	await page.getByRole('button', { name: 'Send message' }).click();
	const trigger = page.getByRole('button', { name: '1 action requires approval' });
	// The approval badge pulses continuously; activate it through the keyboard.
	await trigger.focus();
	await trigger.press('Enter');
	return { trigger, dialog: page.getByRole('dialog', { name: 'Actions Require Approval' }) };
}

test('approval dialog contains focus, makes the page inert, and restores its trigger', async ({
	page,
	api,
}) => {
	const { trigger, dialog } = await openApproval(page, api);
	const close = dialog.getByRole('button', { name: 'Close' });
	await expect(dialog).toBeVisible();
	await expect(close).toBeFocused();
	await page.keyboard.press('Shift+Tab');
	await expect(dialog.getByRole('button', { name: 'Approve All' })).toBeFocused();
	await page.keyboard.press('Tab');
	await expect(close).toBeFocused();
	await expect(
		page.evaluate(() => {
			const input = document.querySelector<HTMLInputElement>('[aria-label="Chat message input"]');
			input?.focus();
			return document.activeElement === input;
		})
	).resolves.toBe(false);
	await page.keyboard.press('Escape');
	await expect(dialog).not.toBeVisible();
	await expect(trigger).toBeFocused();
});

test('fullscreen log dialog contains focus and Escape closes only that dialog', async ({
	page,
	api,
}) => {
	api.on('GET', '/api/logs', () =>
		json({ logs: 'Started successfully', filename: 'server.log', total_lines: 1, truncated: false })
	);
	await page.goto('/settings');
	await page.getByRole('button', { name: 'View Logs' }).click();
	await page.getByRole('button', { name: 'Show Server Logs' }).click();
	const trigger = page.getByRole('button', { name: 'View fullscreen' }).first();
	await trigger.click();
	const dialog = page.getByRole('dialog', { name: 'Application Logs' });
	await expect(dialog).toBeVisible();
	await expect(dialog.getByRole('button', { name: 'Refresh' })).toBeFocused();
	await page.keyboard.press('Shift+Tab');
	await expect(dialog.getByRole('button', { name: 'Close' })).toBeFocused();
	await page.keyboard.press('Escape');
	await expect(dialog).not.toBeVisible();
	await expect(trigger).toBeFocused();
	await expect(page.getByRole('button', { name: 'View Logs' })).toBeVisible();
});

test('approval actions reflow within a narrow phone viewport @mobile', async ({ page, api }) => {
	await page.setViewportSize({ width: 320, height: 640 });
	const { dialog } = await openApproval(page, api);
	await expect(dialog).toBeVisible();
	await dialog.evaluate(async (element) => {
		await Promise.all(
			element.getAnimations({ subtree: true }).map((animation) => animation.finished)
		);
	});
	const controls = [
		dialog.getByRole('button', { name: 'Close' }),
		dialog.getByRole('button', { name: 'Reject All' }),
		dialog.getByRole('button', { name: 'Approve All' }),
	];
	for (const control of controls) {
		const bounds = await control.boundingBox();
		expect(bounds).not.toBeNull();
		expect(bounds!.width).toBeGreaterThanOrEqual(44);
		expect(bounds!.height).toBeGreaterThanOrEqual(44);
		expect(bounds!.x).toBeGreaterThanOrEqual(0);
		expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
	}
	const overflow = await dialog.evaluate((element) => element.scrollWidth - element.clientWidth);
	expect(overflow).toBeLessThanOrEqual(1);
});

test('warning action text meets contrast in normal, hover, active, and disabled states', async ({
	page,
	api,
}) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	const gate = api.gate();
	api.on('POST', '/api/chat/approve/lamp-approval', async () => {
		await gate.promise;
		return json({ success: true });
	});
	const { dialog } = await openApproval(page, api);
	const approve = dialog.getByRole('button', { name: 'Approve All' });
	async function contrast() {
		return approve.evaluate((button) => {
			const style = getComputedStyle(button);
			function luminance(color: string) {
				const channels = color
					.match(/[\d.]+/g)!
					.slice(0, 3)
					.map(Number)
					.map((channel) => {
						const value = channel / 255;
						return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
					});
				return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
			}
			const text = luminance(style.color);
			const background = luminance(style.backgroundColor);
			return (Math.max(text, background) + 0.05) / (Math.min(text, background) + 0.05);
		});
	}
	expect(await contrast()).toBeGreaterThanOrEqual(4.5);
	await approve.hover();
	expect(await contrast()).toBeGreaterThanOrEqual(4.5);
	await page.mouse.down();
	try {
		expect(await contrast()).toBeGreaterThanOrEqual(4.5);
	} finally {
		await page.mouse.up();
	}
	await expect(approve).toBeDisabled();
	expect(await contrast()).toBeGreaterThanOrEqual(4.5);
	gate.release();
	await expect(dialog).toBeHidden();
});

test('shared dialog action keeps nested Escape and focus restoration inside the parent', async ({
	page,
}) => {
	await page.goto('/location');
	// Exercise the actual action in a small DOM fixture without shipping a test route.
	const source = readFileSync('src/lib/actions/dialog.ts', 'utf8');
	const compiled = ts.transpileModule(source, {
		compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
	}).outputText;
	await page.addScriptTag({
		content: `(() => { const exports = {}; ${compiled}
 const trigger = document.createElement('button');
 trigger.textContent = 'Open test parent'; document.body.append(trigger);
 trigger.onclick = () => {
  const parent = document.createElement('dialog'); parent.setAttribute('aria-label', 'Test parent');
  const nested = document.createElement('button'); nested.textContent = 'Open test child'; parent.append(nested); document.body.append(parent);
  const parentAction = exports.modalDialog(parent);
  parent.oncancel = (event) => { event.preventDefault(); parentAction.destroy(); parent.remove(); };
  nested.onclick = () => {
   const child = document.createElement('dialog'); child.setAttribute('aria-label', 'Test child');
   const button = document.createElement('button'); button.textContent = 'Child control'; child.append(button); parent.append(child);
   const childAction = exports.modalDialog(child);
   child.oncancel = (event) => { event.preventDefault(); childAction.destroy(); child.remove(); };
  };
 };
 })();`,
	});
	const trigger = page.getByRole('button', { name: 'Open test parent' });
	await trigger.click();
	const parent = page.getByRole('dialog', { name: 'Test parent', exact: true });
	const nested = parent.getByRole('button', { name: 'Open test child' });
	await nested.click();
	const child = page.getByRole('dialog', { name: 'Test child', exact: true });
	await page.keyboard.press('Tab');
	await expect(child.getByRole('button', { name: 'Child control' })).toBeFocused();
	await page.keyboard.press('Escape');
	await expect(child).toBeHidden();
	await expect(parent).toBeVisible();
	await expect(nested).toBeFocused();
	await page.keyboard.press('Escape');
	await expect(parent).toBeHidden();
	await expect(trigger).toBeFocused();
});
