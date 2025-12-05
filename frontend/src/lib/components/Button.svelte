<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
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

	const variantClasses = {
		primary: 'bg-primary text-white hover:bg-primary-hover hover:shadow-glow',
		secondary: 'bg-surface-elevated text-text hover:bg-surface-hover border border-border',
		ghost: 'bg-transparent text-text-muted hover:text-text hover:bg-surface-elevated',
		danger: 'bg-danger text-white hover:bg-red-600',
	};

	const sizeClasses = {
		sm: 'px-3 py-2 text-sm gap-1.5',
		md: 'px-4 py-3 gap-2',
		lg: 'px-6 py-4 text-lg gap-2.5',
	};
</script>

<button
	{type}
	{onclick}
	disabled={disabled || loading}
	class="inline-flex items-center justify-center rounded-xl font-medium transition-all duration-200 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed {variantClasses[variant]} {sizeClasses[size]}"
	class:w-full={full}
>
	{#if loading}
		<div class="w-5 h-5 rounded-full border-2 border-current/30 border-t-current animate-spin"></div>
	{/if}
	{@render children()}
</button>






