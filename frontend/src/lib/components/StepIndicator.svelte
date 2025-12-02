<script lang="ts">
	interface Props {
		currentStep: number;
		totalSteps?: number;
	}

	let { currentStep, totalSteps = 4 }: Props = $props();

	const steps = Array.from({ length: totalSteps }, (_, i) => i + 1);
</script>

<div class="flex items-center justify-center gap-2 mb-6">
	{#each steps as step, index}
		{#if index > 0}
			<span
				class="w-8 h-0.5 transition-colors duration-300"
				class:bg-primary={step <= currentStep}
				class:bg-border={step > currentStep}
			></span>
		{/if}
		<span
			class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-300 {step === currentStep ? 'bg-primary text-white' : step < currentStep ? 'bg-success text-white' : 'bg-surface-elevated text-text-muted'}"
		>
			{#if step < currentStep}
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
				</svg>
			{:else}
				{step}
			{/if}
		</span>
	{/each}
</div>

