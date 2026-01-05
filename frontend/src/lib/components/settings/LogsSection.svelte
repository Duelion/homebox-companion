<script lang="ts">
	/**
	 * LogsSection - Application logs, frontend logs, chat transcript, and LLM debug log.
	 *
	 * Uses the reusable LogPanel component for consistent UI across all sections.
	 */
	import { settingsService } from '$lib/workflows/settings.svelte';
	import { chatStore } from '$lib/stores/chat.svelte';
	import LogViewer from '$lib/components/LogViewer.svelte';
	import LogPanel from '$lib/components/settings/LogPanel.svelte';

	const service = settingsService;

	// Main section expansion state
	let showLogsSection = $state(false);

	// Chat transcript state (local to this component)
	let showChatTranscript = $state(false);

	// Derived values for cleaner templates
	const serverLogsSubtitleRight = $derived.by(() => {
		if (!service.serverLogs) return '';
		const { truncated, total_lines } = service.serverLogs;
		const shown = truncated && total_lines > 300 ? 300 : total_lines;
		return truncated ? `Last ${shown} of ${total_lines} lines` : `${total_lines} lines`;
	});

	const serverLogsFullscreenSubtitle = $derived.by(() => {
		if (!service.serverLogs?.filename) return undefined;
		return `${service.serverLogs.filename} • ${serverLogsSubtitleRight}`;
	});
</script>

{#snippet logsIcon(className: string)}
	<svg
		class={className}
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
{/snippet}

<section class="card space-y-4">
	<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
		{@render logsIcon('h-5 w-5 text-primary-400')}
		Logs & Debugging
	</h2>

	<p class="text-body-sm text-neutral-400">
		View application logs, frontend console output, and AI interaction history for debugging.
	</p>

	<button
		type="button"
		class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
		onclick={() => (showLogsSection = !showLogsSection)}
	>
		{@render logsIcon('h-5 w-5 text-primary-400')}
		<span>View Logs</span>
		<svg
			class="ml-auto h-4 w-4 transition-transform {showLogsSection ? 'rotate-180' : ''}"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
		>
			<polyline points="6 9 12 15 18 9" />
		</svg>
	</button>

	{#if showLogsSection}
		<!-- Application Logs -->
		<LogPanel
			title="Application Logs"
			toggleLabel="Show Server Logs"
			isExpanded={service.showServerLogs}
			onToggle={() => service.toggleServerLogs()}
			isLoading={service.isLoading.serverLogs}
			error={service.errors.serverLogs}
			isEmpty={!service.serverLogs}
			emptyMessage="No server logs available."
			subtitleLeft={service.serverLogs?.filename ?? undefined}
			subtitleRight={serverLogsSubtitleRight}
			fullscreenSubtitle={serverLogsFullscreenSubtitle}
			onRefresh={() => service.refreshServerLogs()}
			refreshDisabled={service.isLoading.serverLogs}
			refreshLoading={service.isLoading.serverLogs}
			onDownload={() => service.downloadServerLogs()}
			downloadDisabled={!service.serverLogs?.filename}
			hasFullscreen={true}
		>
			{#snippet icon()}
				{@render logsIcon('h-4 w-4 text-neutral-400')}
			{/snippet}
			{#if service.serverLogs}
				<LogViewer source={{ type: 'backend', logs: service.serverLogs.logs }} />
			{/if}
			{#snippet fullscreenContent()}
				{#if service.serverLogs}
					<LogViewer source={{ type: 'backend', logs: service.serverLogs.logs }} maxHeight="" />
				{/if}
			{/snippet}
		</LogPanel>

		<!-- Frontend Logs -->
		<LogPanel
			title="Frontend Logs"
			toggleLabel="Show Frontend Logs"
			description="Browser console logs stored in memory. Cleared on page refresh."
			isExpanded={service.showFrontendLogs}
			onToggle={() => service.toggleFrontendLogs()}
			isEmpty={service.frontendLogs.length === 0}
			emptyMessage="No frontend logs available. Logs will appear here as you use the app."
			subtitleLeft="In-memory buffer"
			subtitleRight={`${service.frontendLogs.length} ${service.frontendLogs.length === 1 ? 'entry' : 'entries'}`}
			fullscreenSubtitle={`In-memory buffer • ${service.frontendLogs.length} ${service.frontendLogs.length === 1 ? 'entry' : 'entries'}`}
			onRefresh={() => service.refreshFrontendLogs()}
			onExport={() => service.exportFrontendLogs()}
			onClear={() => service.clearFrontendLogs()}
			hasFullscreen={true}
		>
			{#snippet icon()}
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
			{/snippet}
			<LogViewer source={{ type: 'frontend', entries: service.frontendLogs }} />
			{#snippet fullscreenContent()}
				<LogViewer source={{ type: 'frontend', entries: service.frontendLogs }} maxHeight="" />
			{/snippet}
		</LogPanel>

		<!-- Chat Transcript -->
		<LogPanel
			title="Chat Transcript"
			toggleLabel="Show Chat Transcript"
			description="Export your conversation history. Clear chat from the chat window."
			isExpanded={showChatTranscript}
			onToggle={() => (showChatTranscript = !showChatTranscript)}
			isEmpty={chatStore.messageCount === 0}
			emptyMessage="No chat messages. Start a conversation in the chat window."
			subtitleLeft="Conversation history"
			subtitleRight={`${chatStore.messageCount} ${chatStore.messageCount === 1 ? 'message' : 'messages'}`}
			fullscreenSubtitle={`Conversation history • ${chatStore.messageCount} ${chatStore.messageCount === 1 ? 'message' : 'messages'}`}
			onExport={() => service.exportChatTranscript()}
			exportDisabled={chatStore.messageCount === 0}
			hasFullscreen={true}
		>
			{#snippet icon()}
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
			{/snippet}
			<LogViewer source={{ type: 'json', data: chatStore.messages }} />
			{#snippet fullscreenContent()}
				<LogViewer source={{ type: 'json', data: chatStore.messages }} maxHeight="" />
			{/snippet}
		</LogPanel>

		<!-- LLM Debug Log -->
		<LogPanel
			title="LLM Debug Log"
			toggleLabel="Show LLM Debug Log"
			description="Raw LLM request/response pairs. Technical debugging data for developers."
			isExpanded={service.showLLMDebugLog}
			onToggle={() => service.toggleLLMDebugLog()}
			isLoading={service.isLoading.llmDebugLog}
			error={service.errors.llmDebugLog}
			isEmpty={service.llmDebugLog.length === 0}
			emptyMessage="No LLM interactions recorded. Start a conversation with the AI to capture debug data."
			subtitleLeft="LLM interactions"
			subtitleRight={`${service.llmDebugLog.length} ${service.llmDebugLog.length === 1 ? 'entry' : 'entries'}`}
			fullscreenSubtitle={`LLM interactions • ${service.llmDebugLog.length} ${service.llmDebugLog.length === 1 ? 'entry' : 'entries'}`}
			onRefresh={() => service.refreshLLMDebugLog()}
			refreshDisabled={service.isLoading.llmDebugLog}
			refreshLoading={service.isLoading.llmDebugLog}
			onExport={() => service.exportLLMDebugLog()}
			hasFullscreen={true}
		>
			{#snippet icon()}
				<svg
					class="h-4 w-4 text-neutral-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
				</svg>
			{/snippet}
			<LogViewer source={{ type: 'json', data: service.llmDebugLog }} />
			{#snippet fullscreenContent()}
				<LogViewer source={{ type: 'json', data: service.llmDebugLog }} maxHeight="" />
			{/snippet}
		</LogPanel>
	{/if}
</section>
