<script lang="ts">
	/**
	 * AboutSection - Version info, config details, and update checking.
	 */
	import { uiStore } from '$lib/stores/ui.svelte';
	import { settingsService } from '$lib/workflows/settings.svelte';

	const service = settingsService;
</script>

<section class="card space-y-4">
	<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
		<svg
			class="h-5 w-5 text-primary-400"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<circle cx="12" cy="12" r="10" />
			<line x1="12" y1="16" x2="12" y2="12" />
			<line x1="12" y1="8" x2="12.01" y2="8" />
		</svg>
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
					<svg
						class="h-3 w-3"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
						<polyline points="7 10 12 15 17 10" />
						<line x1="12" y1="15" x2="12" y2="3" />
					</svg>
					<span>v{service.latestVersion}</span>
				</a>
			{:else if service.updateCheckDone}
				<span
					class="inline-flex items-center gap-1 rounded-full bg-success-500/20 px-2 py-0.5 text-xs text-success-500"
				>
					<svg
						class="h-3 w-3"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<polyline points="20 6 9 17 4 12" />
					</svg>
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
					<svg
						class="h-3 w-3"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path d="M23 4v6h-6M1 20v-6h6" />
						<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
					</svg>
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
				<svg class="h-5 w-5" fill="currentColor" viewBox="0 0 16 16">
					<path
						d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"
					/>
				</svg>
				<span>View on GitHub</span>
			</span>
			<svg
				class="h-4 w-4 opacity-50 transition-opacity group-hover:opacity-100"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
				<polyline points="15 3 21 3 21 9" />
				<line x1="10" y1="14" x2="21" y2="3" />
			</svg>
		</a>
		<p class="flex items-start gap-1.5 text-xs text-neutral-500">
			<svg class="mt-0.5 h-3.5 w-3.5 flex-shrink-0" fill="currentColor" viewBox="0 0 16 16">
				<path
					d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25z"
				/>
			</svg>
			<span>Enjoying the app? Consider giving us a star on GitHub!</span>
		</p>
	</div>

	<!-- Expandable Details Button -->
	<button
		type="button"
		class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
		onclick={() => (service.showAboutDetails = !service.showAboutDetails)}
	>
		<svg
			class="h-5 w-5 text-primary-400"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<circle cx="12" cy="12" r="10" />
			<line x1="12" y1="16" x2="12" y2="12" />
			<line x1="12" y1="8" x2="12.01" y2="8" />
		</svg>
		<span>Show Details</span>
		<svg
			class="ml-auto h-4 w-4 transition-transform {service.showAboutDetails ? 'rotate-180' : ''}"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
		>
			<polyline points="6 9 12 15 18 9" />
		</svg>
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
							<svg
								class="h-3 w-3 flex-shrink-0 opacity-70"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
								<polyline points="15 3 21 3 21 9" />
								<line x1="10" y1="14" x2="21" y2="3" />
							</svg>
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

