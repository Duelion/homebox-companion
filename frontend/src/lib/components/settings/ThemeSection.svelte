<script lang="ts">
	/**
	 * ThemeSection - Theme selector matching Homebox theme options.
	 *
	 * Displays all DaisyUI themes in a grid for easy selection.
	 * Persists selection to localStorage.
	 */
	import { themeStore, THEME_INFO, type ThemeName } from '$lib/stores/theme.svelte';

	// Current theme from store
	const currentTheme = $derived(themeStore.theme);

	function selectTheme(theme: ThemeName) {
		themeStore.setTheme(theme);
	}

	// Group themes by light/dark for better organization
	const darkThemes = THEME_INFO.filter((t) => t.isDark);
	const lightThemes = THEME_INFO.filter((t) => !t.isDark);
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
			<path
				d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"
			/>
		</svg>
		Theme Settings
	</h2>

	<p class="text-xs text-neutral-400">
		Choose a theme to match your Homebox setup. Theme settings are stored in your browser.
	</p>

	<!-- Dark Themes -->
	<div class="space-y-2">
		<h3 class="text-sm font-medium text-neutral-300">Dark Themes</h3>
		<div class="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
			{#each darkThemes as theme}
				<button
					type="button"
					class="group relative flex flex-col items-start rounded-lg border-2 p-3 text-left transition-all
						{currentTheme === theme.name
						? 'border-primary-500 bg-primary-500/10 ring-2 ring-primary-500/20'
						: 'border-neutral-700 bg-neutral-800/50 hover:border-neutral-600 hover:bg-neutral-800'}"
					onclick={() => selectTheme(theme.name)}
					data-theme={theme.name}
				>
					<!-- Theme preview colors -->
					<div class="mb-2 flex gap-1">
						<div class="h-4 w-4 rounded bg-primary"></div>
						<div class="h-4 w-4 rounded bg-secondary"></div>
						<div class="h-4 w-4 rounded bg-accent"></div>
					</div>
					<span class="text-xs font-medium text-base-content">{theme.label}</span>
					{#if currentTheme === theme.name}
						<div class="absolute right-2 top-2">
							<svg class="h-4 w-4 text-primary-500" fill="currentColor" viewBox="0 0 20 20">
								<path
									fill-rule="evenodd"
									d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
									clip-rule="evenodd"
								/>
							</svg>
						</div>
					{/if}
				</button>
			{/each}
		</div>
	</div>

	<!-- Light Themes -->
	<div class="space-y-2">
		<h3 class="text-sm font-medium text-neutral-300">Light Themes</h3>
		<div class="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
			{#each lightThemes as theme}
				<button
					type="button"
					class="group relative flex flex-col items-start rounded-lg border-2 p-3 text-left transition-all
						{currentTheme === theme.name
						? 'border-primary-500 bg-primary-500/10 ring-2 ring-primary-500/20'
						: 'border-neutral-700 bg-neutral-800/50 hover:border-neutral-600 hover:bg-neutral-800'}"
					onclick={() => selectTheme(theme.name)}
					data-theme={theme.name}
				>
					<!-- Theme preview colors -->
					<div class="mb-2 flex gap-1">
						<div class="h-4 w-4 rounded bg-primary"></div>
						<div class="h-4 w-4 rounded bg-secondary"></div>
						<div class="h-4 w-4 rounded bg-accent"></div>
					</div>
					<span class="text-xs font-medium text-base-content">{theme.label}</span>
					{#if currentTheme === theme.name}
						<div class="absolute right-2 top-2">
							<svg class="h-4 w-4 text-primary-500" fill="currentColor" viewBox="0 0 20 20">
								<path
									fill-rule="evenodd"
									d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
									clip-rule="evenodd"
								/>
							</svg>
						</div>
					{/if}
				</button>
			{/each}
		</div>
	</div>

	<!-- Quick toggle -->
	<div class="flex items-center gap-3 border-t border-neutral-700 pt-4">
		<button
			type="button"
			class="flex items-center gap-2 rounded-lg border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-neutral-300 transition-colors hover:bg-neutral-700"
			onclick={() => themeStore.toggleLightDark()}
		>
			{#if themeStore.isDark}
				<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
					<path
						d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
					/>
				</svg>
				Switch to Light
			{:else}
				<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
					<path d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
				</svg>
				Switch to Dark
			{/if}
		</button>
		<span class="text-xs text-neutral-500">Quick toggle between light and dark modes</span>
	</div>
</section>
