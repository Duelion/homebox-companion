import { type Page, type Request } from '@playwright/test';
import { installApi, json, sse } from './api';
import type { MockApi } from './api';
export async function mockApi(
	page: Page,
	options: {
		mode?: 'legacy' | 'api_key';
		connectionStatus?: () => number;
		requests?: Request[];
		chatStatus?: number;
		locationTree?: (request: Request) => Promise<unknown>;
		refreshStatus?: number;
		assistantResponse?: string;
	} = {}
): Promise<MockApi> {
	const api = await installApi(page.context());
	api.setAuthMode(options.mode ?? 'api_key');
	if (options.requests) {
		page.on('request', (request) => {
			if (new URL(request.url()).pathname.startsWith('/api/')) options.requests?.push(request);
		});
	}
	if (options.connectionStatus) {
		api.on('GET', '/api/homebox/connection', () => {
			const status = options.connectionStatus!();
			return status === 200
				? json({
						connected: true,
						context_id: 'deployment:user',
						user_id: 'user-1',
						default_group_id: 'g1',
					})
				: json(
						status === 502
							? {
									detail: 'The configured Homebox API key was rejected.',
									code: 'HOMEBOX_API_KEY_REJECTED',
								}
							: { detail: 'Homebox is unavailable', code: 'HOMEBOX_UNAVAILABLE' },
						status
					);
		});
	}
	if (options.locationTree) {
		api.on('GET', '/api/locations/tree', async (request) =>
			json(await options.locationTree!(request))
		);
	}
	if (options.chatStatus && options.chatStatus !== 200) {
		api.on('GET', '/api/chat/status', () =>
			json(
				{
					detail: 'The configured Homebox API key was rejected.',
					code: 'HOMEBOX_API_KEY_REJECTED',
				},
				options.chatStatus
			)
		);
	}
	if (options.refreshStatus && options.refreshStatus !== 200) {
		api.on('POST', '/api/refresh', () =>
			json({ detail: 'Session expired' }, options.refreshStatus)
		);
	}
	if (options.assistantResponse) {
		api.on('POST', '/api/chat/messages', () =>
			sse([
				{ event: 'text', data: { content: options.assistantResponse } },
				{ event: 'done', data: {} },
			])
		);
	}
	return api;
}

export function lifecycleRequests(requests: Request[]): Request[] {
	return requests.filter((request) =>
		/\/api\/(login|refresh|logout)$/.test(new URL(request.url()).pathname)
	);
}
