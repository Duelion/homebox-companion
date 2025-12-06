<script lang="ts">
	interface Props {
		message?: string;
		size?: 'sm' | 'md' | 'lg';
	}

	let { message = '', size = 'md' }: Props = $props();

	const sizeClasses = {
		sm: 'w-5 h-5 border-2',
		md: 'w-8 h-8 border-3',
		lg: 'w-12 h-12 border-4',
	};
</script>

<div class="flex flex-col items-center justify-center gap-3">
	<div
		class="rounded-full border-primary/30 border-t-primary animate-spin {sizeClasses[size]}"
	></div>
	{#if message}
		<p class="text-text-muted text-sm animate-pulse">{message}</p>
	{/if}
</div>








