<script lang="ts">
	import { slide } from 'svelte/transition';
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

<div class="border-t border-border pt-4">
	<button
		type="button"
		class="flex items-center gap-2 text-sm text-text-muted hover:text-text w-full"
		onclick={onToggle}
	>
		<svg
			class="w-4 h-4 transition-transform {expanded ? 'rotate-180' : ''}"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
		>
			<polyline points="6 9 12 15 18 9" />
		</svg>
		<span>AI Correction</span>
	</button>

	{#if expanded}
		<div class="mt-3 space-y-3" transition:slide={{ duration: 200 }}>
			{#if loading}
				<AnalysisProgressBar
					current={0}
					total={1}
					message="Correcting with AI..."
				/>
			{:else}
				<p class="text-xs text-text-dim">
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
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path d="M12 2a10 10 0 1 0 10 10H12V2z" />
						<path d="M12 2a10 10 0 0 1 10 10" />
					</svg>
					<span>Correct with AI</span>
				</Button>
			{/if}
		</div>
	{/if}
</div>





