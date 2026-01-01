<script lang="ts">
	interface Props {
		/** Width of the skeleton (CSS value) */
		width?: string;
		/** Height of the skeleton (CSS value) */
		height?: string;
		/** Border radius variant */
		rounded?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full';
		/** Additional CSS classes */
		class?: string;
	}

	let { width = '100%', height = '1rem', rounded = 'lg', class: className = '' }: Props = $props();

	const roundedClasses = {
		sm: 'rounded-sm',
		md: 'rounded-md',
		lg: 'rounded-lg',
		xl: 'rounded-xl',
		'2xl': 'rounded-2xl',
		full: 'rounded-full',
	};
</script>

<div
	class="skeleton animate-shimmer {roundedClasses[rounded]} {className}"
	style="width: {width}; height: {height};"
	aria-hidden="true"
></div>
