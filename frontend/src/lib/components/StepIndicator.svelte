<script lang="ts">
	import { Check } from 'lucide-svelte';

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
				class="h-[3px] max-w-12 flex-1 rounded-full transition-colors duration-300"
				class:bg-success-600={step < currentStep}
				class:bg-primary-600={step === currentStep}
				class:bg-neutral-700={step > currentStep}
			></span>
		{/if}
		<!-- Step circle -->
		<span
			class="flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold shadow-sm transition-all duration-300 {step ===
			currentStep
				? 'bg-primary-600 text-white ring-4 ring-primary-500/20'
				: step < currentStep
					? 'bg-success-600 text-white'
					: 'border border-neutral-700 bg-neutral-800 text-neutral-400'}"
		>
			{#if step < currentStep}
				<Check size={20} strokeWidth={2.5} />
			{:else}
				{step}
			{/if}
		</span>
	{/each}
</div>
