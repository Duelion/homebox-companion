<script lang="ts">
	/**
	 * FieldPrefsSection - AI output configuration and field customizations.
	 * Organized into three collapsible sections:
	 *   1. General Settings (Output Language, Default Tag, Naming Examples)
	 *   2. Default Fields (per-field AI instructions with individual reset)
	 *   3. Custom Fields (user-defined Homebox fields)
	 */

	import {
		SlidersHorizontal,
		Check,
		Languages,
		TriangleAlert,
		Tag,
		ChevronDown,
		RotateCcw,
		Eye,
		Maximize2,
		Plus,
		Trash2,
		Layers,
		Pencil,
		Settings2,
		FileText,
	} from 'lucide-svelte';
	import { settingsService, FIELD_META } from '$lib/workflows/settings.svelte';

	import Button from '$lib/components/Button.svelte';
	import FullscreenPanel from '$lib/components/FullscreenPanel.svelte';

	const service = settingsService;

	// Local UI states
	let promptFullscreen = $state(false);
	let editingFieldIndex = $state<number | null>(null);

	// Derived: count of overridden default fields
	const overriddenFieldCount = $derived(
		FIELD_META.filter((f) => service.fieldPrefs[f.key] !== null).length
	);

	// Derived: count of overridden general settings
	const overriddenGeneralCount = $derived(
		[
			service.fieldPrefs.output_language,
			service.fieldPrefs.default_tag_id,
			service.fieldPrefs.naming_examples,
		].filter((v) => v !== null).length
	);
</script>

<section class="card space-y-4">
	<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
		<SlidersHorizontal class="text-primary-400" size={20} strokeWidth={1.5} />
		Configure AI Output
	</h2>

	<p class="text-body-sm text-neutral-400">
		Customize how the AI generates item data. Leave fields empty to use default behavior.
	</p>

	{#if service.isLoading.fieldPrefs}
		<div class="flex items-center gap-2 px-4 py-3 text-neutral-400">
			<div
				class="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
			></div>
			<span>Loading preferences...</span>
		</div>
	{:else}
		{#if service.errors.fieldPrefs}
			<div class="rounded-lg border border-error-500/30 bg-error-500/10 p-3 text-sm text-error-500">
				{service.errors.fieldPrefs}
			</div>
		{/if}

		<!-- ================================================================= -->
		<!-- GENERAL SETTINGS (Output Language, Default Tag, Naming Examples)   -->
		<!-- ================================================================= -->
		<div class="border-t border-neutral-800 pt-4">
			<button
				type="button"
				class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
				onclick={() => service.toggleGeneralSettings()}
			>
				<Settings2 class="text-primary-400" size={20} strokeWidth={1.5} />
				<span>General Settings</span>
				{#if overriddenGeneralCount > 0}
					<span class="rounded-full bg-primary-600/30 px-2 py-0.5 text-xs text-primary-400">
						{overriddenGeneralCount}
					</span>
				{/if}
				<ChevronDown
					class="ml-auto transition-transform {service.showGeneralSettings ? 'rotate-180' : ''}"
					size={16}
				/>
			</button>

			{#if service.showGeneralSettings}
				<div class="mt-3 space-y-4">
					<!-- Output Language -->
					<div class="space-y-3 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-3">
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2">
								<Languages class="text-primary-400" size={20} strokeWidth={1.5} />
								<label for="output_language" class="font-semibold text-neutral-100"
									>Output Language</label
								>
							</div>
							{#if service.fieldPrefs.output_language}
								<button
									type="button"
									class="btn-icon-touch text-neutral-400 hover:text-warning-400"
									title="Reset to default"
									onclick={() => service.resetSingleFieldPref('output_language')}
								>
									<RotateCcw size={14} strokeWidth={2} />
								</button>
							{/if}
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
									<strong>Note:</strong> Field customization instructions below should still be written
									in English. Only the AI output will be in the configured language.
								</span>
							</p>
						</div>
					</div>

					<!-- Default Tag -->
					<div class="space-y-3 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-3">
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2">
								<Tag class="text-primary-400" size={20} strokeWidth={1.5} />
								<label for="default_tag" class="font-semibold text-neutral-100">Default Tag</label>
							</div>
							{#if service.fieldPrefs.default_tag_id}
								<button
									type="button"
									class="btn-icon-touch text-neutral-400 hover:text-warning-400"
									title="Reset to default"
									onclick={() => service.resetSingleFieldPref('default_tag_id')}
								>
									<RotateCcw size={14} strokeWidth={2} />
								</button>
							{/if}
						</div>
						<p class="text-xs text-neutral-400">
							Automatically tag all items created via Homebox Companion with this tag.
						</p>
						<select
							id="default_tag"
							value={service.fieldPrefs.default_tag_id || ''}
							onchange={(e) => service.updateFieldPref('default_tag_id', e.currentTarget.value)}
							class="input"
						>
							<option value="">No default tag</option>
							{#each service.availableTags as tag (tag.id)}
								<option value={tag.id}>
									{tag.name}{service.effectiveDefaults?.default_tag_id === tag.id
										? ' (env default)'
										: ''}
								</option>
							{/each}
						</select>
						<p class="text-xs text-neutral-500">
							Useful for identifying items added through this app in your Homebox inventory.
						</p>
					</div>

					<!-- Naming Examples -->
					<div class="space-y-3 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-3">
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2">
								<FileText class="text-primary-400" size={20} strokeWidth={1.5} />
								<label for="naming_examples" class="font-semibold text-neutral-100"
									>Naming Examples</label
								>
							</div>
							{#if service.fieldPrefs.naming_examples}
								<button
									type="button"
									class="btn-icon-touch text-neutral-400 hover:text-warning-400"
									title="Reset to default"
									onclick={() => service.resetSingleFieldPref('naming_examples')}
								>
									<RotateCcw size={14} strokeWidth={2} />
								</button>
							{/if}
						</div>
						<p class="text-xs text-neutral-400">
							Comma-separated examples that show the AI how to format item names.
						</p>
						<textarea
							id="naming_examples"
							value={service.fieldPrefs.naming_examples || ''}
							oninput={(e) => service.updateFieldPref('naming_examples', e.currentTarget.value)}
							placeholder={service.effectiveDefaults?.naming_examples || 'No default'}
							rows="2"
							class="input resize-none text-sm"
						></textarea>
					</div>
				</div>
			{/if}
		</div>

		<!-- ================================================================= -->
		<!-- DEFAULT FIELDS (per-field AI instructions)                         -->
		<!-- ================================================================= -->
		<div class="border-t border-neutral-800 pt-4">
			<button
				type="button"
				class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
				onclick={() => service.toggleDefaultFields()}
			>
				<SlidersHorizontal class="text-primary-400" size={20} strokeWidth={1.5} />
				<span>Default Fields</span>
				{#if overriddenFieldCount > 0}
					<span class="rounded-full bg-primary-600/30 px-2 py-0.5 text-xs text-primary-400">
						{overriddenFieldCount}
					</span>
				{/if}
				<ChevronDown
					class="ml-auto transition-transform {service.showDefaultFields ? 'rotate-180' : ''}"
					size={16}
				/>
			</button>

			{#if service.showDefaultFields}
				<div class="mt-3 grid gap-4 sm:grid-cols-2">
					{#each FIELD_META as field (field.key)}
						<div class="space-y-2 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-3">
							<div class="flex items-center justify-between">
								<label for={field.key} class="block text-sm font-semibold text-neutral-100">
									{field.label}
								</label>
								{#if service.fieldPrefs[field.key]}
									<button
										type="button"
										class="btn-icon-touch text-neutral-400 hover:text-warning-400"
										title="Reset to default"
										onclick={() => service.resetSingleFieldPref(field.key)}
									>
										<RotateCcw size={14} strokeWidth={2} />
									</button>
								{/if}
							</div>
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
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- ================================================================= -->
		<!-- CUSTOM FIELDS                                                      -->
		<!-- ================================================================= -->
		<div class="border-t border-neutral-800 pt-4">
			<button
				type="button"
				class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
				onclick={() => service.toggleCustomFields()}
			>
				<Layers class="text-primary-400" size={20} strokeWidth={1.5} />
				<span>Custom Fields</span>
				<ChevronDown
					class="ml-auto transition-transform {service.showCustomFields ? 'rotate-180' : ''}"
					size={16}
				/>
			</button>

			{#if service.showCustomFields}
				<div class="mt-3 space-y-3">
					<p class="text-xs text-neutral-400">
						Define custom Homebox fields that the AI will populate during detection. Each field
						needs a name (as shown in Homebox) and an AI instruction.
					</p>

					{#if service.customFieldDefs.length > 0}
						<div class="grid gap-4 sm:grid-cols-2">
							{#each service.customFieldDefs as field, i (i)}
								{#if editingFieldIndex === i}
									<!-- Edit mode: inline name + instruction inputs -->
									<div
										class="space-y-2 rounded-xl border border-primary-500/40 bg-neutral-800/30 p-3"
									>
										<div class="flex items-center justify-between">
											<span class="text-xs font-medium text-primary-400">Editing</span>
											<div class="flex items-center gap-1">
												<button
													type="button"
													class="btn-icon-touch text-success-400 hover:text-success-300"
													title="Done editing"
													onclick={() => (editingFieldIndex = null)}
												>
													<Check size={14} strokeWidth={2} />
												</button>
												<button
													type="button"
													class="btn-icon-touch text-error-400 hover:text-error-300"
													title="Remove field"
													onclick={() => {
														service.removeCustomField(i);
														editingFieldIndex = null;
													}}
												>
													<Trash2 size={14} strokeWidth={1.5} />
												</button>
											</div>
										</div>
										<input
											type="text"
											value={field.name}
											oninput={(e) =>
												service.updateCustomFieldProp(i, 'name', e.currentTarget.value)}
											placeholder="Field name (e.g. Storage Location)"
											class="input text-sm"
										/>
										<textarea
											value={field.ai_instruction}
											oninput={(e) =>
												service.updateCustomFieldProp(i, 'ai_instruction', e.currentTarget.value)}
											placeholder="AI instruction (e.g. Where this item should be stored)"
											rows="3"
											class="input resize-none text-sm"
										></textarea>
									</div>
								{:else}
									<!-- Display mode: matches Default Fields card pattern -->
									<div
										class="space-y-2 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-3"
									>
										<div class="flex items-center justify-between">
											<label
												for="custom-field-{i}"
												class="block text-sm font-semibold text-neutral-100"
											>
												{field.name || 'Untitled Field'}
											</label>
											<div class="flex items-center gap-1">
												<button
													type="button"
													class="btn-icon-touch text-neutral-400 hover:text-primary-400"
													title="Edit field"
													onclick={() => (editingFieldIndex = i)}
												>
													<Pencil size={14} strokeWidth={2} />
												</button>
												<button
													type="button"
													class="btn-icon-touch hover:text-error-400 text-neutral-400"
													title="Remove field"
													onclick={() => {
														service.removeCustomField(i);
														if (editingFieldIndex !== null && i < editingFieldIndex) {
															editingFieldIndex--;
														}
													}}
												>
													<Trash2 size={14} strokeWidth={1.5} />
												</button>
											</div>
										</div>
										<textarea
											id="custom-field-{i}"
											value={field.ai_instruction}
											oninput={(e) =>
												service.updateCustomFieldProp(i, 'ai_instruction', e.currentTarget.value)}
											placeholder="AI instruction for this field"
											rows="1"
											class="input resize-none text-sm transition-all duration-200"
											onfocus={(e) => {
												e.currentTarget.rows = 3;
											}}
											onblur={(e) => {
												e.currentTarget.rows = 1;
											}}
										></textarea>
									</div>
								{/if}
							{/each}
						</div>
					{/if}

					<Button
						variant="ghost"
						size="sm"
						onclick={() => {
							service.addCustomField();
							editingFieldIndex = service.customFieldDefs.length - 1;
						}}
					>
						<Plus size={16} strokeWidth={2} />
						Add Field
					</Button>
				</div>
			{/if}
		</div>

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
						This is what the AI will see when analyzing your images. Tags shown are examples; actual
						tags from your Homebox instance will be used.
					</p>
				</div>
			{/if}
		</div>

		<!-- ================================================================= -->
		<!-- SHARED SAVE BUTTON (persists all settings)                         -->
		<!-- ================================================================= -->
		<div class="border-t border-neutral-800 pt-4">
			<Button
				variant="primary"
				full
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
		</div>
	{/if}
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
