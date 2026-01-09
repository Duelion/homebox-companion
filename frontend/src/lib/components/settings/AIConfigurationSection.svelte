<script lang="ts">
	/**
	 * AIConfigurationSection - Parent wrapper for all AI-related settings.
	 *
	 * Combines:
	 * - AI Provider settings
	 * - Behavior settings (duplicate detection)
	 * - Enrichment settings
	 *
	 * Each sub-section is collapsible within this parent section.
	 */
	import { settingsService } from '$lib/workflows/settings.svelte';
	import CollapsibleSection from './CollapsibleSection.svelte';
	import AIProviderSubSection from './AIProviderSubSection.svelte';
	import BehaviorSubSection from './BehaviorSubSection.svelte';
	import EnrichmentSubSection from './EnrichmentSubSection.svelte';
	import FieldPrefsSubSection from './FieldPrefsSubSection.svelte';

	const service = settingsService;

	// Get display name for current provider
	function getProviderDisplayName(providerId: string): string {
		switch (providerId) {
			case 'ollama':
				return 'Ollama';
			case 'openai':
				return 'OpenAI';
			case 'anthropic':
				return 'Anthropic';
			case 'litellm':
				return 'Cloud';
			default:
				return providerId;
		}
	}

	// Derived value showing current AI config summary
	const aiSummary = $derived.by(() => {
		if (!service.aiConfig) return 'Not configured';
		const provider = getProviderDisplayName(service.aiConfig.active_provider);
		const model = service.aiConfig[service.aiConfig.active_provider as keyof typeof service.aiConfig];
		if (typeof model === 'object' && model !== null && 'model' in model) {
			return `${provider} - ${model.model}`;
		}
		return provider;
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
			d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
		/>
	</svg>
{/snippet}

<CollapsibleSection title="AI Configuration" {icon}>
	<!-- Summary when collapsed -->
	<div class="flex items-center justify-between text-sm">
		<span class="text-base-content/60">Current:</span>
		<span class="font-mono text-base-content">{aiSummary}</span>
	</div>

	<!-- Sub-sections -->
	<div class="space-y-4 border-t border-base-content/10 pt-4">
		<!-- AI Provider -->
		<AIProviderSubSection />

		<!-- AI Output (field preferences) -->
		<FieldPrefsSubSection />

		<!-- Enrichment -->
		<EnrichmentSubSection />

		<!-- Behavior (duplicate detection, token usage) -->
		<BehaviorSubSection />
	</div>
</CollapsibleSection>
