import { browser } from '$app/environment';
import { authStore, type HomeboxConnection } from '$lib/stores/auth.svelte';
import { collectionStore } from '$lib/stores/collection.svelte';
import { setDemoMode, type ConfigResponse } from '$lib/api/settings';
import { request } from '$lib/api/client';
import { initializeAuth } from './tokenRefresh';
import { setLogLevel } from '$lib/utils/logger';

let bootstrapPromise: Promise<void> | null = null;

async function discoverConfig(): Promise<ConfigResponse> {
	const response = await fetch('/api/config', { headers: { Accept: 'application/json' } });
	if (!response.ok) throw new Error(`Unable to load Companion configuration (${response.status})`);
	const config: unknown = await response.json();
	if (
		!config ||
		typeof config !== 'object' ||
		!('auth_mode' in config) ||
		(config.auth_mode !== 'legacy' && config.auth_mode !== 'api_key')
	) {
		throw new Error('Companion returned an invalid authentication configuration');
	}
	return config as ConfigResponse;
}

async function establishConnection(): Promise<void> {
	const connection = await request<HomeboxConnection>('/homebox/connection', {
		omitGroup: true,
	});
	if (!connection.connected || !connection.context_id || !connection.user_id) {
		throw new Error('Homebox returned an invalid connection response');
	}
	authStore.setConnection(connection, false);
	await collectionStore.fetchGroups(connection.default_group_id);
	authStore.markReady();
}

async function runBootstrap(): Promise<void> {
	if (!browser) return;
	try {
		const config = await discoverConfig();
		setLogLevel(config.log_level);
		setDemoMode(config.is_demo_mode, config.demo_mode_explicit);
		authStore.beginMode(config.auth_mode);

		if (config.auth_mode === 'legacy') {
			authStore.loadLegacyStorage();
			await initializeAuth();
			if (!authStore.token) {
				authStore.setSignedOut();
				return;
			}
		}

		await establishConnection();
	} catch (error) {
		authStore.setConnectionError(
			error instanceof Error ? error.message : 'Unable to connect to Homebox'
		);
	} finally {
		authStore.setInitialized(true);
	}
}

export function initializeApp(): Promise<void> {
	bootstrapPromise ??= runBootstrap();
	return bootstrapPromise;
}

export function getInitPromise(): Promise<void> {
	return bootstrapPromise ?? initializeApp();
}

export async function retryConnection(): Promise<void> {
	if (!authStore.mode) {
		bootstrapPromise = runBootstrap();
		await bootstrapPromise;
		return;
	}
	authStore.beginMode(authStore.mode);
	try {
		await establishConnection();
	} catch (error) {
		authStore.setConnectionError(
			error instanceof Error ? error.message : 'Unable to connect to Homebox'
		);
	}
}

export async function completeLegacyLogin(): Promise<void> {
	authStore.beginConnection();
	try {
		await establishConnection();
	} catch (error) {
		authStore.setConnectionError(
			error instanceof Error ? error.message : 'Unable to connect to Homebox'
		);
		throw error;
	}
}
