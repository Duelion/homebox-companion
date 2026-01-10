<script lang="ts">
	interface Props {
		currentStep: number;
		totalSteps?: number;
	}

	let { currentStep, totalSteps = 4 }: Props = $props();

	const steps = $derived(Array.from({ length: totalSteps }, (_, i) => i + 1));
</script>

<div class="mb-6 flex items-center justify-center gap-2">
	{#each steps as step (step)}
		{@const index = step - 1}
		{#if index > 0}
			<!-- Connecting line between steps -->
			<span
				class="h-[3px] max-w-12 flex-1 rounded-full transition-colors duration-300 {step < currentStep
					? 'bg-success'
					: step === currentStep
						? 'bg-primary'
						: 'bg-base-content/20'}"
			></span>
		{/if}
		<!-- Step circle -->
		<span
			class="flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold shadow-sm transition-all duration-300 {step ===
			currentStep
				? 'bg-primary text-primary-content ring-4 ring-primary/20'
				: step < currentStep
					? 'bg-success text-success-content'
					: 'border border-base-content/20 bg-base-300 text-base-content/60'}"
		>
			{#if step < currentStep}
				<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2.5"
						d="M5 13l4 4L19 7"
					/>
				</svg>
			{:else}
				{step}
			{/if}
		</span>
	{/each}
</div>
