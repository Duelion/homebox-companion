<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	// Props
	interface Props {
		current: number;
		total: number;
		message?: string;
	}

	let { current, total, message = 'Analyzing...' }: Props = $props();

	// Internal state for animated progress
	let displayProgress = $state(0);
	let animationInterval: number | null = null;

	// Calculate the real progress percentage (where we should eventually snap to)
	let realProgress = $derived((current / total) * 100);
	
	// Calculate the target for fake progress (90% toward the next milestone)
	let targetProgress = $derived(() => {
		if (current >= total) return 100;
		const nextMilestone = ((current + 1) / total) * 100;
		const currentMilestone = (current / total) * 100;
		return currentMilestone + (nextMilestone - currentMilestone) * 0.9;
	});

	// Generate notch positions for each item
	let notches = $derived(
		Array.from({ length: total }, (_, i) => ({
			position: ((i + 1) / total) * 100,
			completed: i < current
		}))
	);

	// Animation logic
	function startAnimation() {
		if (animationInterval !== null) return;

		animationInterval = window.setInterval(() => {
			const target = targetProgress();
			const distance = target - displayProgress;

			// If we're very close to the target, stop animating
			if (Math.abs(distance) < 0.1) {
				displayProgress = target;
				return;
			}

			// Asymptotic approach with random variance for organic feel
			// Move 8-12% of remaining distance per tick
			const moveRate = 0.08 + Math.random() * 0.04;
			displayProgress += distance * moveRate;
		}, 100); // Tick every 100ms
	}

	function stopAnimation() {
		if (animationInterval !== null) {
			clearInterval(animationInterval);
			animationInterval = null;
		}
	}

	// Watch for changes in current to snap to milestone
	$effect(() => {
		// When current changes, immediately snap to the milestone
		if (current > 0) {
			const milestone = (current / total) * 100;
			displayProgress = milestone;
		}
		
		// Start animating toward the next target if not complete
		if (current < total) {
			startAnimation();
		} else {
			stopAnimation();
			displayProgress = 100;
		}
	});

	// Cleanup on unmount
	onDestroy(() => {
		stopAnimation();
	});
</script>

<div class="bg-surface rounded-xl border border-border p-4 mb-6">
	<!-- Header with message and count -->
	<div class="flex items-center justify-between mb-2">
		<span class="text-sm font-medium text-text">{message}</span>
		<span class="text-sm text-text-muted">{current} / {total}</span>
	</div>

	<!-- Progress bar with notches -->
	<div class="relative">
		<!-- Track -->
		<div class="h-2 bg-surface-elevated rounded-full overflow-hidden">
			<!-- Fill bar with smooth transition -->
			<div
				class="h-full bg-primary transition-all duration-300 ease-out"
				style="width: {Math.max(0, Math.min(100, displayProgress))}%"
			></div>
		</div>

		<!-- Notches -->
		<div class="absolute inset-0 pointer-events-none">
			{#each notches as notch}
				<div
					class="absolute top-1/2 -translate-y-1/2 w-0.5 h-3 transition-colors duration-300"
					class:bg-primary={notch.completed}
					class:bg-border={!notch.completed}
					style="left: {notch.position}%"
				></div>
			{/each}
		</div>
	</div>
</div>

