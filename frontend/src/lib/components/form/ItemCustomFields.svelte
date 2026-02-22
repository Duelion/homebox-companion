<script lang="ts">
	/**
	 * ItemCustomFields - Collapsible panel for user-defined custom fields
	 *
	 * Displays custom field values extracted by AI during detection.
	 * Only shown when custom fields are configured and have data.
	 * Follows the same pattern as ItemExtendedFields.
	 */
	import { slide } from 'svelte/transition';
	import { ChevronDown, Layers } from 'lucide-svelte';
	import type { FormSize } from './types';
	import { getInputClass, getLabelClass } from './types';

	interface Props {
		customFields: Record<string, string>;
		expanded: boolean;
		size?: FormSize;
		disabled?: boolean;
		idPrefix?: string;
		onToggle: () => void;
	}

	let {
		customFields = $bindable(),
		expanded,
		size = 'md',
		disabled = false,
		idPrefix = 'custom',
		onToggle,
	}: Props = $props();

	// Convert to entries for iteration
	const entries = $derived(Object.entries(customFields));
	const hasData = $derived(entries.some(([, v]) => v.trim().length > 0));

	function handleInput(key: string, value: string) {
		customFields = { ...customFields, [key]: value };
	}

	// Dynamic classes based on size
	const inputClass = $derived(getInputClass(size));
	const labelClass = $derived(getLabelClass(size));
	const spacing = $derived(size === 'sm' ? 'space-y-2.5' : 'space-y-4');
</script>

<div class="border-t border-neutral-700 pt-4">
	<button
		type="button"
		class="flex w-full items-center gap-2 text-sm text-neutral-400 hover:text-neutral-200"
		onclick={onToggle}
		aria-expanded={expanded}
	>
		<ChevronDown class="transition-transform {expanded ? 'rotate-180' : ''}" size={16} />
		<Layers size={14} strokeWidth={1.5} class="text-primary-400" />
		<span>Custom Fields</span>
		{#if hasData}
			<span class="rounded bg-primary-500/20 px-1.5 py-0.5 text-xs text-primary-300">Has data</span>
		{/if}
	</button>

	{#if expanded}
		<div class="mt-4 {spacing}" transition:slide={{ duration: 200 }}>
			{#each entries as [key, value] (key)}
				<div>
					<label for="{idPrefix}-cf-{key}" class={labelClass}>{key}</label>
					<input
						type="text"
						id="{idPrefix}-cf-{key}"
						{value}
						oninput={(e) => handleInput(key, e.currentTarget.value)}
						placeholder="AI-populated value"
						class={inputClass}
						{disabled}
					/>
				</div>
			{/each}
		</div>
	{/if}
</div>
