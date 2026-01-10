<script lang="ts">
	import { createLogger } from '$lib/utils/logger';
	import Button from './Button.svelte';
	import type { SessionSummary } from '$lib/api';

	const log = createLogger({ prefix: 'RecoveryBanner' });

	interface Props {
		session: SessionSummary;
		onRecover: () => void;
		onDismiss: () => void;
		isRecovering?: boolean;
	}

	let { session, onRecover, onDismiss, isRecovering = false }: Props = $props();

	// Format the timestamp for display
	function formatTime(isoString: string): string {
		try {
			const date = new Date(isoString);
			const now = new Date();
			const diffMs = now.getTime() - date.getTime();
			const diffMins = Math.floor(diffMs / 60000);
			const diffHours = Math.floor(diffMins / 60);
			const diffDays = Math.floor(diffHours / 24);

			if (diffMins < 1) return 'just now';
			if (diffMins < 60) return `${diffMins} min ago`;
			if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
			if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;

			return date.toLocaleDateString();
		} catch {
			return 'unknown time';
		}
	}

	function handleRecover() {
		log.info('User chose to recover session', session.session_id);
		onRecover();
	}

	function handleDismiss() {
		log.info('User dismissed recovery banner', session.session_id);
		onDismiss();
	}
</script>

<div
	class="mx-4 mt-4 p-4 bg-warning-500/10 border border-warning-500/30 rounded-xl"
	role="alert"
>
	<div class="flex items-start gap-3">
		<!-- Icon -->
		<div class="flex-shrink-0 mt-0.5">
			<svg
				class="w-5 h-5 text-warning-500"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path
					d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
				/>
			</svg>
		</div>

		<!-- Content -->
		<div class="flex-1 min-w-0">
			<h3 class="text-sm font-semibold text-warning-500">
				Unfinished Session Found
			</h3>
			<p class="mt-1 text-sm text-neutral-400">
				{#if session.location_name}
					You have an incomplete session at <span class="text-neutral-200">{session.location_name}</span>
				{:else}
					You have an incomplete session
				{/if}
				from {formatTime(session.created_at)}.
			</p>

			<!-- Stats -->
			<div class="mt-2 flex flex-wrap gap-3 text-xs text-neutral-500">
				{#if session.image_count > 0}
					<span class="flex items-center gap-1">
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
							<path d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
						</svg>
						{session.image_count} image{session.image_count !== 1 ? 's' : ''}
					</span>
				{/if}
				{#if session.completed_count > 0}
					<span class="flex items-center gap-1 text-success-500">
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
							<polyline points="20 6 9 17 4 12" />
						</svg>
						{session.completed_count} processed
					</span>
				{/if}
				{#if session.pending_count > 0}
					<span class="flex items-center gap-1 text-warning-500">
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
							<path d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
						{session.pending_count} pending
					</span>
				{/if}
				{#if session.failed_count > 0}
					<span class="flex items-center gap-1 text-error-500">
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
							<path d="M18 6L6 18M6 6l12 12" />
						</svg>
						{session.failed_count} failed
					</span>
				{/if}
			</div>

			<!-- Actions -->
			<div class="mt-3 flex gap-2">
				<Button
					variant="warning"
					size="sm"
					onclick={handleRecover}
					loading={isRecovering}
					disabled={isRecovering}
				>
					{#if isRecovering}
						Recovering...
					{:else}
						Resume Session
					{/if}
				</Button>
				<Button
					variant="ghost"
					size="sm"
					onclick={handleDismiss}
					disabled={isRecovering}
				>
					Dismiss
				</Button>
			</div>
		</div>

		<!-- Close button -->
		<button
			type="button"
			class="flex-shrink-0 p-1 text-neutral-500 hover:text-neutral-300 rounded-lg hover:bg-neutral-800/50 transition-colors"
			onclick={handleDismiss}
			disabled={isRecovering}
			aria-label="Dismiss"
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
				<path d="M6 18L18 6M6 6l12 12" />
			</svg>
		</button>
	</div>
</div>
