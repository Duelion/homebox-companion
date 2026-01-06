<script lang="ts">
	/**
	 * AIProviderSection - Configure AI provider for vision and chat.
	 *
	 * Allows users to select and configure their AI provider:
	 * - Ollama (local)
	 * - OpenAI
	 * - Anthropic (Claude)
	 * - LiteLLM (cloud fallback)
	 */
	import { settingsService } from '$lib/workflows/settings.svelte';
	import {
		OLLAMA_VISION_MODELS,
		OPENAI_MODELS,
		ANTHROPIC_MODELS,
		type AIConfigInput,
	} from '$lib/api/aiConfig';
	import Button from '$lib/components/Button.svelte';

	const service = settingsService;

	// Local form state for editing
	let editingConfig = $state<AIConfigInput | null>(null);

	// Initialize form state when config loads
	$effect(() => {
		if (service.aiConfig && !editingConfig) {
			editingConfig = {
				active_provider: service.aiConfig.active_provider,
				fallback_to_cloud: service.aiConfig.fallback_to_cloud,
				fallback_provider: service.aiConfig.fallback_provider,
				ollama: { ...service.aiConfig.ollama },
				openai: {
					enabled: service.aiConfig.openai.enabled,
					api_key: null, // Don't populate masked keys
					model: service.aiConfig.openai.model,
					max_tokens: service.aiConfig.openai.max_tokens,
				},
				anthropic: {
					enabled: service.aiConfig.anthropic.enabled,
					api_key: null, // Don't populate masked keys
					model: service.aiConfig.anthropic.model,
					max_tokens: service.aiConfig.anthropic.max_tokens,
				},
				litellm: { ...service.aiConfig.litellm },
			};
		}
	});

	// Sync editingConfig when aiConfig changes (after save)
	$effect(() => {
		if (service.aiConfig && service.aiConfigSaveState === 'success' && editingConfig) {
			editingConfig = {
				active_provider: service.aiConfig.active_provider,
				fallback_to_cloud: service.aiConfig.fallback_to_cloud,
				fallback_provider: service.aiConfig.fallback_provider,
				ollama: { ...service.aiConfig.ollama },
				openai: {
					enabled: service.aiConfig.openai.enabled,
					api_key: null,
					model: service.aiConfig.openai.model,
					max_tokens: service.aiConfig.openai.max_tokens,
				},
				anthropic: {
					enabled: service.aiConfig.anthropic.enabled,
					api_key: null,
					model: service.aiConfig.anthropic.model,
					max_tokens: service.aiConfig.anthropic.max_tokens,
				},
				litellm: { ...service.aiConfig.litellm },
			};
		}
	});

	async function handleSave() {
		console.log('[AI_SECTION] handleSave called');
		if (!editingConfig) {
			console.log('[AI_SECTION] No editingConfig, returning');
			return;
		}
		console.log('[AI_SECTION] Calling saveAIConfig...');
		try {
			await service.saveAIConfig(editingConfig);
			console.log('[AI_SECTION] saveAIConfig completed');
		} catch (error) {
			console.error('[AI_SECTION] saveAIConfig failed:', error);
		}
	}

	async function handleTestConnection(provider: string) {
		if (!editingConfig) return;

		const config: Record<string, unknown> = {};
		if (provider === 'ollama') {
			config.url = editingConfig.ollama.url;
			config.model = editingConfig.ollama.model;
		} else if (provider === 'openai') {
			// Only use the editing key - don't fall back to masked display key
			// If no key entered, the test will prompt user to enter one
			config.api_key = editingConfig.openai.api_key;
			config.model = editingConfig.openai.model;
		} else if (provider === 'anthropic') {
			// Only use the editing key - don't fall back to masked display key
			// If no key entered, the test will prompt user to enter one
			config.api_key = editingConfig.anthropic.api_key;
			config.model = editingConfig.anthropic.model;
		} else if (provider === 'litellm') {
			config.model = editingConfig.litellm.model;
		}

		await service.testAIProviderConnection(provider, config);
	}

	function selectProvider(providerId: string) {
		if (!editingConfig) return;
		editingConfig.active_provider = providerId;

		// Enable the selected provider
		if (providerId === 'ollama') editingConfig.ollama.enabled = true;
		else if (providerId === 'openai') editingConfig.openai.enabled = true;
		else if (providerId === 'anthropic') editingConfig.anthropic.enabled = true;
		else if (providerId === 'litellm') editingConfig.litellm.enabled = true;
	}

	// Get provider display info
	function getProviderIcon(providerId: string): string {
		switch (providerId) {
			case 'ollama':
				return 'M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z';
			case 'openai':
				return 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z';
			case 'anthropic':
				return 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z';
			case 'litellm':
				return 'M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z';
			default:
				return 'M13 10V3L4 14h7v7l9-11h-7z';
		}
	}
</script>

<section class="card space-y-4">
	<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
		<svg
			class="h-5 w-5 text-primary-400"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<path
				d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
			/>
		</svg>
		AI Provider
	</h2>

	<!-- Toggle Button -->
	<button
		type="button"
		class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
		onclick={() => service.toggleAIConfig()}
	>
		<svg
			class="h-5 w-5 text-primary-400"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
			<path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
		</svg>
		<span>Configure AI Provider</span>
		{#if service.isLoading.aiConfig}
			<div
				class="ml-auto h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
			></div>
		{:else}
			<svg
				class="ml-auto h-4 w-4 transition-transform {service.showAIConfig ? 'rotate-180' : ''}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<polyline points="6 9 12 15 18 9" />
			</svg>
		{/if}
	</button>

	{#if service.errors.aiConfig}
		<div class="rounded-xl border border-error-500/30 bg-error-500/10 p-3">
			<p class="text-sm text-error-500">{service.errors.aiConfig}</p>
		</div>
	{/if}

	{#if service.showAIConfig && editingConfig}
		<div class="space-y-4 border-t border-neutral-800 pt-4">
			<!-- Provider Selection -->
			<div class="space-y-3">
				<span class="block text-sm font-medium text-neutral-300">Active Provider</span>
				<div class="grid grid-cols-2 gap-2">
					{#each service.aiConfig?.providers || [] as provider}
						<button
							type="button"
							class="flex items-center gap-2 rounded-xl border px-3 py-2 text-left transition-all {editingConfig.active_provider ===
							provider.id
								? 'border-primary-500 bg-primary-500/10 text-primary-400'
								: 'border-neutral-700 bg-neutral-800/50 text-neutral-400 hover:bg-neutral-700'}"
							onclick={() => selectProvider(provider.id)}
						>
							<svg class="h-4 w-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
								<path d={getProviderIcon(provider.id)} />
							</svg>
							<div class="min-w-0 flex-1">
								<p class="truncate text-sm font-medium">{provider.name}</p>
							</div>
							{#if provider.configured}
								<svg class="h-4 w-4 flex-shrink-0 text-success-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
									<polyline points="20 6 9 17 4 12" />
								</svg>
							{/if}
						</button>
					{/each}
				</div>
			</div>

			<!-- Provider-specific settings -->
			{#if editingConfig.active_provider === 'ollama'}
				<div class="space-y-3 rounded-xl border border-neutral-700 bg-neutral-800/30 p-4">
					<h3 class="text-sm font-medium text-neutral-200">Ollama Settings</h3>

					<div class="space-y-2">
						<label for="ollama-url" class="block text-xs text-neutral-400">Server URL</label>
						<input
							id="ollama-url"
							type="text"
							bind:value={editingConfig.ollama.url}
							class="input w-full"
							placeholder="http://localhost:11434"
						/>
					</div>

					<div class="space-y-2">
						<label for="ollama-model" class="block text-xs text-neutral-400">Model</label>
						<select
							id="ollama-model"
							bind:value={editingConfig.ollama.model}
							class="input w-full"
						>
							{#each OLLAMA_VISION_MODELS as model}
								<option value={model.id}>{model.name}</option>
							{/each}
						</select>
					</div>

					<Button
						variant="secondary"
						size="sm"
						onclick={() => handleTestConnection('ollama')}
						disabled={service.aiConfigTestingProvider === 'ollama'}
					>
						{#if service.aiConfigTestingProvider === 'ollama'}
							<div class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></div>
							Testing...
						{:else}
							Test Connection
						{/if}
					</Button>
				</div>
			{:else if editingConfig.active_provider === 'openai'}
				<div class="space-y-3 rounded-xl border border-neutral-700 bg-neutral-800/30 p-4">
					<h3 class="text-sm font-medium text-neutral-200">OpenAI Settings</h3>

					<div class="space-y-2">
						<label for="openai-key" class="block text-xs text-neutral-400">
							API Key {service.aiConfig?.openai.has_api_key ? '(configured)' : ''}
						</label>
						<input
							id="openai-key"
							type="password"
							bind:value={editingConfig.openai.api_key}
							class="input w-full"
							placeholder={service.aiConfig?.openai.has_api_key ? '••••••••' : 'sk-...'}
						/>
					</div>

					<div class="space-y-2">
						<label for="openai-model" class="block text-xs text-neutral-400">Model</label>
						<select
							id="openai-model"
							bind:value={editingConfig.openai.model}
							class="input w-full"
						>
							{#each OPENAI_MODELS as model}
								<option value={model.id}>{model.name}</option>
							{/each}
						</select>
					</div>

					<Button
						variant="secondary"
						size="sm"
						onclick={() => handleTestConnection('openai')}
						disabled={service.aiConfigTestingProvider === 'openai'}
					>
						{#if service.aiConfigTestingProvider === 'openai'}
							<div class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></div>
							Testing...
						{:else}
							Test Connection
						{/if}
					</Button>
				</div>
			{:else if editingConfig.active_provider === 'anthropic'}
				<div class="space-y-3 rounded-xl border border-neutral-700 bg-neutral-800/30 p-4">
					<h3 class="text-sm font-medium text-neutral-200">Anthropic Settings</h3>

					<div class="space-y-2">
						<label for="anthropic-key" class="block text-xs text-neutral-400">
							API Key {service.aiConfig?.anthropic.has_api_key ? '(configured)' : ''}
						</label>
						<input
							id="anthropic-key"
							type="password"
							bind:value={editingConfig.anthropic.api_key}
							class="input w-full"
							placeholder={service.aiConfig?.anthropic.has_api_key ? '••••••••' : 'sk-ant-...'}
						/>
					</div>

					<div class="space-y-2">
						<label for="anthropic-model" class="block text-xs text-neutral-400">Model</label>
						<select
							id="anthropic-model"
							bind:value={editingConfig.anthropic.model}
							class="input w-full"
						>
							{#each ANTHROPIC_MODELS as model}
								<option value={model.id}>{model.name}</option>
							{/each}
						</select>
					</div>

					<Button
						variant="secondary"
						size="sm"
						onclick={() => handleTestConnection('anthropic')}
						disabled={service.aiConfigTestingProvider === 'anthropic'}
					>
						{#if service.aiConfigTestingProvider === 'anthropic'}
							<div class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></div>
							Testing...
						{:else}
							Test Connection
						{/if}
					</Button>
				</div>
			{:else if editingConfig.active_provider === 'litellm'}
				<div class="space-y-3 rounded-xl border border-neutral-700 bg-neutral-800/30 p-4">
					<h3 class="text-sm font-medium text-neutral-200">Cloud (LiteLLM) Settings</h3>
					<p class="text-xs text-neutral-400">
						Uses environment variables for API keys. Configure HBC_LLM_API_KEY in your deployment.
					</p>

					<div class="space-y-2">
						<label for="litellm-model" class="block text-xs text-neutral-400">Model</label>
						<input
							id="litellm-model"
							type="text"
							bind:value={editingConfig.litellm.model}
							class="input w-full"
							placeholder="gpt-4o"
						/>
					</div>
				</div>
			{/if}

			<!-- Test Result -->
			{#if service.aiConfigTestResult}
				<div
					class="rounded-xl border p-3 {service.aiConfigTestResult.success
						? 'border-success-500/30 bg-success-500/10'
						: 'border-error-500/30 bg-error-500/10'}"
				>
					<div class="flex items-start gap-2">
						{#if service.aiConfigTestResult.success}
							<svg class="mt-0.5 h-4 w-4 flex-shrink-0 text-success-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
								<polyline points="20 6 9 17 4 12" />
							</svg>
						{:else}
							<svg class="mt-0.5 h-4 w-4 flex-shrink-0 text-error-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
								<line x1="18" y1="6" x2="6" y2="18" />
								<line x1="6" y1="6" x2="18" y2="18" />
							</svg>
						{/if}
						<div class="min-w-0 flex-1">
							<p class="text-sm {service.aiConfigTestResult.success ? 'text-success-500' : 'text-error-500'}">
								{service.aiConfigTestResult.message}
							</p>
						</div>
						<button
							type="button"
							class="text-neutral-500 hover:text-neutral-300"
							onclick={() => service.clearAIConfigTestResult()}
							aria-label="Dismiss test result"
						>
							<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
								<line x1="18" y1="6" x2="6" y2="18" />
								<line x1="6" y1="6" x2="18" y2="18" />
							</svg>
						</button>
					</div>
				</div>
			{/if}

			<!-- Save/Reset Buttons -->
			<div class="flex items-center gap-3 border-t border-neutral-800 pt-4">
				<Button
					variant="primary"
					onclick={handleSave}
					disabled={service.aiConfigSaveState === 'saving'}
				>
					{#if service.aiConfigSaveState === 'saving'}
						<div class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></div>
						Saving...
					{:else if service.aiConfigSaveState === 'success'}
						<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
							<polyline points="20 6 9 17 4 12" />
						</svg>
						Saved!
					{:else}
						Save Configuration
					{/if}
				</Button>

				<Button
					variant="ghost"
					onclick={() => service.resetAIConfigToDefaults()}
					disabled={service.aiConfigSaveState === 'saving'}
				>
					Reset to Defaults
				</Button>
			</div>
		</div>
	{/if}
</section>
