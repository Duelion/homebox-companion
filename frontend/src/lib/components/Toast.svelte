<script lang="ts">
	import { uiStore, dismissToast, TOAST_DURATION_MS } from '$lib/stores/ui.svelte';
	import { Info, CheckCircle, TriangleAlert, XCircle, Download, X } from 'lucide-svelte';

	// Derive toasts from store for reactive template usage
	let toasts = $derived(uiStore.toasts);

	// Updated color styles with new design tokens
	const typeStyles = {
		info: 'bg-primary-600/20 border-primary-500/30 text-primary-300',
		success: 'bg-success-500/20 border-success-500/30 text-success-500',
		warning: 'bg-warning-500/20 border-warning-500/30 text-warning-500',
		error: 'bg-error-500/20 border-error-500/30 text-error-500',
		update: 'bg-warning-900/90 border-warning-500/40 text-warning-500',
	};

	// Progress bar colors for each type
	const progressColors = {
		info: 'bg-primary-500',
		success: 'bg-success-500',
		warning: 'bg-warning-500',
		error: 'bg-error-500',
		update: 'bg-warning-500',
	};
</script>

<!-- aria-live region for screen readers -->
<div class="sr-only" role="status" aria-live="polite" aria-atomic="true">
	{#each toasts as toast (toast.id)}
		{#if !toast.exiting}
			{toast.type}: {toast.message}
		{/if}
	{/each}
</div>

{#if toasts.length > 0}
	<div
		class="pointer-events-none fixed left-4 right-4 top-4 z-50 flex flex-col gap-2 md:left-auto md:right-4 md:w-96"
	>
		{#each toasts as toast (toast.id)}
			<div
				class="pointer-events-auto flex flex-col overflow-hidden rounded-xl border shadow-lg backdrop-blur-lg
					{typeStyles[toast.type]}
					{toast.exiting ? 'toast-exit' : 'toast-enter'}"
				style="view-transition-name: toast-{toast.id};"
				role="alert"
			>
				<!-- Toast content -->
				<div class="flex items-center gap-3 px-4 py-2">
					{#if toast.type === 'info'}
						<Info class="shrink-0" size={20} />
					{:else if toast.type === 'success'}
						<CheckCircle class="shrink-0" size={20} />
					{:else if toast.type === 'warning'}
						<TriangleAlert class="shrink-0" size={20} />
					{:else if toast.type === 'error'}
						<XCircle class="shrink-0" size={20} />
					{:else if toast.type === 'update'}
						<Download class="shrink-0" size={20} />
					{/if}
					<div class="flex flex-1 items-center gap-2">
						<p class="text-sm font-medium">{toast.message}</p>
						{#if toast.action}
							<!-- eslint-disable svelte/no-navigation-without-resolve -->
							<a
								href={toast.action.href}
								target="_blank"
								rel="noopener noreferrer"
								class="shrink-0 text-sm underline transition-colors {toast.type === 'update'
									? 'text-primary-400 hover:text-primary-300'
									: 'hover:opacity-80'}"
							>
								{toast.action.label}
							</a>
							<!-- eslint-enable svelte/no-navigation-without-resolve -->
						{/if}
					</div>
					<button
						type="button"
						class="flex min-h-touch min-w-touch items-center justify-center rounded-lg p-1.5 transition-colors hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-white/30"
						aria-label="Dismiss notification"
						onclick={() => dismissToast(toast.id)}
					>
						<X size={16} />
					</button>
				</div>

				<!-- Auto-dismiss progress bar (only for non-persistent toasts) -->
				{#if !toast.exiting && !toast.persistent}
					<div class="h-0.5 w-full bg-black/20">
						<div
							class="h-full {progressColors[toast.type]} toast-progress"
							style="--duration: {TOAST_DURATION_MS}ms;"
						></div>
					</div>
				{/if}
			</div>
		{/each}
	</div>
{/if}

<style>
	.toast-enter {
		@apply animate-toast-in;
	}

	.toast-exit {
		@apply animate-toast-out;
	}

	/* Progress bar animation */
	.toast-progress {
		@apply animate-progress-shrink;
	}
</style>
