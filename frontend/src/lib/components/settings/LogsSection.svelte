<script lang="ts">
	/**
	 * LogsSection - Application logs, frontend logs, and AI chat history.
	 */
	import { settingsService } from '$lib/workflows/settings.svelte';
	import LogViewer from '$lib/components/LogViewer.svelte';
	import FullscreenPanel from '$lib/components/FullscreenPanel.svelte';

	const service = settingsService;

	// Fullscreen states (local UI state)
	let serverLogsFullscreen = $state(false);
	let frontendLogsFullscreen = $state(false);
</script>

<section class="card space-y-4">
	<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
		<svg
			class="h-5 w-5 text-primary-400"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
			<polyline points="14 2 14 8 20 8" />
			<line x1="16" y1="13" x2="8" y2="13" />
			<line x1="16" y1="17" x2="8" y2="17" />
			<polyline points="10 9 9 9 8 9" />
		</svg>
		Logs & Debugging
	</h2>

	<p class="text-body-sm text-neutral-400">
		View application logs, frontend console output, and AI interaction history for debugging.
	</p>

	<!-- Application Logs Sub-section -->
	<div class="space-y-3 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-4">
		<div class="flex items-center justify-between">
			<h3 class="flex items-center gap-2 text-sm font-semibold text-neutral-200">
				<svg
					class="h-4 w-4 text-neutral-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
					<polyline points="14 2 14 8 20 8" />
					<line x1="16" y1="13" x2="8" y2="13" />
					<line x1="16" y1="17" x2="8" y2="17" />
				</svg>
				Application Logs
			</h3>
			{#if service.showServerLogs && service.serverLogs}
				<div class="flex items-center gap-1.5">
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => service.refreshServerLogs()}
						disabled={service.isLoading.serverLogs}
						title="Refresh logs"
						aria-label="Refresh logs"
					>
						<svg
							class="h-5 w-5 {service.isLoading.serverLogs ? 'animate-spin' : ''}"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M23 4v6h-6M1 20v-6h6" />
							<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
						</svg>
					</button>
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => service.downloadServerLogs()}
						disabled={!service.serverLogs.filename}
						title="Download full log file"
						aria-label="Download logs"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
							<polyline points="7 10 12 15 17 10" />
							<line x1="12" y1="15" x2="12" y2="3" />
						</svg>
					</button>
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => (serverLogsFullscreen = true)}
						title="Expand fullscreen"
						aria-label="View logs fullscreen"
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
				</div>
			{/if}
		</div>

		<button
			type="button"
			class="flex w-full items-center gap-2 rounded-lg border border-neutral-700 bg-neutral-800/50 px-3 py-2.5 text-sm text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
			onclick={() => service.toggleServerLogs()}
			disabled={service.isLoading.serverLogs}
		>
			{#if service.isLoading.serverLogs}
				<div
					class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
				></div>
				<span>Loading logs...</span>
			{:else}
				<span>Show Server Logs</span>
				<svg
					class="ml-auto h-4 w-4 transition-transform {service.showServerLogs ? 'rotate-180' : ''}"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<polyline points="6 9 12 15 18 9" />
				</svg>
			{/if}
		</button>

		{#if service.showServerLogs}
			{#if service.errors.serverLogs}
				<div
					class="rounded-lg border border-error-500/30 bg-error-500/10 p-3 text-sm text-error-500"
				>
					{service.errors.serverLogs}
				</div>
			{:else if service.serverLogs}
				<div class="space-y-2">
					{#if service.serverLogs.filename}
						<div class="flex items-center justify-between text-xs text-neutral-500">
							<span>{service.serverLogs.filename}</span>
							<span>
								{service.serverLogs.truncated
									? `Last ${service.serverLogs.total_lines > 300 ? 300 : service.serverLogs.total_lines} of ${service.serverLogs.total_lines}`
									: `${service.serverLogs.total_lines}`} lines
							</span>
						</div>
					{/if}
					<LogViewer source={{ type: 'backend', logs: service.serverLogs.logs }} />
				</div>
			{/if}
		{/if}
	</div>

	<!-- Frontend Logs Sub-section -->
	<div class="space-y-3 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-4">
		<div class="flex items-center justify-between">
			<h3 class="flex items-center gap-2 text-sm font-semibold text-neutral-200">
				<svg
					class="h-4 w-4 text-neutral-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
					/>
				</svg>
				Frontend Logs
			</h3>
			{#if service.showFrontendLogs && service.frontendLogs.length > 0}
				<div class="flex items-center gap-1.5">
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => service.refreshFrontendLogs()}
						title="Refresh logs"
						aria-label="Refresh logs"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M23 4v6h-6M1 20v-6h6" />
							<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
						</svg>
					</button>
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => service.exportFrontendLogs()}
						title="Export as JSON"
						aria-label="Export logs"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
							<polyline points="7 10 12 15 17 10" />
							<line x1="12" y1="15" x2="12" y2="3" />
						</svg>
					</button>
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => service.clearFrontendLogs()}
						title="Clear logs"
						aria-label="Clear logs"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path
								d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
							/>
						</svg>
					</button>
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => (frontendLogsFullscreen = true)}
						title="Expand fullscreen"
						aria-label="View logs fullscreen"
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
				</div>
			{/if}
		</div>

		<p class="text-xs text-neutral-500">
			Browser console logs stored in memory. Cleared on page refresh.
		</p>

		<button
			type="button"
			class="flex w-full items-center gap-2 rounded-lg border border-neutral-700 bg-neutral-800/50 px-3 py-2.5 text-sm text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
			onclick={() => service.toggleFrontendLogs()}
		>
			<span>Show Frontend Logs</span>
			<svg
				class="ml-auto h-4 w-4 transition-transform {service.showFrontendLogs ? 'rotate-180' : ''}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<polyline points="6 9 12 15 18 9" />
			</svg>
		</button>

		{#if service.showFrontendLogs}
			{#if service.frontendLogs.length === 0}
				<div
					class="rounded-lg border border-neutral-700 bg-neutral-800/50 p-3 text-center text-sm text-neutral-400"
				>
					No frontend logs available. Logs will appear here as you use the app.
				</div>
			{:else}
				<div class="space-y-2">
					<div class="flex items-center justify-between text-xs text-neutral-500">
						<span>In-memory buffer</span>
						<span>
							{service.frontendLogs.length}
							{service.frontendLogs.length === 1 ? 'entry' : 'entries'}
						</span>
					</div>
					<LogViewer source={{ type: 'frontend', entries: service.frontendLogs }} />
				</div>
			{/if}
		{/if}
	</div>

	<!-- AI Chat History Sub-section -->
	<div class="space-y-3 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-4">
		<div class="flex items-center justify-between">
			<h3 class="flex items-center gap-2 text-sm font-semibold text-neutral-200">
				<svg
					class="h-4 w-4 text-neutral-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
					/>
				</svg>
				AI Chat History
			</h3>
			{#if service.showChatHistory && service.chatHistory.length > 0}
				<div class="flex items-center gap-1.5">
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => service.refreshChatHistory()}
						title="Refresh"
						aria-label="Refresh chat history"
						disabled={service.isLoading.chatHistory}
					>
						<svg
							class="h-5 w-5 {service.isLoading.chatHistory ? 'animate-spin' : ''}"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M23 4v6h-6M1 20v-6h6" />
							<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
						</svg>
					</button>
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => service.exportChatHistory()}
						title="Export as JSON"
						aria-label="Export chat history"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
							<polyline points="7 10 12 15 17 10" />
							<line x1="12" y1="15" x2="12" y2="3" />
						</svg>
					</button>
					<button
						type="button"
						class="btn-icon-touch"
						onclick={() => service.clearChatHistory()}
						title="Clear history"
						aria-label="Clear chat history"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path
								d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
							/>
						</svg>
					</button>
				</div>
			{/if}
		</div>

		<p class="text-xs text-neutral-500">
			Raw LLM request/response history. Shows complete messages sent to the AI.
		</p>

		<button
			type="button"
			class="flex w-full items-center gap-2 rounded-lg border border-neutral-700 bg-neutral-800/50 px-3 py-2.5 text-sm text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
			onclick={() => service.toggleChatHistory()}
			disabled={service.isLoading.chatHistory}
		>
			{#if service.isLoading.chatHistory}
				<div
					class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
				></div>
				<span>Loading...</span>
			{:else}
				<span>Show AI Chat History</span>
				<svg
					class="ml-auto h-4 w-4 transition-transform {service.showChatHistory ? 'rotate-180' : ''}"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<polyline points="6 9 12 15 18 9" />
				</svg>
			{/if}
		</button>

		{#if service.showChatHistory}
			{#if service.errors.chatHistory}
				<div
					class="rounded-lg border border-error-500/30 bg-error-500/10 p-3 text-sm text-error-500"
				>
					{service.errors.chatHistory}
				</div>
			{:else if service.chatHistory.length === 0}
				<div
					class="rounded-lg border border-neutral-700 bg-neutral-800/50 p-3 text-center text-sm text-neutral-400"
				>
					No chat history available. Start a conversation with the AI to see interactions here.
				</div>
			{:else}
				<div class="space-y-2">
					<div class="flex items-center justify-between text-xs text-neutral-500">
						<span>LLM interactions</span>
						<span>
							{service.chatHistory.length}
							{service.chatHistory.length === 1 ? 'entry' : 'entries'}
						</span>
					</div>
					<LogViewer source={{ type: 'json', data: service.chatHistory }} />
				</div>
			{/if}
		{/if}
	</div>
</section>

<!-- Fullscreen Server Logs Modal -->
<FullscreenPanel
	bind:open={serverLogsFullscreen}
	title="Application Logs"
	subtitle={service.serverLogs?.filename
		? `${service.serverLogs.filename} • ${service.serverLogs.truncated ? `Last ${service.serverLogs.total_lines > 300 ? 300 : service.serverLogs.total_lines} of ${service.serverLogs.total_lines}` : service.serverLogs.total_lines} lines`
		: undefined}
	onclose={() => (serverLogsFullscreen = false)}
>
	{#snippet icon()}
		<svg
			class="h-5 w-5 text-primary-400"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
			<polyline points="14 2 14 8 20 8" />
			<line x1="16" y1="13" x2="8" y2="13" />
			<line x1="16" y1="17" x2="8" y2="17" />
			<polyline points="10 9 9 9 8 9" />
		</svg>
	{/snippet}

	{#snippet headerActions()}
		<button
			type="button"
			class="btn-icon-touch"
			onclick={() => service.refreshServerLogs()}
			disabled={service.isLoading.serverLogs}
			title="Refresh logs"
			aria-label="Refresh logs"
		>
			<svg
				class="h-5 w-5 {service.isLoading.serverLogs ? 'animate-spin' : ''}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path d="M23 4v6h-6M1 20v-6h6" />
				<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
			</svg>
		</button>
		<button
			type="button"
			class="btn-icon-touch"
			onclick={() => service.downloadServerLogs()}
			disabled={!service.serverLogs?.filename}
			title="Download full log file"
			aria-label="Download logs"
		>
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
				<polyline points="7 10 12 15 17 10" />
				<line x1="12" y1="15" x2="12" y2="3" />
			</svg>
		</button>
	{/snippet}

	{#if service.serverLogs}
		<LogViewer source={{ type: 'backend', logs: service.serverLogs.logs }} maxHeight="" />
	{/if}
</FullscreenPanel>

<!-- Fullscreen Frontend Logs Modal -->
<FullscreenPanel
	bind:open={frontendLogsFullscreen}
	title="Frontend Logs"
	subtitle="In-memory buffer • {service.frontendLogs.length} {service.frontendLogs.length === 1
		? 'entry'
		: 'entries'}"
	onclose={() => (frontendLogsFullscreen = false)}
>
	{#snippet icon()}
		<svg
			class="h-5 w-5 text-primary-400"
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

	{#snippet headerActions()}
		<button
			type="button"
			class="btn-icon-touch"
			onclick={() => service.refreshFrontendLogs()}
			title="Refresh logs"
			aria-label="Refresh logs"
		>
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path d="M23 4v6h-6M1 20v-6h6" />
				<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
			</svg>
		</button>
		<button
			type="button"
			class="btn-icon-touch"
			onclick={() => service.exportFrontendLogs()}
			title="Export as JSON"
			aria-label="Export logs"
		>
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
				<polyline points="7 10 12 15 17 10" />
				<line x1="12" y1="15" x2="12" y2="3" />
			</svg>
		</button>
		<button
			type="button"
			class="btn-icon-touch"
			onclick={() => service.clearFrontendLogs()}
			title="Clear logs"
			aria-label="Clear logs"
		>
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path
					d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
				/>
			</svg>
		</button>
	{/snippet}

	<LogViewer source={{ type: 'frontend', entries: service.frontendLogs }} maxHeight="" />
</FullscreenPanel>
