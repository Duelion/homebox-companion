<script lang="ts">
	/**
	 * AboutSection - Version info, config details, and update checking.
	 */
	import { uiStore } from '$lib/stores/ui.svelte';
	import { settingsService } from '$lib/workflows/settings.svelte';
	import {
		Info,
		Download,
		Check,
		RefreshCw,
		Github,
		Star,
		ChevronDown,
		ExternalLink,
	} from 'lucide-svelte';

	const service = settingsService;
</script>

<section class="card space-y-4">
	<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
		<Info class="text-primary-400" size={20} strokeWidth={1.5} />
		About
	</h2>

	<!-- Version - Always visible -->
	<div class="flex items-center justify-between">
		<span class="text-neutral-400">Version</span>
		<div class="flex items-center gap-2">
			<span class="font-mono text-neutral-100">{uiStore.appVersion || 'Loading...'}</span>
			{#if service.updateAvailable && service.latestVersion}
				<a
					href="https://github.com/Duelion/homebox-companion/releases/latest"
					target="_blank"
					rel="noopener noreferrer"
					class="inline-flex items-center gap-1 rounded-full bg-warning-500/20 px-2 py-0.5 text-xs text-warning-500 transition-colors hover:bg-warning-500/30"
					title="Click to view release"
				>
					<Download size={12} strokeWidth={2} />
					<span>v{service.latestVersion}</span>
				</a>
			{:else if service.updateCheckDone}
				<span
					class="inline-flex items-center gap-1 rounded-full bg-success-500/20 px-2 py-0.5 text-xs text-success-500"
				>
					<Check size={12} strokeWidth={2} />
					<span>Up to date</span>
				</span>
			{/if}
			<button
				type="button"
				class="inline-flex items-center gap-1 rounded-full border border-neutral-700 bg-neutral-800/50 px-2 py-0.5 text-xs text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-100 disabled:cursor-not-allowed disabled:opacity-50"
				onclick={() => service.checkForUpdates()}
				disabled={service.isLoading.updateCheck}
				title="Check for updates"
			>
				{#if service.isLoading.updateCheck}
					<div
						class="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
					></div>
				{:else}
					<RefreshCw size={12} strokeWidth={2} />
				{/if}
				<span>Check</span>
			</button>
		</div>
	</div>
	{#if service.errors.updateCheck}
		<p class="text-xs text-error-500">{service.errors.updateCheck}</p>
	{/if}

	<!-- GitHub Link -->
	<div class="space-y-2 border-t border-neutral-800 pt-3">
		<a
			href="https://github.com/Duelion/homebox-companion"
			target="_blank"
			rel="noopener noreferrer"
			class="group flex items-center justify-between py-2 text-neutral-400 transition-colors hover:text-neutral-100"
		>
			<span class="flex items-center gap-2">
				<Github size={20} />
				<span>View on GitHub</span>
			</span>
			<ExternalLink class="opacity-50 transition-opacity group-hover:opacity-100" size={16} />
		</a>
		<p class="flex items-start gap-1.5 text-xs text-neutral-500">
			<Star class="mt-0.5 flex-shrink-0 text-warning-500" size={14} fill="currentColor" />
			<span>Enjoying the app? Consider giving us a star on GitHub!</span>
		</p>
	</div>

	<!-- Expandable Details Button -->
	<button
		type="button"
		class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
		onclick={() => (service.showAboutDetails = !service.showAboutDetails)}
	>
		<Info class="text-primary-400" size={20} strokeWidth={1.5} />
		<span>Show Details</span>
		<ChevronDown
			class="ml-auto transition-transform {service.showAboutDetails ? 'rotate-180' : ''}"
			size={16}
		/>
	</button>

	{#if service.showAboutDetails}
		<div class="space-y-3">
			<!-- Configuration Info -->
			{#if service.config}
				<!-- Homebox URL -->
				<div class="flex items-center justify-between border-t border-neutral-800 py-2">
					<span class="flex-shrink-0 text-neutral-400">Homebox URL</span>
					<div class="flex min-w-0 items-center gap-2">
						<!-- eslint-disable svelte/no-navigation-without-resolve -- External URL, not an app route -->
						<a
							href={service.config.homebox_url}
							target="_blank"
							rel="noopener noreferrer"
							class="flex max-w-[200px] items-center gap-1 truncate font-mono text-sm text-neutral-100 transition-colors hover:text-primary-400"
							title={service.config.homebox_url}
						>
							<!-- eslint-enable svelte/no-navigation-without-resolve -->
							<span class="truncate">{service.config.homebox_url}</span>
							<ExternalLink class="flex-shrink-0 opacity-70" size={12} />
						</a>
						{#if service.config.is_demo_mode}
							<span
								class="inline-flex flex-shrink-0 items-center gap-1 rounded-full bg-warning-500/20 px-2 py-0.5 text-xs text-warning-500"
							>
								Demo
							</span>
						{/if}
					</div>
				</div>

				<!-- AI Model -->
				<div class="flex items-center justify-between border-t border-neutral-800 py-2">
					<span class="text-neutral-400">AI Model</span>
					<span class="font-mono text-sm text-neutral-100">{service.config.llm_model}</span>
				</div>

				<!-- Image Quality -->
				<div class="flex items-center justify-between border-t border-neutral-800 py-2">
					<span class="text-neutral-400">Image Quality</span>
					<span class="font-mono text-sm capitalize text-neutral-100"
						>{service.config.image_quality}</span
					>
				</div>
			{:else if service.isLoading.config}
				<div class="flex items-center justify-center py-4">
					<div
						class="h-5 w-5 animate-spin rounded-full border-2 border-primary-500 border-t-transparent"
					></div>
				</div>
			{/if}
		</div>
	{/if}
</section>
