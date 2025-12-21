<script lang="ts">
	interface Props {
		currentStep: number;
		totalSteps?: number;
	}

	let { currentStep, totalSteps = 4 }: Props = $props();

	const steps = $derived(Array.from({ length: totalSteps }, (_, i) => i + 1));
</script>

<div class="flex items-center justify-center gap-2 mb-6">
	{#each steps as step, index}
		{#if index > 0}
			<!-- Connecting line between steps -->
			<span
				class="flex-1 max-w-12 h-[3px] rounded-full transition-colors duration-300"
				class:bg-success-600={step < currentStep}
				class:bg-primary-600={step === currentStep}
				class:bg-neutral-700={step > currentStep}
			></span>
		{/if}
		<!-- Step circle -->
		<span
			class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-300 shadow-sm {step ===
			currentStep
				? 'bg-primary-600 text-white ring-4 ring-primary-500/20'
				: step < currentStep
					? 'bg-success-600 text-white'
					: 'bg-neutral-800 text-neutral-400 border border-neutral-700'}"
		>
			{#if step < currentStep}
				<svg
					class="w-5 h-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
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
