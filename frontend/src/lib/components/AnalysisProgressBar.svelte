<script lang="ts">
	import { prefersReducedMotion } from 'svelte/motion';

	// Props
	interface Props {
		current: number;
		total: number;
		runId?: number;
		ready?: boolean;
		message?: string;
		onComplete?: () => void;
	}

	let {
		current,
		total,
		runId = 0,
		ready = true,
		message = 'Analyzing...',
		onComplete,
	}: Props = $props();

	// Internal state for animated progress
	let displayProgress = $state(0);
	let isComplete = $state(false);
	let lastRunId: number | undefined;
	let completedRunId: number | null = null;

	// Calculate the target for fake progress (90% toward the next milestone)
	let targetProgress = $derived(() => {
		if (total <= 0) return 0;
		if (current >= total) return 100;
		const nextMilestone = ((current + 1) / total) * 100;
		const currentMilestone = (current / total) * 100;
		return currentMilestone + (nextMilestone - currentMilestone) * 0.9;
	});

	// Generate notch positions for each item (excluding the last one at 100%)
	let notches = $derived(
		Array.from({ length: total - 1 }, (_, i) => ({
			position: ((i + 1) / total) * 100,
			completed: i < current,
		}))
	);

	// Each effect run owns every timer it creates. A changed run, readiness, or
	// progress milestone tears down old work before starting the next animation.
	$effect(() => {
		const effectRunId = runId;
		const effectCurrent = current;
		const effectTotal = total;
		const canComplete = ready && effectTotal > 0 && effectCurrent >= effectTotal;
		const complete = onComplete;
		const reduceMotion = prefersReducedMotion.current;

		if (lastRunId !== effectRunId) {
			lastRunId = effectRunId;
			completedRunId = null;
			displayProgress = 0;
			isComplete = false;
		}

		let animationInterval: number | null = null;
		let finalAnimationInterval: number | null = null;
		let completionTimeout: number | null = null;

		const clearTimers = () => {
			if (animationInterval !== null) window.clearInterval(animationInterval);
			if (finalAnimationInterval !== null) window.clearInterval(finalAnimationInterval);
			if (completionTimeout !== null) window.clearTimeout(completionTimeout);
		};

		if (effectCurrent > 0 && effectTotal > 0) {
			const milestone = (effectCurrent / effectTotal) * 100;
			displayProgress = !canComplete && effectCurrent >= effectTotal ? 95 : milestone;
		}

		if (reduceMotion) {
			displayProgress = canComplete
				? 100
				: !ready && effectCurrent >= effectTotal
					? 95
					: targetProgress();
			isComplete = canComplete;
			if (canComplete && completedRunId !== effectRunId) {
				// A zero-delay task keeps completion cancellable when the user leaves this run.
				completionTimeout = window.setTimeout(() => {
					completionTimeout = null;
					if (completedRunId === effectRunId) return;
					completedRunId = effectRunId;
					complete?.();
				}, 0);
			}
		} else if (!canComplete || completedRunId === effectRunId) {
			if (canComplete && completedRunId === effectRunId) {
				displayProgress = 100;
				isComplete = true;
			} else {
				isComplete = false;
				animationInterval = window.setInterval(() => {
					const target = !ready && current >= total ? 95 : targetProgress();
					const distance = target - displayProgress;

					if (Math.abs(distance) < 0.1) {
						displayProgress = target;
						return;
					}

					// Move 2-4% of remaining distance per tick for a deliberate feel.
					const moveRate = 0.02 + Math.random() * 0.02;
					displayProgress += distance * moveRate;
				}, 250);
			}
		} else {
			finalAnimationInterval = window.setInterval(() => {
				if (displayProgress >= 99.9) {
					displayProgress = 100;
					if (finalAnimationInterval !== null) {
						window.clearInterval(finalAnimationInterval);
						finalAnimationInterval = null;
					}
					isComplete = true;

					if (complete) {
						completionTimeout = window.setTimeout(() => {
							completionTimeout = null;
							if (completedRunId === effectRunId) return;
							completedRunId = effectRunId;
							complete();
						}, 600);
					}
				} else {
					const distance = 100 - displayProgress;
					displayProgress += distance * 0.15;
				}
			}, 50);
		}

		return clearTimers;
	});
</script>

<div class="mb-6 rounded-xl border border-neutral-700 bg-neutral-800 p-4">
	<!-- Header with message and count -->
	<div class="mb-2 flex items-center justify-between">
		<span class="text-body-sm font-medium text-neutral-200">{message}</span>
		<span class="text-body-sm text-neutral-400">{current} / {total}</span>
	</div>

	<!-- Progress bar with notches -->
	<div class="relative">
		<!-- Track -->
		<div
			class="h-2 overflow-hidden rounded-full bg-neutral-700 transition-all duration-300"
			class:complete-pop={isComplete}
		>
			<!-- Fill bar with smooth transition -->
			<div
				class="h-full transition-all duration-300 ease-out"
				class:bg-primary-500={!isComplete}
				class:bg-success-500={isComplete}
				style="width: {Math.max(0, Math.min(100, displayProgress))}%"
			></div>
		</div>

		<!-- Notches -->
		<div class="pointer-events-none absolute inset-0">
			{#each notches as notch (notch.position)}
				<div
					class="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 transition-colors duration-300"
					class:bg-primary-500={notch.completed && !isComplete}
					class:bg-success-500={notch.completed && isComplete}
					class:bg-neutral-600={!notch.completed}
					style="left: {notch.position}%"
				></div>
			{/each}
		</div>
	</div>
</div>

<style>
	@reference "../../app.css";

	.complete-pop {
		@apply animate-pop shadow-success-glow;
	}
</style>
