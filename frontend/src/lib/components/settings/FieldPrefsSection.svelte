<script lang="ts">
	/**
	 * FieldPrefsSection - AI output configuration and field customizations.
	 */
	import { onDestroy } from 'svelte';
	import { settingsService, FIELD_META } from '$lib/workflows/settings.svelte';
	import Button from '$lib/components/Button.svelte';
	import FullscreenPanel from '$lib/components/FullscreenPanel.svelte';
	import CollapsibleSection from './CollapsibleSection.svelte';

	const service = settingsService;

	// Local UI states
	let promptFullscreen = $state(false);
	let showEnvExport = $state(false);
	let envCopied = $state(false);
	let envCopiedTimeoutId: number | null = null;

	async function copyEnvVars() {
		const envVars = service.generateEnvVars(service.fieldPrefs);
		try {
			await navigator.clipboard.writeText(envVars);
			envCopied = true;
			// Clear any existing timeout before setting a new one
			if (envCopiedTimeoutId !== null) {
				window.clearTimeout(envCopiedTimeoutId);
			}
			envCopiedTimeoutId = window.setTimeout(() => {
				envCopied = false;
				envCopiedTimeoutId = null;
			}, 2000);
		} catch {
			// Clipboard access denied - ignore silently
		}
	}

	onDestroy(() => {
		if (envCopiedTimeoutId !== null) {
			window.clearTimeout(envCopiedTimeoutId);
		}
	});
</script>

{#snippet icon()}
	<svg
		class="h-5 w-5 text-primary"
		fill="none"
		stroke="currentColor"
		viewBox="0 0 24 24"
		stroke-width="1.5"
	>
		<path
			d="M12 6V4m0 2a2 2 0 1 0 0 4m0-4a2 2 0 1 1 0 4m-6 8a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4"
		/>
	</svg>
{/snippet}

<CollapsibleSection title="Configure AI Output" {icon}>
	{#if service.showFieldPrefs && service.saveState === 'success'}
		<span
			class="inline-flex items-center gap-2 rounded-full bg-success/20 px-3 py-1.5 text-sm font-medium text-success"
		>
			<svg
				class="h-4 w-4"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="2.5"
			>
				<polyline points="20 6 9 17 4 12" />
			</svg>
			Saved
		</span>
	{/if}

	<p class="text-body-sm text-base-content/60">
		Customize how the AI generates item data. Leave fields empty to use default behavior.
	</p>

	<button
		type="button"
		class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
		onclick={() => service.toggleFieldPrefs()}
		disabled={service.isLoading.fieldPrefs}
	>
		{#if service.isLoading.fieldPrefs}
			<div
				class="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
			></div>
			<span>Loading...</span>
		{:else}
			<svg
				class="h-5 w-5 text-primary-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path
					d="M12 6V4m0 2a2 2 0 1 0 0 4m0-4a2 2 0 1 1 0 4m-6 8a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4"
				/>
			</svg>
			<span>Configure Fields</span>
			<svg
				class="ml-auto h-4 w-4 transition-transform {service.showFieldPrefs ? 'rotate-180' : ''}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<polyline points="6 9 12 15 18 9" />
			</svg>
		{/if}
	</button>

	{#if service.showFieldPrefs}
		{#if service.errors.fieldPrefs}
			<div class="rounded-xl border border-error-500/30 bg-error-500/10 p-4 text-sm text-error-500">
				{service.errors.fieldPrefs}
			</div>
		{/if}

		<!-- Output Language Setting -->
		<div class="space-y-3 rounded-xl border border-primary-500/20 bg-primary-600/10 p-4">
			<div class="flex items-center gap-2">
				<svg
					class="h-5 w-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"
					/>
				</svg>
				<label for="output_language" class="font-semibold text-neutral-100">Output Language</label>
			</div>
			<p class="text-xs text-neutral-400">
				Choose what language the AI should use for item names, descriptions, and notes.
			</p>
			<input
				type="text"
				id="output_language"
				value={service.fieldPrefs.output_language || ''}
				oninput={(e) => service.updateFieldPref('output_language', e.currentTarget.value)}
				placeholder={service.effectiveDefaults
					? service.effectiveDefaults.output_language
					: 'Loading...'}
				class="input"
			/>
			<div class="rounded-lg border border-warning-500/30 bg-warning-500/10 p-2">
				<p class="flex items-start gap-2 text-xs text-warning-500">
					<svg
						class="mt-0.5 h-4 w-4 flex-shrink-0"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path
							d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
						/>
					</svg>
					<span>
						<strong>Note:</strong> Field customization instructions below should still be written in English.
						Only the AI output will be in the configured language.
					</span>
				</p>
			</div>
		</div>

		<!-- Default Label Setting -->
		<div class="space-y-3 rounded-xl border border-primary-500/20 bg-primary-600/10 p-4">
			<div class="flex items-center gap-2">
				<svg
					class="h-5 w-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
					/>
				</svg>
				<label for="default_label" class="font-semibold text-neutral-100">Default Label</label>
			</div>
			<p class="text-xs text-neutral-400">
				Automatically tag all items created via Homebox Companion with this label.
			</p>
			<select
				id="default_label"
				value={service.fieldPrefs.default_label_id || ''}
				onchange={(e) => service.updateFieldPref('default_label_id', e.currentTarget.value)}
				class="input"
			>
				<option value="">No default label</option>
				{#each service.availableLabels as label (label.id)}
					<option value={label.id}>
						{label.name}{service.effectiveDefaults?.default_label_id === label.id
							? ' (env default)'
							: ''}
					</option>
				{/each}
			</select>
			<p class="text-xs text-neutral-500">
				Useful for identifying items added through this app in your Homebox inventory.
			</p>
		</div>

		<!-- Field Customizations - 2-column grid on wider screens -->
		<div class="grid gap-4 sm:grid-cols-2">
			{#each FIELD_META as field (field.key)}
				<div class="space-y-2 rounded-lg border border-neutral-700/50 bg-neutral-800/50 p-3">
					<label for={field.key} class="block text-sm font-semibold text-neutral-100">
						{field.label}
					</label>
					<div
						class="rounded border border-neutral-700/30 bg-neutral-950/50 px-2 py-1.5 text-xs text-neutral-400"
					>
						<span class="text-neutral-500">Default:</span>
						{service.effectiveDefaults?.[field.key] ?? 'Loading...'}
					</div>
					<input
						type="text"
						id={field.key}
						value={service.fieldPrefs[field.key] || ''}
						oninput={(e) => service.updateFieldPref(field.key, e.currentTarget.value)}
						placeholder="Leave empty for default..."
						class="input text-sm"
					/>
					<p class="line-clamp-2 text-xs text-neutral-500">
						Example: {field.example}
					</p>
				</div>
			{/each}
		</div>

		<div class="flex gap-3 pt-2">
			<Button
				variant="primary"
				onclick={() => service.saveFieldPrefs()}
				disabled={service.saveState === 'saving' || service.saveState === 'success'}
			>
				{#if service.saveState === 'saving'}
					<div
						class="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white"
					></div>
					<span>Saving...</span>
				{:else if service.saveState === 'success'}
					<div class="flex h-8 w-8 items-center justify-center rounded-full bg-success-500/20">
						<svg
							class="h-5 w-5 text-success-500"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="2.5"
						>
							<polyline points="20 6 9 17 4 12" />
						</svg>
					</div>
					<span>Saved!</span>
				{:else}
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M5 13l4 4L19 7"
						/>
					</svg>
					<span>Save</span>
				{/if}
			</Button>
			<Button
				variant="secondary"
				onclick={() => service.resetFieldPrefs()}
				disabled={service.saveState === 'saving' || service.saveState === 'success'}
			>
				<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
					/>
				</svg>
				<span>Reset</span>
			</Button>
		</div>
	{/if}

	<!-- Docker Persistence Warning & Export -->
	<div class="space-y-3 rounded-xl border border-warning-500/30 bg-warning-500/10 p-4">
		<div class="flex items-start gap-2">
			<svg
				class="mt-0.5 h-5 w-5 flex-shrink-0 text-warning-500"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
				/>
			</svg>
			<div>
				<p class="mb-1 text-sm font-medium text-warning-500">Docker users</p>
				<p class="text-xs text-neutral-400">
					Customizations are stored in a config file that may be lost when updating your container.
					Export as environment variables to persist settings.
				</p>
			</div>
		</div>

		<button
			type="button"
			class="flex w-full items-center justify-center gap-2 rounded-lg border border-warning-500/30 bg-warning-500/20 px-4 py-2.5 text-sm font-medium text-warning-500 transition-all hover:bg-warning-500/30"
			onclick={() => (showEnvExport = !showEnvExport)}
		>
			<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path
					d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
				/>
			</svg>
			<span>Export as Environment Variables</span>
		</button>
	</div>

	{#if showEnvExport}
		<div class="space-y-2">
			<div class="flex items-center justify-between">
				<span class="text-xs font-medium text-neutral-400">
					Add these to your docker-compose.yml or .env file
				</span>
				<button
					type="button"
					class="flex min-h-[36px] items-center gap-1 rounded-lg bg-primary-600/20 px-3 py-1.5 text-xs text-primary-400 transition-colors hover:bg-primary-600/30"
					onclick={copyEnvVars}
					aria-label="Copy environment variables"
				>
					{#if envCopied}
						<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<polyline points="20 6 9 17 4 12" />
						</svg>
						<span>Copied!</span>
					{:else}
						<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
							<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
						</svg>
						<span>Copy</span>
					{/if}
				</button>
			</div>
			<div class="overflow-hidden rounded-xl border border-neutral-700 bg-neutral-950">
				<pre
					class="overflow-x-auto whitespace-pre-wrap break-words p-4 font-mono text-xs text-neutral-400">{service.generateEnvVars(
						service.fieldPrefs
					)}</pre>
			</div>
		</div>
	{/if}

	<!-- Prompt Preview Section -->
	<div class="border-t border-neutral-800 pt-4">
		<button
			type="button"
			class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
			onclick={() => service.togglePromptPreview()}
			disabled={service.isLoading.promptPreview}
		>
			{#if service.isLoading.promptPreview}
				<div
					class="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
				></div>
				<span>Generating preview...</span>
			{:else}
				<svg
					class="h-5 w-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
					<path
						d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7Z"
					/>
				</svg>
				<span>Preview AI Prompt</span>
				<svg
					class="ml-auto h-4 w-4 transition-transform {service.showPromptPreview
						? 'rotate-180'
						: ''}"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<polyline points="6 9 12 15 18 9" />
				</svg>
			{/if}
		</button>

		{#if service.showPromptPreview && service.promptPreview}
			<div class="mt-3 space-y-2">
				<div class="flex items-center justify-between">
					<span class="text-xs font-medium text-neutral-400">System Prompt Preview</span>
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => (promptFullscreen = true)}
						title="Expand fullscreen"
						aria-label="View prompt fullscreen"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
						</svg>
					</button>
				</div>
				<div class="overflow-hidden rounded-xl border border-neutral-700 bg-neutral-950">
					<pre
						class="max-h-80 overflow-x-auto overflow-y-auto whitespace-pre-wrap break-words p-4 font-mono text-xs text-neutral-400">{service.promptPreview}</pre>
				</div>
				<p class="text-xs text-neutral-500">
					This is what the AI will see when analyzing your images. Labels shown are examples; actual
					labels from your Homebox instance will be used.
				</p>
			</div>
		{/if}
	</div>
</CollapsibleSection>

<!-- Fullscreen Prompt Preview Modal -->
<FullscreenPanel
	bind:open={promptFullscreen}
	title="AI System Prompt"
	subtitle="This is what the AI sees when analyzing your images"
	onclose={() => (promptFullscreen = false)}
>
	{#snippet icon()}
		<svg
			class="h-5 w-5 text-primary-400"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
			<path
				d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7Z"
			/>
		</svg>
	{/snippet}

	<pre
		class="whitespace-pre-wrap break-words font-mono text-sm leading-relaxed text-neutral-400">{service.promptPreview}</pre>
</FullscreenPanel>
