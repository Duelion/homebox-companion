import type { BrowserContext, Request, Route } from '@playwright/test';
import { config, fieldPreferences, groups, location, type AuthMode } from './data';
import { fontCss } from './fonts';

export type Reply = { status: number; contentType: string; body: string };
export type Handler = (request: Request) => Reply | Promise<Reply>;
type Entry = { method: string; path: string | RegExp; handler: Handler };

export const json = (body: unknown, status = 200): Reply => ({
	status,
	contentType: 'application/json',
	body: JSON.stringify(body),
});

export const sse = (events: Array<{ event: string; data: unknown }>): Reply => ({
	status: 200,
	contentType: 'text/event-stream',
	body: events
		.map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
		.join(''),
});

export interface RequestGate {
	promise: Promise<void>;
	release(): void;
}

export class MockApi {
	readonly requests: Request[] = [];
	readonly unknown: string[] = [];
	readonly external: string[] = [];
	readonly routeErrors: string[] = [];
	private entries: Entry[] = [];
	private gates: RequestGate[] = [];
	private allowedPageErrors: RegExp[] = [];
	private mode: AuthMode = 'api_key';

	constructor(private context: BrowserContext) {
		this.installBaseline();
	}

	setAuthMode(mode: AuthMode): void {
		this.mode = mode;
	}

	allowPageError(pattern: RegExp): void {
		this.allowedPageErrors.push(pattern);
	}

	isAllowedPageError(message: string): boolean {
		return this.allowedPageErrors.some((pattern) => pattern.test(message));
	}

	on(method: string, path: string | RegExp, handler: Handler): void {
		this.entries.push({ method: method.toUpperCase(), path, handler });
	}

	gate(): RequestGate {
		let release!: () => void;
		const promise = new Promise<void>((resolve) => (release = resolve));
		const gate = { promise, release };
		this.gates.push(gate);
		return gate;
	}

	releaseGates(): void {
		for (const gate of this.gates) gate.release();
		this.gates = [];
	}

	async install(): Promise<void> {
		await this.context.route('**/*', async (route) => this.dispatch(route));
	}

	private async dispatch(route: Route): Promise<void> {
		const request = route.request();
		const url = new URL(request.url());
		const path = url.pathname;
		if (url.origin !== 'http://127.0.0.1:4173') {
			// app.html imports Google Fonts. Local, pinned fonts keep rendering deterministic.
			if (url.hostname === 'fonts.googleapis.com' && path.startsWith('/css')) {
				await route.fulfill({ status: 200, contentType: 'text/css', body: fontCss });
				return;
			}
			this.external.push(`${request.method()} ${request.url()}`);
			await route.abort();
			return;
		}
		if (!path.startsWith('/api/')) {
			await route.continue();
			return;
		}
		this.requests.push(request);
		const entry = [...this.entries]
			.reverse()
			.find(
				({ method, path: match }) =>
					method === request.method() &&
					(typeof match === 'string' ? match === path : match.test(path))
			);
		if (!entry) {
			this.unknown.push(`${request.method()} ${path}${url.search}`);
			await route.abort();
			return;
		}
		try {
			await route.fulfill(await entry.handler(request));
		} catch (error) {
			this.routeErrors.push(`${request.method()} ${path}: ${String(error)}`);
			await route.abort().catch(() => {});
		}
	}

	private installBaseline(): void {
		this.on('GET', '/api/config', () => json(config(this.mode)));
		this.on('GET', '/api/homebox/connection', () =>
			json({
				connected: true,
				context_id: 'deployment:user',
				user_id: 'user-1',
				default_group_id: 'g1',
			})
		);
		this.on('GET', '/api/groups', () => json(groups()));
		this.on('GET', '/api/version', () =>
			json({ version: 'test', latest_version: null, update_available: false })
		);
		this.on('GET', '/api/locations/tree', () => json([location()]));
		this.on('GET', '/api/locations/loc-1', () => json(location()));
		this.on('GET', '/api/locations', () => json([]));
		this.on('GET', '/api/tags', () => json([]));
		this.on('GET', '/api/items', () => json([]));
		this.on('GET', '/api/settings/field-preferences', () => json(fieldPreferences()));
		this.on('GET', '/api/settings/effective-defaults', () =>
			json({
				...Object.fromEntries(Object.keys(fieldPreferences()).map((key) => [key, ''])),
				default_tag_id: null,
			})
		);
		this.on('GET', '/api/settings/custom-fields', () => json([]));
		this.on('GET', '/api/llm/profiles', () => json({ profiles: [] }));
		this.on('GET', '/api/chat/health', () =>
			json({ status: 'ok', chat_enabled: true, max_history: 20, approval_timeout_seconds: 300 })
		);
		this.on('GET', '/api/chat/status', () => json({ session_id: 's1', message_count: 0 }));
		this.on('GET', '/api/chat/pending', () => json({ approvals: [] }));
		this.on('POST', '/api/chat/messages', () =>
			sse([
				{ event: 'text', data: { content: 'Hello' } },
				{ event: 'done', data: {} },
			])
		);
		this.on('POST', '/api/login', () =>
			json({
				token: 'fresh-token',
				expires_at: new Date(Date.now() + 3_600_000).toISOString(),
				message: 'ok',
			})
		);
		this.on('POST', '/api/refresh', () =>
			json({
				token: 'refreshed-token',
				expires_at: new Date(Date.now() + 3_600_000).toISOString(),
				message: 'ok',
			})
		);
	}
}

const contextApis = new WeakMap<BrowserContext, MockApi>();

export async function installApi(context: BrowserContext): Promise<MockApi> {
	const existing = contextApis.get(context);
	if (existing) return existing;
	const api = new MockApi(context);
	await api.install();
	contextApis.set(context, api);
	return api;
}
