<script lang="ts">
	/**
	 * LogViewer - Colorized log display with auto-scroll.
	 *
	 * Supports both backend logs (raw string) and frontend logs (LogEntry[]).
	 * Applies Loguru-compatible color styling to log levels.
	 */
	import type { LogEntry } from '$lib/utils/logger';
	import { colorizeBackendLogs, colorizeFrontendLogs } from '$lib/utils/logColors';

	type LogSource =
		| { type: 'backend'; logs: string }
		| { type: 'frontend'; entries: LogEntry[] }
		| { type: 'json'; data: unknown };

	interface Props {
		/** Log source - either backend string, frontend entries, or raw JSON */
		source: LogSource;
		/** Maximum height CSS class (default: max-h-64) */
		maxHeight?: string;
		/** Reference to the container element for external scroll control */
		containerRef?: HTMLPreElement | null;
	}

	let { source, maxHeight = 'max-h-64', containerRef = $bindable(null) }: Props = $props();

	// Generate colorized HTML based on source type
	const colorizedContent = $derived.by(() => {
		if (source.type === 'backend') {
			return colorizeBackendLogs(source.logs);
		} else if (source.type === 'frontend') {
			return colorizeFrontendLogs(source.entries);
		} else {
			// JSON mode - no colorization, just pretty print
			return null;
		}
	});

	// Auto-scroll to bottom when content changes
	$effect(() => {
		if (containerRef && (colorizedContent || source.type === 'json')) {
			requestAnimationFrame(() => {
				if (containerRef) {
					containerRef.scrollTop = containerRef.scrollHeight;
				}
			});
		}
	});
</script>

<div class="overflow-hidden rounded-lg border border-neutral-700 bg-neutral-950">
	{#if source.type === 'json'}
		<pre
			bind:this={containerRef}
			class="overflow-x-auto overflow-y-auto whitespace-pre-wrap break-all p-3 font-mono text-xs text-neutral-400 {maxHeight}">{JSON.stringify(
				source.data,
				null,
				2
			)}</pre>
	{:else}
		<!-- eslint-disable svelte/no-at-html-tags -- Colorized log output with escaped content -->
		<pre
			bind:this={containerRef}
			class="overflow-x-auto overflow-y-auto whitespace-pre-wrap break-all p-3 font-mono text-xs text-neutral-400 {maxHeight}">{@html colorizedContent}</pre>
		<!-- eslint-enable svelte/no-at-html-tags -->
	{/if}
</div>




