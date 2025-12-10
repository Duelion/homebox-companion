<script lang="ts">
	import { toasts, dismissToast } from '$lib/stores/ui';

	const typeStyles = {
		info: 'bg-primary/20 border-primary/30 text-primary-light',
		success: 'bg-success/20 border-success/30 text-green-300',
		warning: 'bg-warning/20 border-warning/30 text-yellow-300',
		error: 'bg-danger/20 border-danger/30 text-red-300',
	};

	const typeIcons = {
		info: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
		success: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
		warning: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
		error: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z',
	};
</script>

{#if $toasts.length > 0}
	<div class="fixed top-4 left-4 right-4 z-50 flex flex-col gap-2 pointer-events-none md:left-auto md:right-4 md:w-96">
		{#each $toasts as toast (toast.id)}
			<div
				class="pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-lg shadow-lg
					{typeStyles[toast.type]}
					{toast.exiting ? 'toast-exit' : 'toast-enter'}"
				role="alert"
			>
				<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={typeIcons[toast.type]} />
				</svg>
				<p class="flex-1 text-sm font-medium">{toast.message}</p>
				<button
					type="button"
					class="p-1 rounded-lg hover:bg-white/10 transition-colors"
					aria-label="Dismiss notification"
					onclick={() => dismissToast(toast.id)}
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
		{/each}
	</div>
{/if}

<style>
	.toast-enter {
		animation: slideDown 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
	}
	
	.toast-exit {
		animation: fadeOutDown 0.3s cubic-bezier(0.4, 0, 0.2, 1) forwards;
	}
	
	@keyframes slideDown {
		from {
			opacity: 0;
			transform: translateY(-100%) scale(0.95);
		}
		to {
			opacity: 1;
			transform: translateY(0) scale(1);
		}
	}
	
	@keyframes fadeOutDown {
		from {
			opacity: 1;
			transform: translateY(0) scale(1);
		}
		to {
			opacity: 0;
			transform: translateY(1rem) scale(0.95);
		}
	}
</style>
