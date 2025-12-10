<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	// Props
	interface Props {
		current: number;
		total: number;
		message?: string;
		onComplete?: () => void;
	}

	let { current, total, message = 'Analyzing...', onComplete }: Props = $props();

	// Internal state for animated progress
	let displayProgress = $state(0);
	let animationInterval: number | null = null;
	let hasCalledComplete = $state(false);
	let isComplete = $state(false);

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
			// Move 2-4% of remaining distance per tick (slower for 5-15s OpenAI response time)
			const moveRate = 0.02 + Math.random() * 0.02;
			displayProgress += distance * moveRate;
		}, 250); // Tick every 250ms for slower, more deliberate movement
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
			hasCalledComplete = false;
			isComplete = false;
			startAnimation();
		} else {
			// All items complete - animate to 100% then call onComplete
			stopAnimation();
			
			// Smoothly animate to 100%
			const finalAnimationInterval = window.setInterval(() => {
				if (displayProgress >= 99.9) {
					displayProgress = 100;
					clearInterval(finalAnimationInterval);
					
					// Trigger completion effect
					isComplete = true;
					
					// Wait for the pop animation + brief hold before signaling completion
					if (!hasCalledComplete && onComplete) {
						setTimeout(() => {
							hasCalledComplete = true;
							onComplete();
						}, 600); // 300ms pop + 300ms hold
					}
				} else {
					// Quick smooth movement to 100%
					const distance = 100 - displayProgress;
					displayProgress += distance * 0.15;
				}
			}, 50);
		}
	});

	// Cleanup on unmount
	onDestroy(() => {
		stopAnimation();
	});
</script>

<!-- Full-screen overlay centered vertically -->
<div class="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
	<div class="w-full max-w-sm mx-4 flex flex-col items-center gap-6">
		<!-- Spinner or success checkmark -->
		<div class="relative">
			{#if isComplete}
				<!-- Success checkmark -->
				<div class="w-16 h-16 rounded-full bg-success/20 flex items-center justify-center success-pop">
					<svg class="w-8 h-8 text-success" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24">
						<polyline points="20 6 9 17 4 12" />
					</svg>
				</div>
			{:else}
				<!-- Spinning loader -->
				<div class="w-16 h-16 rounded-full border-4 border-primary/30 border-t-primary animate-spin"></div>
			{/if}
		</div>

		<!-- Message -->
		<p class="text-lg font-medium text-text text-center">{message}</p>

		<!-- Progress bar -->
		<div class="w-full bg-surface rounded-xl border border-border p-4">
			<div class="flex items-center justify-between mb-2">
				<span class="text-sm text-text-muted">Progress</span>
				<span class="text-sm text-text-muted">{current} / {total}</span>
			</div>

			<!-- Progress bar with notches -->
			<div class="relative">
				<!-- Track -->
				<div 
					class="h-2 bg-surface-elevated rounded-full overflow-hidden transition-all duration-300"
					class:complete-glow={isComplete}
				>
					<!-- Fill bar with smooth transition -->
					<div
						class="h-full transition-all duration-300 ease-out"
						class:bg-primary={!isComplete}
						class:bg-success={isComplete}
						style="width: {Math.max(0, Math.min(100, displayProgress))}%"
					></div>
				</div>

				<!-- Notches -->
				<div class="absolute inset-0 pointer-events-none">
					{#each notches as notch}
						<div
							class="absolute top-1/2 -translate-y-1/2 w-0.5 h-3 transition-colors duration-300"
							class:bg-primary={notch.completed && !isComplete}
							class:bg-success={notch.completed && isComplete}
							class:bg-border={!notch.completed}
							style="left: {notch.position}%"
						></div>
					{/each}
				</div>
			</div>
		</div>
	</div>
</div>

<style>
	.complete-glow {
		box-shadow: 0 0 12px rgba(34, 197, 94, 0.5);
	}

	.success-pop {
		animation: pop 300ms ease-out;
	}

	@keyframes pop {
		0% {
			transform: scale(0.8);
			opacity: 0;
		}
		50% {
			transform: scale(1.1);
		}
		100% {
			transform: scale(1);
			opacity: 1;
		}
	}
</style>

