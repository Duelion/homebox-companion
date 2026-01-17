<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'warning';
		size?: 'sm' | 'md' | 'lg';
		disabled?: boolean;
		loading?: boolean;
		full?: boolean;
		type?: 'button' | 'submit' | 'reset';
		onclick?: () => void;
		children: Snippet;
	}

	let {
		variant = 'primary',
		size = 'md',
		disabled = false,
		loading = false,
		full = false,
		type = 'button',
		onclick,
		children,
	}: Props = $props();

	// Track touch state to prevent double-firing (touchend + synthetic click)
	let touchFired = $state(false);

	/**
	 * Handle touch events for iOS Safari keyboard dismissal edge case.
	 *
	 * iOS Safari swallows the first click event after dismissing the virtual keyboard,
	 * but touchend still fires reliably. This handler ensures buttons respond to taps
	 * even when iOS would otherwise swallow the click.
	 *
	 * See: https://github.com/Duelion/homebox-companion/issues/72
	 */
	function handleTouchEnd(e: TouchEvent) {
		if (disabled || loading) return;

		// Mark that touch fired so we don't double-fire on synthetic click
		touchFired = true;

		// Call onclick handler if provided (matches native behavior order)
		onclick?.();

		// Handle form button types explicitly since we're preventing the synthetic click
		const button = e.currentTarget as HTMLButtonElement;
		if (type === 'submit' && button.form) {
			button.form.requestSubmit(button);
		} else if (type === 'reset' && button.form) {
			button.form.reset();
		}

		// Prevent the synthetic click event that would otherwise fire after touchend
		e.preventDefault();

		// Reset flag after the synthetic click would have fired
		// 300ms matches iOS's legacy click delay (though modern iOS with
		// touch-action:manipulation is faster, we keep this for safety)
		setTimeout(() => {
			touchFired = false;
		}, 300);
	}

	/**
	 * Handle click events for desktop, keyboard (Enter/Space), and assistive technology.
	 * On touch devices, this may fire as a synthetic click after touchend - we use
	 * touchFired flag to prevent double-firing in that case.
	 */
	function handleClick() {
		if (disabled || loading) return;

		// Prevent double-fire if touch already triggered this action
		if (touchFired) return;

		onclick?.();
		// Note: for submit/reset buttons, native form behavior handles submission
	}

	// Modernized variant classes with tonal colors
	const variantClasses = {
		primary:
			'bg-primary-600 text-white hover:bg-primary-500 active:bg-primary-700 disabled:bg-neutral-800 disabled:text-neutral-500 focus:ring-primary-500/50',
		secondary:
			'bg-neutral-800 text-neutral-200 hover:bg-neutral-700 hover:border-neutral-600 active:bg-neutral-900 border border-neutral-700 disabled:bg-neutral-900 disabled:text-neutral-600 disabled:border-neutral-800 focus:ring-neutral-500/50',
		ghost:
			'bg-transparent text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 active:bg-neutral-700 disabled:text-neutral-600 focus:ring-neutral-500/50',
		danger:
			'bg-error-600 text-white hover:bg-error-500 active:bg-error-700 disabled:bg-neutral-800 disabled:text-neutral-500 focus:ring-error-500/50',
		warning:
			'bg-warning-500 text-white hover:bg-warning-600 active:bg-warning-700 disabled:bg-neutral-800 disabled:text-neutral-500 focus:ring-warning-500/50',
	};

	const sizeClasses = {
		sm: 'px-3 py-2 text-sm gap-1.5',
		md: 'px-4 py-3 gap-2',
		lg: 'px-6 py-4 text-lg gap-2.5',
	};
</script>

<button
	{type}
	onclick={handleClick}
	ontouchend={handleTouchEnd}
	disabled={disabled || loading}
	class="inline-flex items-center justify-center rounded-xl font-medium transition-all duration-150 focus:ring-2 focus:ring-offset-2 focus:ring-offset-neutral-950 focus:outline-none active:scale-[0.98] disabled:cursor-not-allowed {variantClasses[
		variant
	]} {sizeClasses[size]}"
	class:w-full={full}
>
	{#if loading}
		<div
			class="h-5 w-5 animate-spin rounded-full border-2 border-current/30 border-t-current"
		></div>
	{/if}
	{@render children()}
</button>
