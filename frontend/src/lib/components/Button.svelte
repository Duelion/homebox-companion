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

	// Modernized variant classes with DaisyUI semantic colors
	const variantClasses = {
		primary:
			'bg-primary text-primary-content hover:bg-primary/90 active:bg-primary/80 disabled:bg-base-300 disabled:text-base-content/40 focus:ring-primary/50',
		secondary:
			'bg-base-300 text-base-content hover:bg-base-300/80 hover:border-base-content/30 active:bg-base-300/70 border border-base-content/20 disabled:bg-base-200 disabled:text-base-content/30 disabled:border-base-content/10 focus:ring-base-content/30',
		ghost:
			'bg-transparent text-base-content/60 hover:text-base-content hover:bg-base-300 active:bg-base-300/80 disabled:text-base-content/30 focus:ring-base-content/30',
		danger:
			'bg-error text-error-content hover:bg-error/90 active:bg-error/80 disabled:bg-base-300 disabled:text-base-content/40 focus:ring-error/50',
		warning:
			'bg-warning text-warning-content hover:bg-warning/90 active:bg-warning/80 disabled:bg-base-300 disabled:text-base-content/40 focus:ring-warning/50',
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
	class="inline-flex items-center justify-center rounded-xl font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-base-100 active:scale-[0.98] disabled:cursor-not-allowed {variantClasses[
		variant
	]} {sizeClasses[size]}"
	class:w-full={full}
	style="touch-action: manipulation;"
>
	{#if loading}
		<div
			class="border-current/30 h-5 w-5 animate-spin rounded-full border-2 border-t-current"
		></div>
	{/if}
	{@render children()}
</button>
