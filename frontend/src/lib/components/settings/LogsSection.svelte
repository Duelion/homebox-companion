<script lang="ts">
	/**
	 * LogsSection - Application logs, frontend logs, chat transcript, and LLM debug log.
	 *
	 * Uses the reusable LogPanel component for consistent UI across all sections.
	 */
	import { FileText, Monitor, MessageSquare, Code, ChevronDown } from 'lucide-svelte';
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

	const llmDebugLogsSubtitleRight = $derived.by(() => {
		if (!service.llmDebugLog) return '';
		const { truncated, total_lines } = service.llmDebugLog;
		const shown = truncated && total_lines > 300 ? 300 : total_lines;
		return truncated ? `Last ${shown} of ${total_lines} lines` : `${total_lines} lines`;
	});

	const llmDebugLogsFullscreenSubtitle = $derived.by(() => {
		if (!service.llmDebugLog?.filename) return undefined;
		return `${service.llmDebugLog.filename} • ${llmDebugLogsSubtitleRight}`;
	});
</script>

{#snippet logsIcon(className: string)}
	<FileText class={className} strokeWidth={1.5} />
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
		<ChevronDown
			class="ml-auto transition-transform {showLogsSection ? 'rotate-180' : ''}"
			size={16}
		/>
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
				<Monitor class="h-4 w-4 text-neutral-400" size={16} strokeWidth={1.5} />
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
				<MessageSquare class="h-4 w-4 text-neutral-400" size={16} strokeWidth={1.5} />
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
			isEmpty={!service.llmDebugLog}
			emptyMessage="No LLM debug log files found."
			subtitleLeft={service.llmDebugLog?.filename ?? undefined}
			subtitleRight={llmDebugLogsSubtitleRight}
			fullscreenSubtitle={llmDebugLogsFullscreenSubtitle}
			onRefresh={() => service.refreshLLMDebugLog()}
			refreshDisabled={service.isLoading.llmDebugLog}
			refreshLoading={service.isLoading.llmDebugLog}
			onDownload={() => service.downloadLLMDebugLogs()}
			downloadDisabled={!service.llmDebugLog?.filename}
			hasFullscreen={true}
		>
			{#snippet icon()}
				<Code class="h-4 w-4 text-neutral-400" size={16} strokeWidth={1.5} />
			{/snippet}
			{#if service.llmDebugLog}
				<LogViewer source={{ type: 'backend', logs: service.llmDebugLog.logs }} />
			{/if}
			{#snippet fullscreenContent()}
				{#if service.llmDebugLog}
					<LogViewer source={{ type: 'backend', logs: service.llmDebugLog.logs }} maxHeight="" />
				{/if}
			{/snippet}
		</LogPanel>
	{/if}
</section>
