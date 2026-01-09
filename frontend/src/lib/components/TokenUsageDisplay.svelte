<script lang="ts">
	/**
	 * TokenUsageDisplay - Shows AI token usage statistics.
	 *
	 * Displays prompt/completion/total token counts from the last analysis
	 * when the show_token_usage setting is enabled.
	 */
	import type { TokenUsage } from '$lib/types';

	interface Props {
		usage: TokenUsage | null;
	}

	let { usage }: Props = $props();

	// Format large numbers with commas
	function formatNumber(n: number): string {
		return n.toLocaleString();
	}
</script>

{#if usage}
	<div class="flex items-center gap-3 rounded-lg border border-info-500/20 bg-info-500/5 px-3 py-2 text-xs">
		<svg class="h-4 w-4 shrink-0 text-info-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
			<path d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
		</svg>
		<div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-neutral-300">
			<span>
				<span class="text-neutral-400">Prompt:</span>
				<span class="font-mono text-info-300">{formatNumber(usage.prompt_tokens)}</span>
			</span>
			<span>
				<span class="text-neutral-400">Completion:</span>
				<span class="font-mono text-info-300">{formatNumber(usage.completion_tokens)}</span>
			</span>
			<span>
				<span class="text-neutral-400">Total:</span>
				<span class="font-mono font-medium text-info-200">{formatNumber(usage.total_tokens)}</span>
			</span>
			<span class="text-neutral-500">({usage.provider})</span>
		</div>
	</div>
{/if}
