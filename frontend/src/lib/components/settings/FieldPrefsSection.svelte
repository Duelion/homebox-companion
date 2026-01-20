<script lang="ts">
	/**
	 * FieldPrefsSection - AI output configuration and field customizations.
	 */
	import { onDestroy } from 'svelte';
	import {
		SlidersHorizontal,
		Check,
		Languages,
		TriangleAlert,
		Tag,
		ChevronDown,
		RotateCcw,
		Copy,
		Eye,
		Maximize2,
	} from 'lucide-svelte';
	import { settingsService, FIELD_META } from '$lib/workflows/settings.svelte';
	import Button from '$lib/components/Button.svelte';
	import FullscreenPanel from '$lib/components/FullscreenPanel.svelte';

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

<section class="card space-y-4">
	<div class="flex items-center justify-between">
		<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
			<SlidersHorizontal class="text-primary-400" size={20} strokeWidth={1.5} />
			Configure AI Output
		</h2>
		{#if service.showFieldPrefs && service.saveState === 'success'}
			<span
				class="inline-flex items-center gap-2 rounded-full bg-success-500/20 px-3 py-1.5 text-sm font-medium text-success-500"
			>
				<Check size={16} strokeWidth={2.5} />
				Saved
			</span>
		{/if}
	</div>

	<p class="text-body-sm text-neutral-400">
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
			<SlidersHorizontal class="text-primary-400" size={20} strokeWidth={1.5} />
			<span>Configure Fields</span>
			<ChevronDown
				class="ml-auto transition-transform {service.showFieldPrefs ? 'rotate-180' : ''}"
				size={16}
			/>
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
				<Languages class="text-primary-400" size={20} strokeWidth={1.5} />
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
					<TriangleAlert class="mt-0.5 flex-shrink-0" size={16} strokeWidth={1.5} />
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
				<Tag class="text-primary-400" size={20} strokeWidth={1.5} />
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
					<textarea
						id={field.key}
						value={service.fieldPrefs[field.key] || ''}
						oninput={(e) => service.updateFieldPref(field.key, e.currentTarget.value)}
						placeholder={service.effectiveDefaults?.[field.key] || 'No default'}
						rows="1"
						class="input resize-none text-sm transition-all duration-200"
						onfocus={(e) => {
							e.currentTarget.rows = 3;
						}}
						onblur={(e) => {
							e.currentTarget.rows = 1;
						}}
					></textarea>
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
						<Check class="text-success-500" size={20} strokeWidth={2.5} />
					</div>
					<span>Saved!</span>
				{:else}
					<Check size={16} strokeWidth={2} />
					<span>Save</span>
				{/if}
			</Button>
			<Button
				variant="secondary"
				onclick={() => service.resetFieldPrefs()}
				disabled={service.saveState === 'saving' || service.saveState === 'success'}
			>
				<RotateCcw size={16} strokeWidth={2} />
				<span>Reset</span>
			</Button>
		</div>
	{/if}

	<!-- Docker Persistence Warning & Export -->
	<div class="space-y-3 rounded-xl border border-warning-500/30 bg-warning-500/10 p-4">
		<div class="flex items-start gap-2">
			<TriangleAlert class="mt-0.5 flex-shrink-0 text-warning-500" size={20} strokeWidth={1.5} />
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
			<Copy size={16} strokeWidth={1.5} />
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
						<Check size={16} />
						<span>Copied!</span>
					{:else}
						<Copy size={16} />
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
				<Eye size={20} strokeWidth={1.5} />
				<span>Preview AI Prompt</span>
				<ChevronDown
					class="ml-auto transition-transform {service.showPromptPreview ? 'rotate-180' : ''}"
					size={16}
				/>
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
						<Maximize2 size={20} strokeWidth={1.5} />
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
</section>

<!-- Fullscreen Prompt Preview Modal -->
<FullscreenPanel
	bind:open={promptFullscreen}
	title="AI System Prompt"
	subtitle="This is what the AI sees when analyzing your images"
	onclose={() => (promptFullscreen = false)}
>
	{#snippet icon()}
		<Eye class="text-primary-400" size={20} strokeWidth={1.5} />
	{/snippet}

	<pre
		class="whitespace-pre-wrap break-words font-mono text-sm leading-relaxed text-neutral-400">{service.promptPreview}</pre>
</FullscreenPanel>
