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
			<svg
				class="h-5 w-5 {refreshLoading ? 'animate-spin' : ''}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path d="M23 4v6h-6M1 20v-6h6" />
				<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
			</svg>
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
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
				<polyline points="7 10 12 15 17 10" />
				<line x1="12" y1="15" x2="12" y2="3" />
			</svg>
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
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
				<polyline points="7 10 12 15 17 10" />
				<line x1="12" y1="15" x2="12" y2="3" />
			</svg>
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
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path
					d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
				/>
			</svg>
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
			<svg
				class="ml-auto h-4 w-4 transition-transform {isExpanded ? 'rotate-180' : ''}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<polyline points="6 9 12 15 18 9" />
			</svg>
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
