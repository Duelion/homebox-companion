<script lang="ts">
	import { uiStore, dismissToast, TOAST_DURATION_MS } from '$lib/stores/ui.svelte';

	// Derive toasts from store for reactive template usage
	let toasts = $derived(uiStore.toasts);

	// Updated color styles with new design tokens
	const typeStyles = {
		info: 'bg-primary-600/20 border-primary-500/30 text-primary-300',
		success: 'bg-success-500/20 border-success-500/30 text-success-500',
		warning: 'bg-warning-500/20 border-warning-500/30 text-warning-500',
		error: 'bg-error-500/20 border-error-500/30 text-error-500',
		update: 'bg-amber-900/90 border-amber-500/40 text-amber-300',
	};

	// Progress bar colors for each type
	const progressColors = {
		info: 'bg-primary-500',
		success: 'bg-success-500',
		warning: 'bg-warning-500',
		error: 'bg-error-500',
		update: 'bg-amber-500',
	};

	const typeIcons = {
		info: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
		success: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
		warning:
			'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
		error: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z',
		update: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3',
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
		class="pointer-events-none fixed top-4 right-4 left-4 z-50 flex flex-col gap-2 md:right-4 md:left-auto md:w-96"
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
					<svg class="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d={typeIcons[toast.type]}
						/>
					</svg>
					<div class="flex flex-1 items-center gap-2">
						<p class="text-sm font-medium">{toast.message}</p>
						{#if toast.action}
							<!-- eslint-disable svelte/no-navigation-without-resolve -->
							<a
								href={toast.action.href}
								target="_blank"
								rel="noopener noreferrer"
								class="shrink-0 text-sm underline transition-colors {toast.type === 'update'
									? 'text-primary hover:text-primary/80'
									: 'hover:opacity-80'}"
							>
								{toast.action.label}
							</a>
							<!-- eslint-enable svelte/no-navigation-without-resolve -->
						{/if}
					</div>
					<button
						type="button"
						class="flex min-h-8 min-w-8 items-center justify-center rounded-lg p-1.5 transition-colors hover:bg-white/10 focus:ring-2 focus:ring-white/30 focus:outline-none"
						aria-label="Dismiss notification"
						onclick={() => dismissToast(toast.id)}
					>
						<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M6 18L18 6M6 6l12 12"
							/>
						</svg>
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
