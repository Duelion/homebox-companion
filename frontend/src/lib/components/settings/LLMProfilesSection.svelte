<script lang="ts">
	/**
	 * LLMProfilesSection - Manage AI model profiles.
	 *
	 * Allows users to configure multiple LLM providers and switch between them.
	 */
	import { onMount, onDestroy } from 'svelte';
	import { llmProfiles, type LLMProfile, type ProfileStatus } from '$lib/api/settings';
	import Button from '$lib/components/Button.svelte';
	import Modal from '$lib/components/Modal.svelte';

	// State
	let profiles = $state<LLMProfile[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let testingProfile = $state<string | null>(null);
	let testResult = $state<{ success: boolean; message: string } | null>(null);

	// Edit modal state
	let showModal = $state(false);
	let editingProfile = $state<LLMProfile | null>(null);
	let formName = $state('');
	let formModel = $state('');
	let formApiKey = $state('');
	let formApiBase = $state('');
	let formStatus = $state<ProfileStatus>('off');

	let saving = $state(false);
	let testTimeoutId: ReturnType<typeof setTimeout> | null = null;

	onMount(async () => {
		await loadProfiles();
	});

	onDestroy(() => {
		if (testTimeoutId) {
			clearTimeout(testTimeoutId);
		}
	});

	async function loadProfiles() {
		loading = true;
		error = null;
		try {
			const result = await llmProfiles.list();
			profiles = result.profiles;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load profiles';
		} finally {
			loading = false;
		}
	}

	function openCreateModal() {
		editingProfile = null;
		formName = '';
		formModel = '';
		formApiKey = '';
		formApiBase = '';
		formStatus = 'off';
		showModal = true;
	}

	function openEditModal(profile: LLMProfile) {
		editingProfile = profile;
		formName = profile.name;
		formModel = profile.model;
		formApiKey = ''; // Don't pre-fill - user must re-enter
		formApiBase = profile.api_base || '';
		formStatus = profile.status;
		showModal = true;
	}

	function closeModal() {
		showModal = false;
		editingProfile = null;
	}

	async function handleSave() {
		saving = true;
		error = null;
		try {
			if (editingProfile) {
				// Update existing
				await llmProfiles.update(editingProfile.name, {
					new_name: formName !== editingProfile.name ? formName : undefined,
					model: formModel,
					api_key: formApiKey || undefined, // undefined = keep existing, value = set new
					api_base: formApiBase || null,
					status: formStatus,
				});
			} else {
				// Create new
				await llmProfiles.create({
					name: formName,
					model: formModel,
					api_key: formApiKey || undefined,
					api_base: formApiBase || undefined,
					status: formStatus,
				});
			}
			await loadProfiles();
			closeModal();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save profile';
		} finally {
			saving = false;
		}
	}

	async function handleDelete(name: string) {
		if (!confirm(`Delete profile "${name}"?`)) return;
		error = null;
		try {
			await llmProfiles.delete(name);
			await loadProfiles();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete profile';
		}
	}

	async function handleActivate(name: string) {
		error = null;
		try {
			await llmProfiles.activate(name);
			await loadProfiles();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to activate profile';
		}
	}

	async function handleTest(name: string) {
		testingProfile = name;
		testResult = null;
		try {
			const result = await llmProfiles.test(name);
			testResult = result;
			// Auto-clear after 5 seconds
			if (testTimeoutId) clearTimeout(testTimeoutId);
			testTimeoutId = setTimeout(() => {
				if (testResult?.message === result.message) testResult = null;
				testTimeoutId = null;
			}, 5000);
		} catch (e) {
			testResult = { success: false, message: e instanceof Error ? e.message : 'Test failed' };
		} finally {
			testingProfile = null;
		}
	}

	function getStatusBadgeClass(status: ProfileStatus): string {
		switch (status) {
			case 'primary':
				return 'bg-success-500/20 text-success-400 border-success-500/30';
			case 'fallback':
				return 'bg-warning-500/20 text-warning-400 border-warning-500/30';
			default:
				return 'bg-neutral-700/50 text-neutral-400 border-neutral-600/50';
		}
	}
</script>

<section class="card space-y-4">
	<div class="flex items-center justify-between">
		<h2 class="text-body-lg flex items-center gap-2 font-semibold text-neutral-100">
			<svg
				class="text-primary-400 h-5 w-5"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path
					d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5"
				/>
			</svg>
			AI Models
		</h2>
		<Button variant="ghost" size="sm" onclick={openCreateModal}>
			<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
				<path d="M12 4v16m8-8H4" />
			</svg>
			Add
		</Button>
	</div>

	{#if error}
		<div class="text-error-400 border-error-500/30 bg-error-500/10 rounded-lg border p-3 text-sm">
			{error}
		</div>
	{/if}

	{#if testResult}
		<div
			class="rounded-lg border p-3 text-sm {testResult.success
				? 'text-success-400 border-success-500/30 bg-success-500/10'
				: 'text-error-400 border-error-500/30 bg-error-500/10'}"
		>
			{testResult.message}
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-8">
			<div
				class="border-primary-500 h-6 w-6 animate-spin rounded-full border-2 border-t-transparent"
			></div>
		</div>
	{:else if profiles.length === 0}
		<div class="rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-6 text-center">
			<p class="text-neutral-400">No AI models configured</p>
			<p class="mt-1 text-sm text-neutral-500">Add a model to enable AI features</p>
		</div>
	{:else}
		<div class="space-y-2">
			{#each profiles as profile (profile.name)}
				<div
					class="flex items-center gap-3 rounded-xl border border-neutral-700/50 bg-neutral-800/30 p-3"
				>
					<div class="min-w-0 flex-1">
						<div class="flex items-center gap-2">
							<span class="font-medium text-neutral-100">{profile.name}</span>
							<span
								class="rounded-full border px-2 py-0.5 text-xs capitalize {getStatusBadgeClass(
									profile.status
								)}"
							>
								{profile.status}
							</span>
						</div>
						<p class="mt-0.5 truncate text-sm text-neutral-400">{profile.model}</p>
						{#if profile.api_base}
							<p class="truncate text-xs text-neutral-500">{profile.api_base}</p>
						{/if}
					</div>
					<div class="flex items-center gap-1">
						{#if profile.status !== 'primary'}
							<button
								type="button"
								class="min-h-touch min-w-touch hover:text-success-400 rounded-lg p-2 text-neutral-400 hover:bg-neutral-700/50"
								title="Set as active profile"
								aria-label="Set as active profile"
								onclick={() => handleActivate(profile.name)}
							>
								<svg
									class="h-4 w-4"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									stroke-width="2"
								>
									<path d="M5 13l4 4L19 7" />
								</svg>
							</button>
						{/if}
						<button
							type="button"
							class="min-h-touch min-w-touch hover:text-primary-400 rounded-lg p-2 text-neutral-400 hover:bg-neutral-700/50"
							title="Test connection"
							aria-label="Test connection"
							disabled={testingProfile === profile.name}
							onclick={() => handleTest(profile.name)}
						>
							{#if testingProfile === profile.name}
								<div
									class="border-primary-500 h-4 w-4 animate-spin rounded-full border-2 border-t-transparent"
								></div>
							{:else}
								<svg
									class="h-4 w-4"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									stroke-width="2"
								>
									<path d="M13 10V3L4 14h7v7l9-11h-7z" />
								</svg>
							{/if}
						</button>
						<button
							type="button"
							class="min-h-touch min-w-touch rounded-lg p-2 text-neutral-400 hover:bg-neutral-700/50 hover:text-neutral-100"
							title="Edit"
							aria-label="Edit profile"
							onclick={() => openEditModal(profile)}
						>
							<svg
								class="h-4 w-4"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2"
							>
								<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
								<path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
							</svg>
						</button>
						<button
							type="button"
							class="min-h-touch min-w-touch hover:text-error-400 rounded-lg p-2 text-neutral-400 hover:bg-neutral-700/50"
							title="Delete"
							aria-label="Delete profile"
							onclick={() => handleDelete(profile.name)}
						>
							<svg
								class="h-4 w-4"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2"
							>
								<path
									d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
								/>
							</svg>
						</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</section>

<!-- Modal -->
<Modal
	bind:open={showModal}
	title={editingProfile ? 'Edit Profile' : 'New Profile'}
	onclose={closeModal}
>
	<form
		class="space-y-4"
		onsubmit={(e) => {
			e.preventDefault();
			handleSave();
		}}
	>
		<div>
			<label for="profile-name" class="mb-1 block text-sm font-medium text-neutral-300">
				Name
			</label>
			<input
				id="profile-name"
				type="text"
				bind:value={formName}
				required
				placeholder="e.g., openai-prod"
				class="input-sm"
			/>
		</div>

		<div>
			<label for="profile-model" class="mb-1 block text-sm font-medium text-neutral-300">
				Model
			</label>
			<input
				id="profile-model"
				type="text"
				bind:value={formModel}
				required
				placeholder="e.g., gpt-4o, ollama/mistral"
				class="input-sm"
			/>
			<p class="mt-1 text-xs text-neutral-500">
				LiteLLM model format: gpt-4o, claude-3-opus, ollama/mistral
			</p>
		</div>

		<div>
			<label for="profile-api-key" class="mb-1 block text-sm font-medium text-neutral-300">
				API Key
			</label>
			<input
				id="profile-api-key"
				type="password"
				bind:value={formApiKey}
				placeholder={editingProfile?.has_api_key ? '••••••••' : 'sk-...'}
				class="input-sm"
			/>
			{#if editingProfile}
				<p class="mt-1 text-xs text-neutral-500">Leave blank to keep existing key</p>
			{/if}
		</div>

		<div>
			<label for="profile-api-base" class="mb-1 block text-sm font-medium text-neutral-300">
				API Base URL <span class="text-neutral-500">(optional)</span>
			</label>
			<input
				id="profile-api-base"
				type="text"
				bind:value={formApiBase}
				placeholder="e.g., http://localhost:11434"
				class="input-sm"
			/>
		</div>

		<div>
			<label for="profile-status" class="mb-1 block text-sm font-medium text-neutral-300">
				Status
			</label>
			<select id="profile-status" bind:value={formStatus} class="input-sm">
				<option value="primary">Primary</option>
				<option value="fallback">Fallback</option>
				<option value="off">Off</option>
			</select>
			<p class="mt-1 text-xs text-neutral-500">
				{#if formStatus === 'primary'}
					Primary model used for all AI features
				{:else if formStatus === 'fallback'}
					Used automatically if the primary model fails
				{:else}
					Profile saved but not in use
				{/if}
			</p>
		</div>

		<div class="flex gap-3 pt-2">
			<Button variant="ghost" full onclick={closeModal} type="button">Cancel</Button>
			<Button variant="primary" full type="submit" disabled={saving}>
				{saving ? 'Saving...' : 'Save'}
			</Button>
		</div>
	</form>
</Modal>
