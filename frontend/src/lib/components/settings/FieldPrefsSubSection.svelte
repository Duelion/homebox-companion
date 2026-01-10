<script lang="ts">
	/**
	 * FieldPrefsSubSection - AI output configuration as a sub-section.
	 *
	 * Configures how AI generates item data: output language, default labels,
	 * and field-specific instructions.
	 */
	import { onDestroy } from 'svelte';
	import { settingsService, FIELD_META } from '$lib/workflows/settings.svelte';
	import Button from '$lib/components/Button.svelte';
	import FullscreenPanel from '$lib/components/FullscreenPanel.svelte';

	const service = settingsService;

	// Local UI states
	let isExpanded = $state(false);
	let promptFullscreen = $state(false);
	let showEnvExport = $state(false);
	let envCopied = $state(false);
	let envCopiedTimeoutId: number | null = null;

	async function copyEnvVars() {
		const envVars = service.generateEnvVars(service.fieldPrefs);
		try {
			await navigator.clipboard.writeText(envVars);
			envCopied = true;
			if (envCopiedTimeoutId !== null) {
				window.clearTimeout(envCopiedTimeoutId);
			}
			envCopiedTimeoutId = window.setTimeout(() => {
				envCopied = false;
				envCopiedTimeoutId = null;
			}, 2000);
		} catch {
			// Clipboard access denied
		}
	}

	onDestroy(() => {
		if (envCopiedTimeoutId !== null) {
			window.clearTimeout(envCopiedTimeoutId);
		}
	});
</script>

<!-- Sub-section header -->
<button
	type="button"
	class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
	onclick={() => (isExpanded = !isExpanded)}
>
	<svg class="h-5 w-5 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
		<path d="M12 6V4m0 2a2 2 0 1 0 0 4m0-4a2 2 0 1 1 0 4m-6 8a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4" />
	</svg>
	<span>AI Output</span>
	{#if service.fieldPrefs.output_language}
		<span class="rounded-full bg-primary-500/20 px-2 py-0.5 text-xs text-primary-400">
			{service.fieldPrefs.output_language}
		</span>
	{/if}
	{#if service.saveState === 'success'}
		<span class="rounded-full bg-success-500/20 px-2 py-0.5 text-xs text-success-500">Saved</span>
	{/if}
	<svg class="ml-auto h-4 w-4 transition-transform {isExpanded ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
		<polyline points="6 9 12 15 18 9" />
	</svg>
</button>

{#if isExpanded}
	<div class="space-y-4 rounded-xl border border-neutral-700 bg-neutral-800/30 p-4">
		<p class="text-xs text-neutral-400">
			Customize how the AI generates item data. Leave fields empty to use default behavior.
		</p>

		<!-- Load fields button -->
		{#if !service.showFieldPrefs}
			<Button variant="secondary" size="sm" onclick={() => service.toggleFieldPrefs()} disabled={service.isLoading.fieldPrefs}>
				{#if service.isLoading.fieldPrefs}
					<div class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></div>
					Loading...
				{:else}
					Load Field Configuration
				{/if}
			</Button>
		{/if}

		{#if service.showFieldPrefs}
			{#if service.errors.fieldPrefs}
				<div class="rounded-lg border border-error-500/30 bg-error-500/10 p-3 text-xs text-error-500">
					{service.errors.fieldPrefs}
				</div>
			{/if}

			<!-- Output Language -->
			<div class="space-y-2 border-t border-neutral-700 pt-3">
				<label for="sub-output-language" class="block text-sm font-medium text-neutral-200">Output Language</label>
				<p class="text-xs text-neutral-400">Language for AI-generated names, descriptions, and notes.</p>
				<input
					type="text"
					id="sub-output-language"
					value={service.fieldPrefs.output_language || ''}
					oninput={(e) => service.updateFieldPref('output_language', e.currentTarget.value)}
					placeholder={service.effectiveDefaults?.output_language ?? 'English'}
					class="input w-full"
				/>
			</div>

			<!-- Default Label -->
			<div class="space-y-2 border-t border-neutral-700 pt-3">
				<label for="sub-default-label" class="block text-sm font-medium text-neutral-200">Default Label</label>
				<p class="text-xs text-neutral-400">Auto-tag all items created via Companion.</p>
				<select
					id="sub-default-label"
					value={service.fieldPrefs.default_label_id || ''}
					onchange={(e) => service.updateFieldPref('default_label_id', e.currentTarget.value)}
					class="input w-full"
				>
					<option value="">No default label</option>
					{#each service.availableLabels as label (label.id)}
						<option value={label.id}>{label.name}</option>
					{/each}
				</select>
			</div>

			<!-- Field Customizations -->
			<div class="space-y-3 border-t border-neutral-700 pt-3">
				<h4 class="text-sm font-medium text-neutral-200">Field Instructions</h4>
				<div class="grid gap-3 sm:grid-cols-2">
					{#each FIELD_META as field (field.key)}
						<div class="space-y-1 rounded-lg border border-neutral-700/50 bg-neutral-800/50 p-2">
							<label for="sub-{field.key}" class="block text-xs font-medium text-neutral-300">
								{field.label}
							</label>
							<input
								type="text"
								id="sub-{field.key}"
								value={service.fieldPrefs[field.key] || ''}
								oninput={(e) => service.updateFieldPref(field.key, e.currentTarget.value)}
								placeholder={service.effectiveDefaults?.[field.key] ?? 'Default'}
								class="input w-full text-xs"
							/>
						</div>
					{/each}
				</div>
			</div>

			<!-- Save/Reset buttons -->
			<div class="flex gap-2 border-t border-neutral-700 pt-3">
				<Button
					variant="primary"
					size="sm"
					onclick={() => service.saveFieldPrefs()}
					disabled={service.saveState === 'saving' || service.saveState === 'success'}
				>
					{#if service.saveState === 'saving'}
						Saving...
					{:else if service.saveState === 'success'}
						Saved!
					{:else}
						Save
					{/if}
				</Button>
				<Button
					variant="secondary"
					size="sm"
					onclick={() => service.resetFieldPrefs()}
					disabled={service.saveState === 'saving'}
				>
					Reset
				</Button>
			</div>

			<!-- Env Export -->
			<div class="border-t border-neutral-700 pt-3">
				<button
					type="button"
					class="flex w-full items-center gap-2 rounded-lg border border-warning-500/30 bg-warning-500/10 px-3 py-2 text-xs text-warning-500 transition-all hover:bg-warning-500/20"
					onclick={() => (showEnvExport = !showEnvExport)}
				>
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
						<path d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
					</svg>
					Export as Environment Variables (Docker)
					<svg class="ml-auto h-3 w-3 transition-transform {showEnvExport ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<polyline points="6 9 12 15 18 9" />
					</svg>
				</button>

				{#if showEnvExport}
					<div class="mt-2 space-y-2">
						<div class="flex items-center justify-between">
							<span class="text-xs text-neutral-500">Add to docker-compose.yml or .env</span>
							<button
								type="button"
								class="rounded bg-primary-600/20 px-2 py-1 text-xs text-primary-400 hover:bg-primary-600/30"
								onclick={copyEnvVars}
							>
								{envCopied ? 'Copied!' : 'Copy'}
							</button>
						</div>
						<pre class="overflow-x-auto rounded-lg bg-neutral-950 p-2 font-mono text-xs text-neutral-400">{service.generateEnvVars(service.fieldPrefs)}</pre>
					</div>
				{/if}
			</div>

			<!-- Prompt Preview -->
			<div class="border-t border-neutral-700 pt-3">
				<button
					type="button"
					class="flex w-full items-center gap-2 text-xs text-neutral-400 hover:text-neutral-200"
					onclick={() => service.togglePromptPreview()}
					disabled={service.isLoading.promptPreview}
				>
					{#if service.isLoading.promptPreview}
						<div class="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent"></div>
					{:else}
						<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
							<path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
							<path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7Z" />
						</svg>
					{/if}
					<span>Preview AI Prompt</span>
					<svg class="ml-auto h-3 w-3 transition-transform {service.showPromptPreview ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<polyline points="6 9 12 15 18 9" />
					</svg>
				</button>

				{#if service.showPromptPreview && service.promptPreview}
					<div class="mt-2 space-y-2">
						<div class="flex items-center justify-between">
							<span class="text-xs text-neutral-500">System prompt preview</span>
							<button
								type="button"
								class="text-xs text-primary-400 hover:text-primary-300"
								onclick={() => (promptFullscreen = true)}
							>
								Fullscreen
							</button>
						</div>
						<pre class="max-h-40 overflow-auto rounded-lg bg-neutral-950 p-2 font-mono text-xs text-neutral-400">{service.promptPreview}</pre>
					</div>
				{/if}
			</div>
		{/if}
	</div>
{/if}

<!-- Fullscreen Prompt Preview -->
<FullscreenPanel
	bind:open={promptFullscreen}
	title="AI System Prompt"
	subtitle="This is what the AI sees when analyzing images"
	onclose={() => (promptFullscreen = false)}
>
	{#snippet icon()}
		<svg class="h-5 w-5 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
			<path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
			<path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7Z" />
		</svg>
	{/snippet}

	<pre class="whitespace-pre-wrap break-words font-mono text-sm leading-relaxed text-neutral-400">{service.promptPreview}</pre>
</FullscreenPanel>
