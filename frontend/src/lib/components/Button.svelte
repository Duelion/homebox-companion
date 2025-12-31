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

	// Track touch state to prevent double-firing (touchend + click)
	let touchFired = $state(false);

	// Handle touch events for iOS Safari
	// touchend fires reliably even when dismissing keyboard, unlike click
	function handleTouchEnd(e: TouchEvent) {
		if (disabled || loading) return;
		
		// Prevent synthetic click event from firing
		e.preventDefault();
		
		// Mark that touch fired so we don't double-fire on click
		touchFired = true;
		
		// Call the onclick handler
		onclick?.();
		
		// Reset after click event would have fired (300ms is iOS click delay)
		setTimeout(() => {
			touchFired = false;
		}, 300);
	}

	// Handle click events for desktop/keyboard interactions
	function handleClick() {
		if (disabled || loading) return;
		
		// Prevent double-fire if touch already triggered
		if (touchFired) return;
		
		onclick?.();
	}

	// Modernized variant classes with tonal colors
	const variantClasses = {
		primary: 'bg-primary-600 text-white hover:bg-primary-500 active:bg-primary-700 disabled:bg-neutral-800 disabled:text-neutral-500 focus:ring-primary-500/50',
		secondary: 'bg-neutral-800 text-neutral-200 hover:bg-neutral-700 hover:border-neutral-600 active:bg-neutral-900 border border-neutral-700 disabled:bg-neutral-900 disabled:text-neutral-600 disabled:border-neutral-800 focus:ring-neutral-500/50',
		ghost: 'bg-transparent text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 active:bg-neutral-700 disabled:text-neutral-600 focus:ring-neutral-500/50',
		danger: 'bg-error-600 text-white hover:bg-error-500 active:bg-error-700 disabled:bg-neutral-800 disabled:text-neutral-500 focus:ring-error-500/50',
		warning: 'bg-warning-500 text-white hover:bg-warning-600 active:bg-warning-700 disabled:bg-neutral-800 disabled:text-neutral-500 focus:ring-warning-500/50',
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
	class="inline-flex items-center justify-center rounded-xl font-medium transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-neutral-950 {variantClasses[variant]} {sizeClasses[size]}"
	class:w-full={full}
	style="touch-action: manipulation;"
>
	{#if loading}
		<div class="w-5 h-5 rounded-full border-2 border-current/30 border-t-current animate-spin"></div>
	{/if}
	{@render children()}
</button>
