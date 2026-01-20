<script lang="ts">
	import { slide } from 'svelte/transition';
	import { ChevronDown, RefreshCcw } from 'lucide-svelte';
	import Button from './Button.svelte';
	import AnalysisProgressBar from './AnalysisProgressBar.svelte';

	interface Props {
		expanded: boolean;
		loading: boolean;
		onToggle: () => void;
		onCorrect: (prompt: string) => void;
	}

	let { expanded, loading, onToggle, onCorrect }: Props = $props();

	let correctionPrompt = $state('');

	function handleCorrect() {
		if (correctionPrompt.trim()) {
			onCorrect(correctionPrompt);
			correctionPrompt = '';
		}
	}
</script>

<div class="border-t border-neutral-700 pt-4">
	<button
		type="button"
		class="flex w-full items-center gap-2 text-sm text-neutral-400 hover:text-neutral-200"
		onclick={onToggle}
	>
		<ChevronDown class="transition-transform {expanded ? 'rotate-180' : ''}" size={16} />
		<span>AI Correction</span>
	</button>

	{#if expanded}
		<div class="mt-3 space-y-3" transition:slide={{ duration: 200 }}>
			{#if loading}
				<AnalysisProgressBar current={0} total={1} message="Correcting with AI..." />
			{:else}
				<p class="text-xs text-neutral-500">
					Tell the AI what's wrong and it will re-analyze the image
				</p>
				<textarea
					bind:value={correctionPrompt}
					placeholder="e.g., 'The brand is Sony, not Samsung' or 'This is a multimeter, not a voltmeter'"
					rows="2"
					class="input resize-none"
				></textarea>
				<Button
					variant="secondary"
					full
					onclick={handleCorrect}
					{loading}
					disabled={loading || !correctionPrompt.trim()}
				>
					<RefreshCcw size={16} strokeWidth={2} />
					<span>Correct with AI</span>
				</Button>
			{/if}
		</div>
	{/if}
</div>
