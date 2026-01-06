<script lang="ts">
<<<<<<< HEAD
	/**
	 * Settings Page - Thin orchestrator for settings sections.
	 *
	 * This page delegates all state management and business logic to:
	 * - settingsService: Centralized state and API calls
	 * - Section components: UI rendering for each settings area
	 */
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount, onDestroy } from 'svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import { settingsService } from '$lib/workflows/settings.svelte';
=======
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";
	import { authStore } from "$lib/stores/auth.svelte";
	import { resetLocationState } from "$lib/stores/locations.svelte";
	import { uiStore } from "$lib/stores/ui.svelte";
	import { scanWorkflow } from "$lib/workflows/scan.svelte";
	import {
		getConfig,
		getLogs,
		downloadLogs,
		getVersion,
		labels as labelsApi,
		fieldPreferences,
		setDemoMode,
		getAIConfig,
		updateAIConfig,
		testProviderConnection,
		getGPUInfo,
		OLLAMA_VISION_MODELS,
		OPENAI_MODELS,
		ANTHROPIC_MODELS,
		type ConfigResponse,
		type LogsResponse,
		type FieldPreferences,
		type EffectiveDefaults,
		type LabelData,
		type AIConfigResponse,
		type AIConfigInput,
		type GPUInfo,
	} from "$lib/api";
	import {
		getLogBuffer,
		clearLogBuffer,
		exportLogs,
		type LogEntry,
		settingsLogger as log,
	} from "$lib/utils/logger";
	import Button from "$lib/components/Button.svelte";
>>>>>>> 5ceb0f9 (feat(ai-config): add multi-provider AI settings with editable UI)

	import AccountSection from '$lib/components/settings/AccountSection.svelte';
	import AboutSection from '$lib/components/settings/AboutSection.svelte';
	import FieldPrefsSection from '$lib/components/settings/FieldPrefsSection.svelte';
	import LogsSection from '$lib/components/settings/LogsSection.svelte';

<<<<<<< HEAD
=======
	// Frontend logs state
	let frontendLogs = $state<LogEntry[]>([]);
	let showFrontendLogs = $state(false);
	let frontendLogsContainer = $state<HTMLPreElement | null>(null);
	let frontendLogsFullscreenContainer = $state<HTMLDivElement | null>(null);
	let frontendLogsFullscreen = $state(false);

	// Version update state (fetched with force_check to always show updates)
	let updateAvailable = $state(false);
	let latestVersionNumber = $state<string | null>(null);
	let isCheckingUpdates = $state(false);
	let updateCheckError = $state<string | null>(null);
	let updateCheckDone = $state(false); // Shows "Up to date" message after manual check

	// Field preferences state
	let showFieldPrefs = $state(false);
	let isLoadingFieldPrefs = $state(false);
	let saveFieldPrefsState = $state<"idle" | "saving" | "success" | "error">(
		"idle",
	);
	let fieldPrefsError = $state<string | null>(null);
	let availableLabels = $state<LabelData[]>([]);
	let prefs = $state<FieldPreferences>({
		output_language: null,
		default_label_id: null,
		name: null,
		description: null,
		quantity: null,
		manufacturer: null,
		model_number: null,
		serial_number: null,
		purchase_price: null,
		purchase_from: null,
		notes: null,
		naming_examples: null,
	});

	// Prompt preview state
	let showPromptPreview = $state(false);
	let isLoadingPreview = $state(false);
	let promptPreview = $state<string | null>(null);

	// Export env vars state
	let showEnvExport = $state(false);
	let envCopied = $state(false);
	let isLoadingExport = $state(false);
	let exportPrefs = $state<FieldPreferences | null>(null);

	// Effective defaults from backend (env var if set, otherwise hardcoded fallback)
	let effectiveDefaults = $state<EffectiveDefaults | null>(null);

	// Fullscreen modal states
	let logsFullscreen = $state(false);
	let promptFullscreen = $state(false);

	// AI Provider state
	let aiConfig = $state<AIConfigResponse | null>(null);
	let gpuInfo = $state<GPUInfo | null>(null);
	let isLoadingAIConfig = $state(false);
	let showAISection = $state(false);
	let aiConfigError = $state<string | null>(null);
	let isSavingAIConfig = $state(false);
	let isTestingConnection = $state(false);
	let connectionTestResult = $state<{ success: boolean; message: string } | null>(null);
	let aiConfigDirty = $state(false);

	// Editable AI config form state
	let editableAIConfig = $state<AIConfigInput>({
		active_provider: "litellm",
		fallback_to_cloud: true,
		fallback_provider: "litellm",
		ollama: { enabled: false, url: "http://localhost:11434", model: "minicpm-v", timeout: 120 },
		openai: { enabled: false, api_key: null, model: "gpt-4o", max_tokens: 4096 },
		anthropic: { enabled: false, api_key: null, model: "claude-sonnet-4-20250514", max_tokens: 4096 },
		litellm: { enabled: true, model: "gpt-4o" },
	});

	// Field metadata for display
	const fieldMeta: Array<{
		key: keyof FieldPreferences;
		label: string;
		example: string;
	}> = [
		{
			key: "name",
			label: "Name",
			example:
				'"Ball Bearing 6900-2RS 10x22x6mm", "LED Strip COB Green 5V 1M"',
		},
		{
			key: "naming_examples",
			label: "Naming Examples",
			example:
				"Comma-separated examples that show the AI how to format names",
		},
		{
			key: "description",
			label: "Description",
			example: '"Minor scratches on casing", "New in packaging"',
		},
		{
			key: "quantity",
			label: "Quantity",
			example:
				"5 identical screws = qty 5, but 2 sizes = 2 separate items",
		},
		{
			key: "manufacturer",
			label: "Manufacturer",
			example: 'DeWalt, Vallejo (NOT "Shenzhen XYZ Technology Co.")',
		},
		{
			key: "model_number",
			label: "Model Number",
			example: '"DCD771C2", "72.034"',
		},
		{
			key: "serial_number",
			label: "Serial Number",
			example: 'Look for "S/N:", "Serial:" markings',
		},
		{
			key: "purchase_price",
			label: "Purchase Price",
			example: '29.99 (not "$29.99")',
		},
		{
			key: "purchase_from",
			label: "Purchase From",
			example: '"Amazon", "Home Depot"',
		},
		{
			key: "notes",
			label: "Notes",
			example:
				"For defects/warnings only. Include GOOD/BAD examples for clarity.",
		},
	];

	// Redirect if not authenticated
>>>>>>> 5ceb0f9 (feat(ai-config): add multi-provider AI settings with editable UI)
	onMount(async () => {
		// Wait for auth initialization to complete to avoid race conditions
		// where we check isAuthenticated before initializeAuth clears expired tokens
		await getInitPromise();

		if (!authStore.isAuthenticated) {
			goto(resolve('/'));
			return;
		}

		await settingsService.initialize();
	});

	onDestroy(() => {
		// Clean up any pending timeouts
		settingsService.cleanup();
	});
<<<<<<< HEAD
=======

	// Auto-scroll fullscreen logs to bottom when opened or refreshed
	$effect(() => {
		if (logsFullscreenContainer && logs && logsFullscreen) {
			// Use requestAnimationFrame to ensure DOM is updated
			requestAnimationFrame(() => {
				if (logsFullscreenContainer) {
					logsFullscreenContainer.scrollTop =
						logsFullscreenContainer.scrollHeight;
				}
			});
		}
	});

	// Colorize log output like Loguru does in terminal
	// Log format: "YYYY-MM-DD HH:mm:ss | LEVEL    | module:function:line - message"
	function colorizedLogs(): string {
		if (!logs?.logs) return "";

		return logs.logs
			.split("\n")
			.map((line) => {
				// Match the log format: timestamp | level | location - message
				const match = line.match(
					/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s*\| ([^-]+)- (.*)$/,
				);

				if (!match) {
					// Line doesn't match format, return escaped
					return escapeHtml(line);
				}

				const [, timestamp, level, location, message] = match;
				const levelTrimmed = level.trim();

				// Get color class based on log level (matching Loguru's default color scheme)
				// https://github.com/Delgan/loguru/blob/master/loguru/_defaults.py
				let levelClass = "text-neutral-100 font-semibold"; // Default: bold white (INFO)
				switch (levelTrimmed) {
					case "TRACE":
						levelClass = "text-cyan-400 font-semibold";
						break;
					case "DEBUG":
						levelClass = "text-blue-400 font-semibold";
						break;
					case "INFO":
						levelClass = "text-neutral-100 font-semibold";
						break;
					case "SUCCESS":
						levelClass = "text-success-500 font-semibold";
						break;
					case "WARNING":
						levelClass = "text-warning-500 font-semibold";
						break;
					case "ERROR":
						levelClass = "text-error-500 font-semibold";
						break;
					case "CRITICAL":
						levelClass = "text-error-700 font-bold";
						break;
				}

				// Build colorized line matching Loguru's format:
				// <green>timestamp</green> | <level>LEVEL</level> | <cyan>location</cyan> - <level>message</level>
				return (
					`<span class="text-success-500">${escapeHtml(timestamp)}</span> | ` +
					`<span class="${levelClass}">${escapeHtml(level)}</span>| ` +
					`<span class="text-cyan-400">${escapeHtml(location)}</span>- ` +
					`<span class="${levelClass}">${escapeHtml(message)}</span>`
				);
			})
			.join("\n");
	}

	function escapeHtml(text: string): string {
		return text
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&#039;");
	}

	// Frontend logs functions
	function loadFrontendLogs() {
		frontendLogs = [...getLogBuffer()];
		showFrontendLogs = !showFrontendLogs;
	}

	function refreshFrontendLogs() {
		frontendLogs = [...getLogBuffer()];
	}

	function handleClearFrontendLogs() {
		clearLogBuffer();
		frontendLogs = [];
	}

	function handleExportFrontendLogs() {
		const json = exportLogs();
		const blob = new Blob([json], { type: "application/json" });
		const url = window.URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = `frontend-logs-${new Date().toISOString().split("T")[0]}.json`;
		document.body.appendChild(a);
		a.click();
		window.URL.revokeObjectURL(url);
		document.body.removeChild(a);
	}

	// Auto-scroll frontend logs to bottom when loaded or refreshed
	$effect(() => {
		if (
			frontendLogsContainer &&
			frontendLogs.length > 0 &&
			showFrontendLogs
		) {
			requestAnimationFrame(() => {
				if (frontendLogsContainer) {
					frontendLogsContainer.scrollTop =
						frontendLogsContainer.scrollHeight;
				}
			});
		}
	});

	// Auto-scroll fullscreen frontend logs to bottom when opened or refreshed
	$effect(() => {
		if (
			frontendLogsFullscreenContainer &&
			frontendLogs.length > 0 &&
			frontendLogsFullscreen
		) {
			requestAnimationFrame(() => {
				if (frontendLogsFullscreenContainer) {
					frontendLogsFullscreenContainer.scrollTop =
						frontendLogsFullscreenContainer.scrollHeight;
				}
			});
		}
	});

	// Colorize frontend logs (similar to backend logs but adapted for LogEntry format)
	function colorizedFrontendLogs(): string {
		if (!frontendLogs || frontendLogs.length === 0) return "";

		return frontendLogs
			.map((entry) => {
				// Format timestamp from ISO to match backend format
				const date = new Date(entry.timestamp);
				const timestamp = date
					.toISOString()
					.replace("T", " ")
					.substring(0, 19);

				// Get color class based on log level
				let levelClass = "text-neutral-100 font-semibold";
				switch (entry.level) {
					case "TRACE":
						levelClass = "text-cyan-400 font-semibold";
						break;
					case "DEBUG":
						levelClass = "text-blue-400 font-semibold";
						break;
					case "INFO":
						levelClass = "text-neutral-100 font-semibold";
						break;
					case "SUCCESS":
						levelClass = "text-success-500 font-semibold";
						break;
					case "WARNING":
						levelClass = "text-warning-500 font-semibold";
						break;
					case "ERROR":
						levelClass = "text-error-500 font-semibold";
						break;
					case "CRITICAL":
						levelClass = "text-error-700 font-bold";
						break;
				}

				// Pad level to 8 characters for alignment
				const paddedLevel = entry.level.padEnd(8, " ");

				// Build display message: include error summary (first line only) if present
				let displayMessage = entry.message;
				if (entry.error) {
					// Get first line of error (the error message, not the full stack)
					const errorFirstLine = entry.error.split("\n")[0];
					displayMessage = `${entry.message} [${errorFirstLine}]`;
				}

				// Build colorized line matching Loguru's format
				return (
					`<span class="text-success-500">${escapeHtml(timestamp)}</span> | ` +
					`<span class="${levelClass}">${escapeHtml(paddedLevel)}</span>| ` +
					`<span class="text-cyan-400">${escapeHtml(entry.module)}</span>- ` +
					`<span class="${levelClass}">${escapeHtml(displayMessage)}</span>`
				);
			})
			.join("\n");
	}

	function handleLogout() {
		scanWorkflow.reset();
		resetLocationState();
		authStore.logout();
		goto("/");
	}

	async function checkForUpdates() {
		isCheckingUpdates = true;
		updateCheckError = null;
		updateCheckDone = false;

		try {
			const versionResult = await getVersion(true); // Force check for updates

			if (
				versionResult.update_available &&
				versionResult.latest_version
			) {
				updateAvailable = true;
				latestVersionNumber = versionResult.latest_version;
			} else {
				updateAvailable = false;
				latestVersionNumber = null;
				updateCheckDone = true; // Show "Up to date" message
				setTimeout(() => {
					updateCheckDone = false;
				}, 5000); // Clear after 5 seconds
			}
		} catch (error) {
			log.error("Failed to check for updates:", error);
			updateCheckError =
				error instanceof Error
					? error.message
					: "Failed to check for updates";
		} finally {
			isCheckingUpdates = false;
		}
	}

	// AI Provider functions
	async function loadAIConfig() {
		if (aiConfig !== null && !isLoadingAIConfig) {
			showAISection = !showAISection;
			return;
		}

		isLoadingAIConfig = true;
		aiConfigError = null;

		try {
			const [configResult, gpuResult] = await Promise.all([
				getAIConfig(),
				getGPUInfo(),
			]);
			aiConfig = configResult;
			gpuInfo = gpuResult;

			// Initialize editable form state from loaded config
			editableAIConfig = {
				active_provider: configResult.active_provider,
				fallback_to_cloud: configResult.fallback_to_cloud,
				fallback_provider: configResult.fallback_provider,
				ollama: { ...configResult.ollama },
				openai: { ...configResult.openai, api_key: configResult.openai.has_api_key ? "********" : null },
				anthropic: { ...configResult.anthropic, api_key: configResult.anthropic.has_api_key ? "********" : null },
				litellm: { ...configResult.litellm },
			};

			showAISection = true;
			aiConfigDirty = false;
		} catch (error) {
			log.error("Failed to load AI config:", error);
			aiConfigError =
				error instanceof Error
					? error.message
					: "Failed to load AI configuration";
		} finally {
			isLoadingAIConfig = false;
		}
	}

	async function saveAIConfig() {
		isSavingAIConfig = true;
		aiConfigError = null;
		connectionTestResult = null;

		try {
			// If Ollama is active, test connection first
			if (editableAIConfig.active_provider === "ollama" && editableAIConfig.ollama.enabled) {
				const testResult = await testProviderConnection("ollama", {
					url: editableAIConfig.ollama.url,
					model: editableAIConfig.ollama.model,
				});

				if (!testResult.success) {
					connectionTestResult = {
						success: false,
						message: `Ollama: ${testResult.message}`,
					};
					// Still save but show warning
				} else {
					connectionTestResult = {
						success: true,
						message: testResult.message,
					};
				}
			}

			const result = await updateAIConfig(editableAIConfig);
			aiConfig = result;
			aiConfigDirty = false;

			// Update editable state with response (handles masked keys)
			editableAIConfig = {
				active_provider: result.active_provider,
				fallback_to_cloud: result.fallback_to_cloud,
				fallback_provider: result.fallback_provider,
				ollama: { ...result.ollama },
				openai: { ...result.openai, api_key: result.openai.has_api_key ? "********" : null },
				anthropic: { ...result.anthropic, api_key: result.anthropic.has_api_key ? "********" : null },
				litellm: { ...result.litellm },
			};

			if (!connectionTestResult) {
				connectionTestResult = {
					success: true,
					message: "Configuration saved successfully",
				};
			}

			// Clear success message after 5 seconds
			setTimeout(() => {
				if (connectionTestResult?.success) {
					connectionTestResult = null;
				}
			}, 5000);
		} catch (error) {
			log.error("Failed to save AI config:", error);
			aiConfigError =
				error instanceof Error
					? error.message
					: "Failed to save configuration";
		} finally {
			isSavingAIConfig = false;
		}
	}

	async function testConnectionHandler(provider: string) {
		isTestingConnection = true;
		connectionTestResult = null;

		const providerConfig = provider === "ollama"
			? { url: editableAIConfig.ollama.url, model: editableAIConfig.ollama.model }
			: provider === "openai"
				? { api_key: editableAIConfig.openai.api_key, model: editableAIConfig.openai.model }
				: provider === "anthropic"
					? { api_key: editableAIConfig.anthropic.api_key, model: editableAIConfig.anthropic.model }
					: { model: editableAIConfig.litellm.model };

		try {
			const result = await testProviderConnection(provider, providerConfig);
			connectionTestResult = {
				success: result.success,
				message: result.message,
			};
		} catch (error) {
			log.error(`Failed to test ${provider} connection:`, error);
			connectionTestResult = {
				success: false,
				message: error instanceof Error ? error.message : "Test failed",
			};
		} finally {
			isTestingConnection = false;
			// Clear result after 5 seconds
			setTimeout(() => {
				connectionTestResult = null;
			}, 5000);
		}
	}

	function markAIConfigDirty() {
		aiConfigDirty = true;
	}

	function formatBytes(bytes: number): string {
		if (bytes === 0) return "0 B";
		const k = 1024;
		const sizes = ["B", "KB", "MB", "GB", "TB"];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
	}

	async function loadFieldPrefs() {
		if (effectiveDefaults !== null || isLoadingFieldPrefs) {
			showFieldPrefs = !showFieldPrefs;
			return;
		}

		isLoadingFieldPrefs = true;
		fieldPrefsError = null;

		try {
			// Load preferences and effective defaults in parallel (labels already loaded in onMount)
			const [prefsResult, defaultsResult] = await Promise.all([
				fieldPreferences.get(),
				fieldPreferences.getEffectiveDefaults(),
			]);
			prefs = prefsResult;
			effectiveDefaults = defaultsResult;
			showFieldPrefs = true;
		} catch (error) {
			log.error("Failed to load field preferences:", error);
			fieldPrefsError =
				error instanceof Error
					? error.message
					: "Failed to load preferences";
		} finally {
			isLoadingFieldPrefs = false;
		}
	}

	async function saveFieldPrefs() {
		saveFieldPrefsState = "saving";
		fieldPrefsError = null;

		try {
			const result = await fieldPreferences.update(prefs);
			prefs = result;

			// Show success state
			saveFieldPrefsState = "success";

			// Reset to idle after showing success
			setTimeout(() => {
				saveFieldPrefsState = "idle";
			}, 2000);
		} catch (error) {
			log.error("Failed to save field preferences:", error);
			fieldPrefsError =
				error instanceof Error
					? error.message
					: "Failed to save preferences";
			saveFieldPrefsState = "error";
			// Reset error state after a delay
			setTimeout(() => {
				saveFieldPrefsState = "idle";
			}, 3000);
		}
	}

	async function resetFieldPrefs() {
		saveFieldPrefsState = "saving";
		fieldPrefsError = null;

		try {
			const result = await fieldPreferences.reset();
			prefs = result;
			promptPreview = null; // Clear preview when resetting

			// Show success state
			saveFieldPrefsState = "success";

			// Reset to idle after showing success
			setTimeout(() => {
				saveFieldPrefsState = "idle";
			}, 2000);
		} catch (error) {
			log.error("Failed to reset field preferences:", error);
			fieldPrefsError =
				error instanceof Error
					? error.message
					: "Failed to reset preferences";
			saveFieldPrefsState = "error";
			// Reset error state after a delay
			setTimeout(() => {
				saveFieldPrefsState = "idle";
			}, 3000);
		}
	}

	function handleFieldInput(key: keyof FieldPreferences, value: string) {
		prefs[key] = value.trim() || null;
		promptPreview = null; // Clear preview when editing
	}

	async function loadPromptPreview() {
		// If already showing, just toggle off
		if (showPromptPreview) {
			showPromptPreview = false;
			return;
		}

		// If we have cached preview, just show it
		if (promptPreview) {
			showPromptPreview = true;
			return;
		}

		// Otherwise fetch the preview
		isLoadingPreview = true;

		try {
			const result = await fieldPreferences.getPromptPreview(prefs);
			promptPreview = result.prompt;
			showPromptPreview = true;
		} catch (error) {
			log.error("Failed to load prompt preview:", error);
			fieldPrefsError =
				error instanceof Error
					? error.message
					: "Failed to load preview";
		} finally {
			isLoadingPreview = false;
		}
	}

	// Generate env vars string from current preferences
	function generateEnvVars(prefsToExport: FieldPreferences): string {
		const envMapping: Record<keyof FieldPreferences, string> = {
			output_language: "HBC_AI_OUTPUT_LANGUAGE",
			default_label_id: "HBC_AI_DEFAULT_LABEL_ID",
			name: "HBC_AI_NAME",
			description: "HBC_AI_DESCRIPTION",
			quantity: "HBC_AI_QUANTITY",
			manufacturer: "HBC_AI_MANUFACTURER",
			model_number: "HBC_AI_MODEL_NUMBER",
			serial_number: "HBC_AI_SERIAL_NUMBER",
			purchase_price: "HBC_AI_PURCHASE_PRICE",
			purchase_from: "HBC_AI_PURCHASE_FROM",
			notes: "HBC_AI_NOTES",
			naming_examples: "HBC_AI_NAMING_EXAMPLES",
		};

		const lines: string[] = [];
		for (const [key, envName] of Object.entries(envMapping)) {
			const value = prefsToExport[key as keyof FieldPreferences];
			if (value) {
				// Escape quotes and wrap in quotes if contains special chars
				const escaped = value.replace(/"/g, '\\"');
				lines.push(`${envName}="${escaped}"`);
			}
		}

		return lines.length > 0
			? lines.join("\n")
			: "# No customizations configured";
	}

	async function toggleEnvExport() {
		if (showEnvExport) {
			showEnvExport = false;
			return;
		}

		// Fetch fresh prefs for export
		isLoadingExport = true;
		try {
			exportPrefs = await fieldPreferences.get();
			showEnvExport = true;
		} catch (error) {
			log.error("Failed to load preferences for export:", error);
			fieldPrefsError =
				error instanceof Error
					? error.message
					: "Failed to load preferences";
		} finally {
			isLoadingExport = false;
		}
	}

	async function copyEnvVars() {
		if (!exportPrefs) return;
		const envVars = generateEnvVars(exportPrefs);
		try {
			await navigator.clipboard.writeText(envVars);
			envCopied = true;
			setTimeout(() => {
				envCopied = false;
			}, 2000);
		} catch (error) {
			log.warn("Failed to copy to clipboard:", error);
		}
	}
>>>>>>> 5ceb0f9 (feat(ai-config): add multi-provider AI settings with editable UI)
</script>

<svelte:head>
	<title>Settings - Homebox Companion</title>
</svelte:head>

<div class="animate-in space-y-6">
	<div>
		<h1 class="text-h1 font-bold text-neutral-100">Settings</h1>
		<p class="mt-1 text-body-sm text-neutral-400">App configuration and information</p>
	</div>

<<<<<<< HEAD
	{#if settingsService.errors.init}
		<div class="card border-error-500/30 bg-error-500/10">
			<div class="flex items-start gap-3">
				<svg
					class="mt-0.5 h-5 w-5 flex-shrink-0 text-error-500"
=======
	<!-- About Section -->
	<section class="card space-y-4">
		<h2
			class="text-body-lg font-semibold text-neutral-100 flex items-center gap-2"
		>
			<svg
				class="w-5 h-5 text-primary-400"
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

		<div class="space-y-3">
			<!-- Version -->
			<div class="flex items-center justify-between py-2">
				<span class="text-neutral-400">Version</span>
				<div class="flex items-center gap-2">
					<span class="text-neutral-100 font-mono"
						>{uiStore.appVersion || "Loading..."}</span
					>
					{#if updateAvailable && latestVersionNumber}
						<a
							href="https://github.com/Duelion/homebox-companion/releases/latest"
							target="_blank"
							rel="noopener noreferrer"
							class="inline-flex items-center gap-1 px-2 py-0.5 bg-warning-500/20 text-warning-500 rounded-full text-xs hover:bg-warning-500/30 transition-colors"
							title="Click to view release"
						>
							<svg
								class="w-3 h-3"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2"
							>
								<path
									d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
								/>
								<polyline points="7 10 12 15 17 10" />
								<line x1="12" y1="15" x2="12" y2="3" />
							</svg>
							<span>v{latestVersionNumber}</span>
						</a>
					{:else if updateCheckDone}
						<span
							class="inline-flex items-center gap-1 px-2 py-0.5 bg-success-500/20 text-success-500 rounded-full text-xs"
						>
							<svg
								class="w-3 h-3"
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
				</div>
			</div>

			<!-- Check for Updates Button -->
			<div class="py-2 border-t border-neutral-800">
				<button
					type="button"
					class="w-full py-2.5 px-4 bg-neutral-800/50 hover:bg-neutral-700 border border-neutral-700 rounded-xl text-neutral-400 hover:text-neutral-100 transition-all flex items-center justify-center gap-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
					onclick={checkForUpdates}
					disabled={isCheckingUpdates}
				>
					{#if isCheckingUpdates}
						<div
							class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"
						></div>
						<span>Checking for updates...</span>
					{:else}
						<svg
							class="w-4 h-4"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M23 4v6h-6M1 20v-6h6" />
							<path
								d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"
							/>
						</svg>
						<span>Check for Updates</span>
					{/if}
				</button>
				{#if updateCheckError}
					<p class="mt-2 text-xs text-error-500">
						{updateCheckError}
					</p>
				{/if}
			</div>

			<!-- Configuration Info -->
			{#if config}
				<!-- Homebox URL -->
				<div
					class="flex items-center justify-between py-2 border-t border-neutral-800"
				>
					<span class="text-neutral-400 flex-shrink-0"
						>Homebox URL</span
					>
					<div class="flex items-center gap-2 min-w-0">
						<a
							href={config.homebox_url}
							target="_blank"
							rel="noopener noreferrer"
							class="text-neutral-100 hover:text-primary-400 font-mono text-sm transition-colors flex items-center gap-1 truncate max-w-[200px]"
							title={config.homebox_url}
						>
							<span class="truncate">{config.homebox_url}</span>
							<svg
								class="w-3 h-3 opacity-70 flex-shrink-0"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"
								/>
								<polyline points="15 3 21 3 21 9" />
								<line x1="10" y1="14" x2="21" y2="3" />
							</svg>
						</a>
						{#if config.is_demo_mode}
							<span
								class="inline-flex items-center gap-1 px-2 py-0.5 bg-warning-500/20 text-warning-500 rounded-full text-xs flex-shrink-0"
							>
								Demo
							</span>
						{/if}
					</div>
				</div>

				<!-- AI Model -->
				<div
					class="flex items-center justify-between py-2 border-t border-neutral-800"
				>
					<span class="text-neutral-400">AI Model</span>
					<span class="text-neutral-100 font-mono text-sm"
						>{config.llm_model}</span
					>
				</div>

				<!-- Image Quality -->
				<div
					class="flex items-center justify-between py-2 border-t border-neutral-800"
				>
					<span class="text-neutral-400">Image Quality</span>
					<span class="text-neutral-100 font-mono text-sm capitalize"
						>{config.image_quality}</span
					>
				</div>
			{:else if isLoadingConfig}
				<div class="flex items-center justify-center py-4">
					<div
						class="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"
					></div>
				</div>
			{/if}

			<!-- GitHub Link -->
			<div class="pt-2 border-t border-neutral-800 space-y-2">
				<a
					href="https://github.com/Duelion/homebox-companion"
					target="_blank"
					rel="noopener noreferrer"
					class="flex items-center justify-between py-2 text-neutral-400 hover:text-neutral-100 transition-colors group"
				>
					<span class="flex items-center gap-2">
						<svg
							class="w-5 h-5"
							fill="currentColor"
							viewBox="0 0 16 16"
						>
							<path
								d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"
							/>
						</svg>
						<span>View on GitHub</span>
					</span>
					<svg
						class="w-4 h-4 opacity-50 group-hover:opacity-100 transition-opacity"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"
						/>
						<polyline points="15 3 21 3 21 9" />
						<line x1="10" y1="14" x2="21" y2="3" />
					</svg>
				</a>
				<p class="text-xs text-neutral-500 flex items-start gap-1.5">
					<svg
						class="w-3.5 h-3.5 mt-0.5 flex-shrink-0"
						fill="currentColor"
						viewBox="0 0 16 16"
					>
						<path
							d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25z"
						/>
					</svg>
					<span
						>Enjoying the app? Consider giving us a star on GitHub!</span
					>
				</p>
			</div>
		</div>
	</section>

	<!-- AI Provider Settings Section -->
	<section class="card space-y-4">
		<div class="flex items-center justify-between">
			<h2
				class="text-body-lg font-semibold text-neutral-100 flex items-center gap-2"
			>
				<svg
					class="w-5 h-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5"
					/>
				</svg>
				AI Provider Settings
			</h2>
			{#if showAISection && aiConfig}
				<div class="flex items-center gap-1.5">
					{#if aiConfigDirty}
						<span class="text-xs text-warning-500">Unsaved changes</span>
					{/if}
					<button
						type="button"
						class="p-2 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 rounded-lg transition-all min-w-[44px] min-h-[44px] flex items-center justify-center"
						onclick={loadAIConfig}
						disabled={isLoadingAIConfig}
						title="Refresh"
						aria-label="Refresh"
					>
						<svg
							class="w-5 h-5 {isLoadingAIConfig ? 'animate-spin' : ''}"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M23 4v6h-6M1 20v-6h6" />
							<path
								d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"
							/>
						</svg>
					</button>
				</div>
			{/if}
		</div>

		<p class="text-body-sm text-neutral-400">
			Configure AI providers for image analysis. Choose between local processing (Ollama) or cloud services.
		</p>

		<button
			type="button"
			class="w-full py-3 px-4 bg-neutral-800/50 hover:bg-neutral-700 border border-neutral-700 rounded-xl text-neutral-400 hover:text-neutral-100 transition-all flex items-center gap-2"
			onclick={loadAIConfig}
			disabled={isLoadingAIConfig}
		>
			{#if isLoadingAIConfig}
				<div
					class="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"
				></div>
				<span>Loading...</span>
			{:else}
				<svg
					class="w-5 h-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" />
				</svg>
				<span>Configure AI Providers</span>
				<svg
					class="w-4 h-4 ml-auto transition-transform {showAISection
						? 'rotate-180'
						: ''}"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<polyline points="6 9 12 15 18 9" />
				</svg>
			{/if}
		</button>

		{#if showAISection}
			{#if aiConfigError}
				<div
					class="p-4 bg-error-500/10 border border-error-500/30 rounded-xl text-error-500 text-sm"
				>
					{aiConfigError}
				</div>
			{:else if aiConfig}
				<div class="space-y-4 mt-3">
					<!-- Active Provider Selection -->
					<div class="p-4 bg-neutral-800/50 rounded-xl border border-neutral-700 space-y-4">
						<h3 class="text-sm font-semibold text-neutral-100 flex items-center gap-2">
							<svg class="w-4 h-4 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
								<path d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
							Active Provider
						</h3>
						<select
							class="w-full px-3 py-2.5 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
							bind:value={editableAIConfig.active_provider}
							onchange={markAIConfigDirty}
						>
							<option value="ollama">Ollama (Local)</option>
							<option value="openai">OpenAI</option>
							<option value="anthropic">Anthropic (Claude)</option>
							<option value="litellm">Cloud (LiteLLM) - Original</option>
						</select>
						<p class="text-xs text-neutral-500">
							{#if editableAIConfig.active_provider === "ollama"}
								Local AI processing for maximum privacy. Requires Ollama running on your system.
							{:else if editableAIConfig.active_provider === "openai"}
								Use OpenAI's GPT-4 Vision models. Requires an API key.
							{:else if editableAIConfig.active_provider === "anthropic"}
								Use Anthropic's Claude models. Requires an API key.
							{:else}
								Default cloud provider (original). No API key required.
							{/if}
						</p>
					</div>

					<!-- Ollama Configuration -->
					<div class="p-4 bg-neutral-800/50 rounded-xl border border-neutral-700 space-y-4">
						<div class="flex items-center justify-between">
							<h3 class="text-sm font-semibold text-neutral-100 flex items-center gap-2">
								<svg class="w-4 h-4 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
									<path d="M5.25 14.25h13.5m-13.5 0a3 3 0 01-3-3m3 3a3 3 0 100 6h13.5a3 3 0 100-6m-16.5-3a3 3 0 013-3h13.5a3 3 0 013 3m-19.5 0a4.5 4.5 0 01.9-2.7L5.737 5.1a3.375 3.375 0 012.7-1.35h7.126c1.062 0 2.062.5 2.7 1.35l2.587 3.45a4.5 4.5 0 01.9 2.7m0 0a3 3 0 01-3 3m0 3h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008zm-3 6h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008z" />
								</svg>
								Ollama (Local AI)
							</h3>
							<label class="flex items-center gap-2 cursor-pointer">
								<input
									type="checkbox"
									class="w-4 h-4 rounded border-neutral-600 bg-neutral-900 text-primary-500 focus:ring-primary-500"
									bind:checked={editableAIConfig.ollama.enabled}
									onchange={markAIConfigDirty}
								/>
								<span class="text-sm text-neutral-400">Enabled</span>
							</label>
						</div>

						{#if editableAIConfig.ollama.enabled}
							<div class="grid gap-3">
								<div>
									<label class="block text-xs text-neutral-400 mb-1">Server URL</label>
									<input
										type="url"
										class="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
										bind:value={editableAIConfig.ollama.url}
										oninput={markAIConfigDirty}
										placeholder="http://localhost:11434"
									/>
								</div>
								<div>
									<label class="block text-xs text-neutral-400 mb-1">Model</label>
									<select
										class="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
										bind:value={editableAIConfig.ollama.model}
										onchange={markAIConfigDirty}
									>
										{#each OLLAMA_VISION_MODELS as model}
											<option value={model.id}>{model.name} ({model.vram})</option>
										{/each}
									</select>
								</div>
								<div>
									<label class="block text-xs text-neutral-400 mb-1">Timeout (seconds)</label>
									<input
										type="number"
										class="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
										bind:value={editableAIConfig.ollama.timeout}
										oninput={markAIConfigDirty}
										min="30"
										max="600"
									/>
								</div>
							</div>

							<!-- GPU Info for Ollama -->
							{#if gpuInfo}
								<div class="pt-3 mt-3 border-t border-neutral-700/50">
									<h4 class="text-xs font-semibold text-neutral-400 mb-2">System GPU</h4>
									{#if gpuInfo.detected}
										<div class="grid grid-cols-2 gap-2 text-xs">
											<span class="text-neutral-500">GPU:</span>
											<span class="text-neutral-300">{gpuInfo.name}</span>
											<span class="text-neutral-500">VRAM:</span>
											<span class="text-neutral-300">{gpuInfo.vram_gb.toFixed(1)} GB</span>
											<span class="text-neutral-500">Vision:</span>
											<span class="{gpuInfo.supports_vision_models ? 'text-success-500' : 'text-warning-500'}">
												{gpuInfo.supports_vision_models ? 'Supported' : 'Limited'}
											</span>
										</div>
									{:else}
										<p class="text-xs text-neutral-500">No GPU detected. Will use CPU.</p>
									{/if}
								</div>
							{/if}

							<button
								type="button"
								class="w-full py-2 px-3 bg-neutral-700/50 hover:bg-neutral-700 border border-neutral-600 rounded-lg text-neutral-300 hover:text-neutral-100 transition-all flex items-center justify-center gap-2 text-sm disabled:opacity-50"
								onclick={() => testConnectionHandler("ollama")}
								disabled={isTestingConnection}
							>
								{#if isTestingConnection}
									<div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
								{:else}
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
										<path d="M13 10V3L4 14h7v7l9-11h-7z" />
									</svg>
								{/if}
								<span>Test Ollama Connection</span>
							</button>
						{/if}
					</div>

					<!-- OpenAI Configuration -->
					<div class="p-4 bg-neutral-800/50 rounded-xl border border-neutral-700 space-y-4">
						<div class="flex items-center justify-between">
							<h3 class="text-sm font-semibold text-neutral-100 flex items-center gap-2">
								<svg class="w-4 h-4 text-green-400" viewBox="0 0 24 24" fill="currentColor">
									<path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364l2.0201-1.1638a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z" />
								</svg>
								OpenAI
							</h3>
							<label class="flex items-center gap-2 cursor-pointer">
								<input
									type="checkbox"
									class="w-4 h-4 rounded border-neutral-600 bg-neutral-900 text-primary-500 focus:ring-primary-500"
									bind:checked={editableAIConfig.openai.enabled}
									onchange={markAIConfigDirty}
								/>
								<span class="text-sm text-neutral-400">Enabled</span>
							</label>
						</div>

						{#if editableAIConfig.openai.enabled}
							<div class="grid gap-3">
								<div>
									<label class="block text-xs text-neutral-400 mb-1">API Key</label>
									<input
										type="password"
										class="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
										bind:value={editableAIConfig.openai.api_key}
										oninput={markAIConfigDirty}
										placeholder="sk-..."
									/>
									<p class="text-xs text-neutral-500 mt-1">Starts with sk-</p>
								</div>
								<div>
									<label class="block text-xs text-neutral-400 mb-1">Model</label>
									<select
										class="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
										bind:value={editableAIConfig.openai.model}
										onchange={markAIConfigDirty}
									>
										{#each OPENAI_MODELS as model}
											<option value={model.id}>{model.name}</option>
										{/each}
									</select>
								</div>
								<div>
									<label class="block text-xs text-neutral-400 mb-1">Max Tokens</label>
									<input
										type="number"
										class="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
										bind:value={editableAIConfig.openai.max_tokens}
										oninput={markAIConfigDirty}
										min="1024"
										max="16384"
									/>
								</div>
							</div>

							<button
								type="button"
								class="w-full py-2 px-3 bg-neutral-700/50 hover:bg-neutral-700 border border-neutral-600 rounded-lg text-neutral-300 hover:text-neutral-100 transition-all flex items-center justify-center gap-2 text-sm disabled:opacity-50"
								onclick={() => testConnectionHandler("openai")}
								disabled={isTestingConnection}
							>
								{#if isTestingConnection}
									<div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
								{:else}
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
										<path d="M13 10V3L4 14h7v7l9-11h-7z" />
									</svg>
								{/if}
								<span>Test API Key</span>
							</button>
						{/if}
					</div>

					<!-- Anthropic Configuration -->
					<div class="p-4 bg-neutral-800/50 rounded-xl border border-neutral-700 space-y-4">
						<div class="flex items-center justify-between">
							<h3 class="text-sm font-semibold text-neutral-100 flex items-center gap-2">
								<svg class="w-4 h-4 text-orange-400" viewBox="0 0 24 24" fill="currentColor">
									<path d="M17.304 3.541l-5.494 16.918h-3.114l5.494-16.918h3.114zm-10.608 0l5.494 16.918h3.114l-5.494-16.918h-3.114z" />
								</svg>
								Anthropic (Claude)
							</h3>
							<label class="flex items-center gap-2 cursor-pointer">
								<input
									type="checkbox"
									class="w-4 h-4 rounded border-neutral-600 bg-neutral-900 text-primary-500 focus:ring-primary-500"
									bind:checked={editableAIConfig.anthropic.enabled}
									onchange={markAIConfigDirty}
								/>
								<span class="text-sm text-neutral-400">Enabled</span>
							</label>
						</div>

						{#if editableAIConfig.anthropic.enabled}
							<div class="grid gap-3">
								<div>
									<label class="block text-xs text-neutral-400 mb-1">API Key</label>
									<input
										type="password"
										class="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
										bind:value={editableAIConfig.anthropic.api_key}
										oninput={markAIConfigDirty}
										placeholder="sk-ant-..."
									/>
									<p class="text-xs text-neutral-500 mt-1">Starts with sk-ant-</p>
								</div>
								<div>
									<label class="block text-xs text-neutral-400 mb-1">Model</label>
									<select
										class="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
										bind:value={editableAIConfig.anthropic.model}
										onchange={markAIConfigDirty}
									>
										{#each ANTHROPIC_MODELS as model}
											<option value={model.id}>{model.name}</option>
										{/each}
									</select>
								</div>
								<div>
									<label class="block text-xs text-neutral-400 mb-1">Max Tokens</label>
									<input
										type="number"
										class="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
										bind:value={editableAIConfig.anthropic.max_tokens}
										oninput={markAIConfigDirty}
										min="1024"
										max="16384"
									/>
								</div>
							</div>

							<button
								type="button"
								class="w-full py-2 px-3 bg-neutral-700/50 hover:bg-neutral-700 border border-neutral-600 rounded-lg text-neutral-300 hover:text-neutral-100 transition-all flex items-center justify-center gap-2 text-sm disabled:opacity-50"
								onclick={() => testConnectionHandler("anthropic")}
								disabled={isTestingConnection}
							>
								{#if isTestingConnection}
									<div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
								{:else}
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
										<path d="M13 10V3L4 14h7v7l9-11h-7z" />
									</svg>
								{/if}
								<span>Test API Key</span>
							</button>
						{/if}
					</div>

					<!-- LiteLLM (Cloud/Original) Configuration -->
					<div class="p-4 bg-neutral-800/50 rounded-xl border border-neutral-700 space-y-4">
						<div class="flex items-center justify-between">
							<h3 class="text-sm font-semibold text-neutral-100 flex items-center gap-2">
								<svg class="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
									<path d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
								</svg>
								Cloud (LiteLLM) - Original Provider
							</h3>
							<label class="flex items-center gap-2 cursor-pointer">
								<input
									type="checkbox"
									class="w-4 h-4 rounded border-neutral-600 bg-neutral-900 text-primary-500 focus:ring-primary-500"
									bind:checked={editableAIConfig.litellm.enabled}
									onchange={markAIConfigDirty}
								/>
								<span class="text-sm text-neutral-400">Enabled</span>
							</label>
						</div>

						<p class="text-xs text-neutral-500">
							This is the original cloud AI provider included with the app. No API key required - uses the app developer's infrastructure.
						</p>

						{#if editableAIConfig.litellm.enabled}
							<div>
								<label class="block text-xs text-neutral-400 mb-1">Model</label>
								<input
									type="text"
									class="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
									bind:value={editableAIConfig.litellm.model}
									oninput={markAIConfigDirty}
									placeholder="gpt-4o"
								/>
							</div>
						{/if}
					</div>

					<!-- Fallback Settings -->
					<div class="p-4 bg-neutral-800/50 rounded-xl border border-neutral-700 space-y-4">
						<h3 class="text-sm font-semibold text-neutral-100 flex items-center gap-2">
							<svg class="w-4 h-4 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
								<path d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
							</svg>
							Fallback Settings
						</h3>

						<label class="flex items-center gap-3 cursor-pointer">
							<input
								type="checkbox"
								class="w-4 h-4 rounded border-neutral-600 bg-neutral-900 text-primary-500 focus:ring-primary-500"
								bind:checked={editableAIConfig.fallback_to_cloud}
								onchange={markAIConfigDirty}
							/>
							<div>
								<span class="text-sm text-neutral-100">Enable fallback</span>
								<p class="text-xs text-neutral-500">If primary provider fails, try a backup provider</p>
							</div>
						</label>

						{#if editableAIConfig.fallback_to_cloud}
							<div>
								<label class="block text-xs text-neutral-400 mb-1">Fallback Provider</label>
								<select
									class="w-full px-3 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-neutral-100 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
									bind:value={editableAIConfig.fallback_provider}
									onchange={markAIConfigDirty}
								>
									<option value="litellm">Cloud (LiteLLM)</option>
									<option value="ollama">Ollama</option>
									<option value="openai">OpenAI</option>
									<option value="anthropic">Anthropic</option>
								</select>
							</div>
						{/if}
					</div>

					<!-- Test Result -->
					{#if connectionTestResult}
						<div
							class="p-3 rounded-xl text-sm {connectionTestResult.success
								? 'bg-success-500/10 border border-success-500/30 text-success-500'
								: 'bg-error-500/10 border border-error-500/30 text-error-500'}"
						>
							<div class="flex items-center gap-2">
								{#if connectionTestResult.success}
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
										<polyline points="20 6 9 17 4 12" />
									</svg>
								{:else}
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
										<path d="M18 6L6 18M6 6l12 12" />
									</svg>
								{/if}
								<span>{connectionTestResult.message}</span>
							</div>
						</div>
					{/if}

					<!-- Save Button -->
					<button
						type="button"
						class="w-full py-3 px-4 bg-primary-600 hover:bg-primary-500 disabled:bg-primary-800 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
						onclick={saveAIConfig}
						disabled={isSavingAIConfig || !aiConfigDirty}
					>
						{#if isSavingAIConfig}
							<div class="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
							<span>Saving...</span>
						{:else}
							<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
								<path d="M4.5 12.75l6 6 9-13.5" />
							</svg>
							<span>Save Configuration</span>
						{/if}
					</button>

					<!-- Configuration Tip -->
					<div class="p-3 bg-neutral-800/30 rounded-xl border border-neutral-700/50">
						<p class="text-xs text-neutral-500">
							Tip: When using Ollama, the connection is tested automatically on save. API keys for OpenAI and Anthropic are validated for correct format.
						</p>
					</div>
				</div>
			{/if}
		{/if}
	</section>

	<!-- Logs Section -->
	<section class="card space-y-4">
		<div class="flex items-center justify-between">
			<h2
				class="text-body-lg font-semibold text-neutral-100 flex items-center gap-2"
			>
				<svg
					class="w-5 h-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
					/>
					<polyline points="14 2 14 8 20 8" />
					<line x1="16" y1="13" x2="8" y2="13" />
					<line x1="16" y1="17" x2="8" y2="17" />
					<polyline points="10 9 9 9 8 9" />
				</svg>
				Application Logs
			</h2>
			{#if showLogs && logs}
				<div class="flex items-center gap-1.5">
					<button
						type="button"
						class="p-2 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 rounded-lg transition-all min-w-[44px] min-h-[44px] flex items-center justify-center"
						onclick={refreshLogs}
						disabled={isLoadingLogs}
						title="Refresh logs"
						aria-label="Refresh logs"
					>
						<svg
							class="w-5 h-5 {isLoadingLogs
								? 'animate-spin'
								: ''}"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M23 4v6h-6M1 20v-6h6" />
							<path
								d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"
							/>
						</svg>
					</button>
					<button
						type="button"
						class="p-2 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 rounded-lg transition-all min-w-[44px] min-h-[44px] flex items-center justify-center"
						onclick={handleDownloadLogs}
						disabled={!logs.filename}
						title="Download full log file"
						aria-label="Download logs"
					>
						<svg
							class="w-5 h-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path
								d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
							/>
							<polyline points="7 10 12 15 17 10" />
							<line x1="12" y1="15" x2="12" y2="3" />
						</svg>
					</button>
					<button
						type="button"
						class="p-2 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 rounded-lg transition-all min-w-[44px] min-h-[44px] flex items-center justify-center"
						onclick={() => (logsFullscreen = true)}
						title="Expand fullscreen"
						aria-label="View logs fullscreen"
					>
						<svg
							class="w-5 h-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
						</svg>
					</button>
				</div>
			{/if}
		</div>

		<p class="text-body-sm text-neutral-400">
			View recent application logs for debugging and reference.
		</p>

		<button
			type="button"
			class="w-full py-3 px-4 bg-neutral-800/50 hover:bg-neutral-700 border border-neutral-700 rounded-xl text-neutral-400 hover:text-neutral-100 transition-all flex items-center gap-2"
			onclick={loadLogs}
			disabled={isLoadingLogs}
		>
			{#if isLoadingLogs}
				<div
					class="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"
				></div>
				<span>Loading logs...</span>
			{:else}
				<svg
					class="w-5 h-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
					/>
					<polyline points="14 2 14 8 20 8" />
					<line x1="16" y1="13" x2="8" y2="13" />
					<line x1="16" y1="17" x2="8" y2="17" />
					<polyline points="10 9 9 9 8 9" />
				</svg>
				<span>Show Logs</span>
				<svg
					class="w-4 h-4 ml-auto transition-transform {showLogs
						? 'rotate-180'
						: ''}"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<polyline points="6 9 12 15 18 9" />
				</svg>
			{/if}
		</button>

		{#if showLogs}
			{#if logsError}
				<div
					class="p-4 bg-error-500/10 border border-error-500/30 rounded-xl text-error-500 text-sm"
				>
					{logsError}
				</div>
			{:else if logs}
				<div class="mt-3 space-y-2">
					{#if logs.filename}
						<div
							class="flex items-center justify-between text-xs text-neutral-500"
						>
							<span>{logs.filename}</span>
							<span>
								{logs.truncated
									? `Last ${logs.total_lines > 300 ? 300 : logs.total_lines} of ${logs.total_lines}`
									: `${logs.total_lines}`} lines
							</span>
						</div>
					{/if}
					<div
						class="bg-neutral-950 rounded-xl border border-neutral-700 overflow-hidden"
					>
						<pre
							bind:this={logsContainer}
							class="p-4 text-xs font-mono text-neutral-400 overflow-x-auto max-h-80 overflow-y-auto whitespace-pre-wrap break-all">{@html colorizedLogs()}</pre>
					</div>
				</div>
			{/if}
		{/if}
	</section>

	<!-- Frontend Logs Section -->
	<section class="card space-y-4">
		<div class="flex items-center justify-between">
			<h2
				class="text-body-lg font-semibold text-neutral-100 flex items-center gap-2"
			>
				<svg
					class="w-5 h-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
					/>
				</svg>
				Frontend Logs
			</h2>
			{#if showFrontendLogs && frontendLogs.length > 0}
				<div class="flex items-center gap-1.5">
					<button
						type="button"
						class="p-2 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 rounded-lg transition-all min-w-[44px] min-h-[44px] flex items-center justify-center"
						onclick={refreshFrontendLogs}
						title="Refresh logs"
						aria-label="Refresh logs"
					>
						<svg
							class="w-5 h-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M23 4v6h-6M1 20v-6h6" />
							<path
								d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"
							/>
						</svg>
					</button>
					<button
						type="button"
						class="p-2 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 rounded-lg transition-all min-w-[44px] min-h-[44px] flex items-center justify-center"
						onclick={handleExportFrontendLogs}
						title="Export as JSON"
						aria-label="Export logs"
					>
						<svg
							class="w-5 h-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path
								d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
							/>
							<polyline points="7 10 12 15 17 10" />
							<line x1="12" y1="15" x2="12" y2="3" />
						</svg>
					</button>
					<button
						type="button"
						class="p-2 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 rounded-lg transition-all min-w-[44px] min-h-[44px] flex items-center justify-center"
						onclick={handleClearFrontendLogs}
						title="Clear logs"
						aria-label="Clear logs"
					>
						<svg
							class="w-5 h-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path
								d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
							/>
						</svg>
					</button>
					<button
						type="button"
						class="p-2 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 rounded-lg transition-all min-w-[44px] min-h-[44px] flex items-center justify-center"
						onclick={() => (frontendLogsFullscreen = true)}
						title="Expand fullscreen"
						aria-label="View logs fullscreen"
					>
						<svg
							class="w-5 h-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
						</svg>
					</button>
				</div>
			{/if}
		</div>

		<p class="text-body-sm text-neutral-400">
			View browser console logs stored in memory. Logs are cleared on page
			refresh.
		</p>

		<button
			type="button"
			class="w-full py-3 px-4 bg-neutral-800/50 hover:bg-neutral-700 border border-neutral-700 rounded-xl text-neutral-400 hover:text-neutral-100 transition-all flex items-center gap-2"
			onclick={loadFrontendLogs}
		>
			<svg
				class="w-5 h-5 text-primary-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path
					d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
				/>
			</svg>
			<span>Show Frontend Logs</span>
			<svg
				class="w-4 h-4 ml-auto transition-transform {showFrontendLogs
					? 'rotate-180'
					: ''}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<polyline points="6 9 12 15 18 9" />
			</svg>
		</button>

		{#if showFrontendLogs}
			{#if frontendLogs.length === 0}
				<div
					class="p-4 bg-neutral-800/50 border border-neutral-700 rounded-xl text-neutral-400 text-sm text-center"
				>
					No frontend logs available. Logs will appear here as you use
					the app.
				</div>
			{:else}
				<div class="mt-3 space-y-2">
					<div
						class="flex items-center justify-between text-xs text-neutral-500"
					>
						<span>In-memory buffer</span>
						<span
							>{frontendLogs.length}
							{frontendLogs.length === 1
								? "entry"
								: "entries"}</span
						>
					</div>
					<div
						class="bg-neutral-950 rounded-xl border border-neutral-700 overflow-hidden"
					>
						<pre
							bind:this={frontendLogsContainer}
							class="p-4 text-xs font-mono text-neutral-400 overflow-x-auto max-h-80 overflow-y-auto whitespace-pre-wrap break-all">{@html colorizedFrontendLogs()}</pre>
					</div>
				</div>
			{/if}
		{/if}
	</section>

	<!-- AI Output Configuration Section -->
	<section class="card space-y-4">
		<div class="flex items-center justify-between">
			<h2
				class="text-body-lg font-semibold text-neutral-100 flex items-center gap-2"
			>
				<svg
					class="w-5 h-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M12 6V4m0 2a2 2 0 1 0 0 4m0-4a2 2 0 1 1 0 4m-6 8a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4"
					/>
				</svg>
				Configure AI Output
			</h2>
			{#if showFieldPrefs && saveFieldPrefsState === "success"}
				<span
					class="inline-flex items-center gap-2 px-3 py-1.5 bg-success-500/20 text-success-500 rounded-full text-sm font-medium"
				>
					<svg
						class="w-4 h-4"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2.5"
					>
						<polyline points="20 6 9 17 4 12" />
					</svg>
					Saved
				</span>
			{/if}
		</div>

		<p class="text-body-sm text-neutral-400">
			Customize how the AI generates item data. Leave fields empty to use
			default behavior.
		</p>

		<button
			type="button"
			class="w-full py-3 px-4 bg-neutral-800/50 hover:bg-neutral-700 border border-neutral-700 rounded-xl text-neutral-400 hover:text-neutral-100 transition-all flex items-center gap-2"
			onclick={loadFieldPrefs}
			disabled={isLoadingFieldPrefs}
		>
			{#if isLoadingFieldPrefs}
				<div
					class="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"
				></div>
				<span>Loading...</span>
			{:else}
				<svg
					class="w-5 h-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M12 6V4m0 2a2 2 0 1 0 0 4m0-4a2 2 0 1 1 0 4m-6 8a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4"
					/>
				</svg>
				<span>Configure Fields</span>
				<svg
					class="w-4 h-4 ml-auto transition-transform {showFieldPrefs
						? 'rotate-180'
						: ''}"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<polyline points="6 9 12 15 18 9" />
				</svg>
			{/if}
		</button>

		{#if showFieldPrefs}
			{#if fieldPrefsError}
				<div
					class="p-4 bg-error-500/10 border border-error-500/30 rounded-xl text-error-500 text-sm"
				>
					{fieldPrefsError}
				</div>
			{/if}

			<!-- Output Language Setting -->
			<div
				class="p-4 bg-primary-600/10 rounded-xl border border-primary-500/20 space-y-3"
			>
				<div class="flex items-center gap-2">
					<svg
						class="w-5 h-5 text-primary-400"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path
							d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"
						/>
					</svg>
					<label
						for="output_language"
						class="font-semibold text-neutral-100"
						>Output Language</label
					>
				</div>
				<p class="text-xs text-neutral-400">
					Choose what language the AI should use for item names,
					descriptions, and notes.
				</p>
				<input
					type="text"
					id="output_language"
					value={prefs.output_language || ""}
					oninput={(e) =>
						handleFieldInput(
							"output_language",
							e.currentTarget.value,
						)}
					placeholder={effectiveDefaults
						? effectiveDefaults.output_language
						: "Loading..."}
					class="input"
				/>
				<div
					class="p-2 bg-warning-500/10 border border-warning-500/30 rounded-lg"
				>
					<p class="text-xs text-warning-500 flex items-start gap-2">
						<svg
							class="w-4 h-4 flex-shrink-0 mt-0.5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path
								d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
							/>
						</svg>
						<span
							><strong>Note:</strong> Field customization instructions
							below should still be written in English. Only the AI
							output will be in the configured language.</span
						>
					</p>
				</div>
			</div>

			<!-- Default Label Setting -->
			<div
				class="p-4 bg-primary-600/10 rounded-xl border border-primary-500/20 space-y-3"
			>
				<div class="flex items-center gap-2">
					<svg
						class="w-5 h-5 text-primary-400"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path
							d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
						/>
					</svg>
					<label
						for="default_label"
						class="font-semibold text-neutral-100"
						>Default Label</label
					>
				</div>
				<p class="text-xs text-neutral-400">
					Automatically tag all items created via Homebox Companion
					with this label.
				</p>
				<select
					id="default_label"
					value={prefs.default_label_id || ""}
					onchange={(e) => {
						prefs.default_label_id = e.currentTarget.value || null;
					}}
					class="input"
				>
					<option value="">No default label</option>
					{#each availableLabels as label}
						<option value={label.id}
							>{label.name}{effectiveDefaults?.default_label_id ===
							label.id
								? " (env default)"
								: ""}</option
						>
					{/each}
				</select>
				<p class="text-xs text-neutral-500">
					Useful for identifying items added through this app in your
					Homebox inventory.
				</p>
			</div>

			<!-- Field Customizations - 2-column grid on wider screens -->
			<div class="grid gap-4 sm:grid-cols-2">
				{#each fieldMeta as field}
					<div
						class="p-3 bg-neutral-800/50 rounded-lg border border-neutral-700/50 space-y-2"
					>
						<label
							for={field.key}
							class="block text-sm font-semibold text-neutral-100"
						>
							{field.label}
						</label>
						<div
							class="text-xs text-neutral-400 bg-neutral-950/50 px-2 py-1.5 rounded border border-neutral-700/30"
						>
							<span class="text-neutral-500">Default:</span>
							{effectiveDefaults?.[field.key] ?? "Loading..."}
						</div>
						<input
							type="text"
							id={field.key}
							value={prefs[field.key] || ""}
							oninput={(e) =>
								handleFieldInput(
									field.key,
									e.currentTarget.value,
								)}
							placeholder="Leave empty for default..."
							class="input text-sm"
						/>
						<p class="text-xs text-neutral-500 line-clamp-2">
							Example: {field.example}
						</p>
					</div>
				{/each}
			</div>

			<div class="flex gap-3 pt-2">
				<Button
					variant="primary"
					onclick={saveFieldPrefs}
					disabled={saveFieldPrefsState === "saving" ||
						saveFieldPrefsState === "success"}
				>
					{#if saveFieldPrefsState === "saving"}
						<div
							class="w-5 h-5 rounded-full border-2 border-white/30 border-t-white animate-spin"
						></div>
						<span>Saving...</span>
					{:else if saveFieldPrefsState === "success"}
						<div
							class="w-8 h-8 flex items-center justify-center bg-success-500/20 rounded-full"
						>
							<svg
								class="w-5 h-5 text-success-500"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2.5"
							>
								<polyline points="20 6 9 17 4 12" />
							</svg>
						</div>
						<span>Saved!</span>
					{:else}
						<svg
							class="w-4 h-4"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M5 13l4 4L19 7"
							/>
						</svg>
						<span>Save</span>
					{/if}
				</Button>
				<Button
					variant="secondary"
					onclick={resetFieldPrefs}
					disabled={saveFieldPrefsState === "saving" ||
						saveFieldPrefsState === "success"}
				>
					<svg
						class="w-4 h-4"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
						/>
					</svg>
					<span>Reset</span>
				</Button>
			</div>
		{/if}

		<!-- Docker Persistence Warning & Export - Moved up for visibility -->
		<div
			class="p-4 bg-warning-500/10 border border-warning-500/30 rounded-xl space-y-3"
		>
			<div class="flex items-start gap-2">
				<svg
					class="w-5 h-5 text-warning-500 flex-shrink-0 mt-0.5"
>>>>>>> 5ceb0f9 (feat(ai-config): add multi-provider AI settings with editable UI)
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
					/>
				</svg>
				<div>
					<p class="font-medium text-error-500">Failed to load settings</p>
					<p class="mt-1 text-sm text-neutral-400">{settingsService.errors.init}</p>
					<button
						type="button"
						class="mt-2 text-sm text-primary-400 underline hover:text-primary-300"
						onclick={() => settingsService.initialize()}
					>
						Try again
					</button>
				</div>
			</div>
		</div>
	{/if}

	<AccountSection />
	<AboutSection />
	<FieldPrefsSection />
	<LogsSection />

	<!-- Bottom spacing for nav -->
	<div class="h-4"></div>
</div>
