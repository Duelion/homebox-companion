<script lang="ts">
	/**
	 * LogPanel - Reusable collapsible log viewer panel.
	 *
	 * Provides a consistent UI for all log sections:
	 * - Collapsible toggle with loading state
	 * - Action buttons (refresh, export, download, clear, fullscreen)
	 * - Error/empty state handling
	 * - Fullscreen modal support
	 */
	import type { Snippet } from 'svelte';
	import { RefreshCw, Download, Share, Trash2, Maximize2, ChevronDown } from 'lucide-svelte';
	import FullscreenPanel from '$lib/components/FullscreenPanel.svelte';

	interface Props {
		/** Panel title */
		title: string;
		/** Toggle button text (e.g., "Show Server Logs") */
		toggleLabel: string;
		/** Optional description below the title */
		description?: string;
		/** Icon snippet for the title */
		icon: Snippet;
		/** Whether the panel is expanded */
		isExpanded: boolean;
		/** Toggle expanded state */
		onToggle: () => void;
		/** Loading state for toggle */
		isLoading?: boolean;
		/** Error message to display */
		error?: string | null;
		/** Whether content is empty */
		isEmpty?: boolean;
		/** Message to show when empty */
		emptyMessage?: string;
		/** Left side of subtitle (e.g., filename, "In-memory buffer") */
		subtitleLeft?: string;
		/** Right side of subtitle (e.g., "5 entries", "300 lines") */
		subtitleRight?: string;
		/** Fullscreen subtitle (single line format) */
		fullscreenSubtitle?: string;
		/** Content to render when expanded */
		children: Snippet;
		/** Content to render in fullscreen mode (defaults to children) */
		fullscreenContent?: Snippet;

		// Action callbacks - only shown when expanded and has content
		onRefresh?: () => void;
		refreshDisabled?: boolean;
		refreshLoading?: boolean;

		onExport?: () => void;
		exportDisabled?: boolean;

		onDownload?: () => void;
		downloadDisabled?: boolean;

		onClear?: () => void;
		clearDisabled?: boolean;

		/** Enable fullscreen support */
		hasFullscreen?: boolean;
	}

	let {
		title,
		toggleLabel,
		description,
		icon,
		isExpanded,
		onToggle,
		isLoading = false,
		error = null,
		isEmpty = false,
		emptyMessage = 'No data available.',
		subtitleLeft,
		subtitleRight,
		fullscreenSubtitle,
		children,
		fullscreenContent,
		onRefresh,
		refreshDisabled = false,
		refreshLoading = false,
		onExport,
		exportDisabled = false,
		onDownload,
		downloadDisabled = false,
		onClear,
		clearDisabled = false,
		hasFullscreen = false,
	}: Props = $props();

	let isFullscreen = $state(false);

	// Show action buttons when expanded and has content (not empty, no error)
	const showActions = $derived(isExpanded && !isEmpty && !error);
</script>

<!-- Reusable action buttons snippet -->
{#snippet actionButtons()}
	{#if onRefresh}
		<button
			type="button"
			class="btn-icon-touch"
			onclick={onRefresh}
			disabled={refreshDisabled || refreshLoading}
			title="Refresh"
			aria-label="Refresh"
		>
			<RefreshCw class={refreshLoading ? 'animate-spin' : ''} size={20} strokeWidth={1.5} />
		</button>
	{/if}
	{#if onDownload}
		<button
			type="button"
			class="btn-icon-touch"
			onclick={onDownload}
			disabled={downloadDisabled}
			title="Download"
			aria-label="Download"
		>
			<Download size={20} strokeWidth={1.5} />
		</button>
	{/if}
	{#if onExport}
		<button
			type="button"
			class="btn-icon-touch"
			onclick={onExport}
			disabled={exportDisabled}
			title="Export"
			aria-label="Export"
		>
			<Share size={20} strokeWidth={1.5} />
		</button>
	{/if}
	{#if onClear}
		<button
			type="button"
			class="btn-icon-touch"
			onclick={onClear}
			disabled={clearDisabled}
			title="Clear"
			aria-label="Clear"
		>
			<Trash2 size={20} strokeWidth={1.5} />
		</button>
	{/if}
{/snippet}

<div class="space-y-3 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-4">
	<!-- Header row -->
	<div class="flex items-center justify-between">
		<h3 class="flex items-center gap-2 text-sm font-semibold text-neutral-200">
			{@render icon()}
			{title}
		</h3>
		{#if showActions}
			<div class="flex items-center gap-1.5">
				{@render actionButtons()}
				{#if hasFullscreen}
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => (isFullscreen = true)}
						title="Expand fullscreen"
						aria-label="View fullscreen"
					>
						<Maximize2 size={20} strokeWidth={1.5} />
					</button>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Description -->
	{#if description}
		<p class="text-xs text-neutral-500">{description}</p>
	{/if}

	<!-- Toggle button -->
	<button
		type="button"
		class="flex w-full items-center gap-2 rounded-lg border border-neutral-700 bg-neutral-800/50 px-3 py-2.5 text-sm text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
		onclick={onToggle}
		disabled={isLoading}
	>
		{#if isLoading}
			<div
				class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
			></div>
			<span>Loading...</span>
		{:else}
			<span>{toggleLabel}</span>
			<ChevronDown
				class="ml-auto transition-transform {isExpanded ? 'rotate-180' : ''}"
				size={16}
			/>
		{/if}
	</button>

	<!-- Content area (when expanded) -->
	{#if isExpanded}
		{#if error}
			<div class="rounded-lg border border-error-500/30 bg-error-500/10 p-3 text-sm text-error-500">
				{error}
			</div>
		{:else if isEmpty}
			<div
				class="rounded-lg border border-neutral-700 bg-neutral-800/50 p-3 text-center text-sm text-neutral-400"
			>
				{emptyMessage}
			</div>
		{:else}
			<div class="space-y-2">
				{#if subtitleLeft || subtitleRight}
					<div class="flex items-center justify-between text-xs text-neutral-500">
						<span>{subtitleLeft ?? ''}</span>
						<span>{subtitleRight ?? ''}</span>
					</div>
				{/if}
				{@render children()}
			</div>
		{/if}
	{/if}
</div>

<!-- Fullscreen Modal -->
{#if hasFullscreen}
	<FullscreenPanel
		bind:open={isFullscreen}
		{title}
		subtitle={fullscreenSubtitle}
		onclose={() => (isFullscreen = false)}
	>
		{#snippet icon()}
			<!-- Re-render the icon prop passed to LogPanel -->
			{@render icon?.()}
		{/snippet}

		{#snippet headerActions()}
			{@render actionButtons()}
		{/snippet}

		{#if fullscreenContent}
			{@render fullscreenContent()}
		{:else}
			{@render children()}
		{/if}
	</FullscreenPanel>
{/if}
