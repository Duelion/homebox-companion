<script lang="ts">
	import { locationPreferences } from '$lib/stores/locationPreferences.svelte';
</script>

<section class="card space-y-4">
	<h2 class="text-h3 font-semibold text-neutral-100">Location Selection</h2>
	<label class="flex cursor-pointer items-start gap-3">
		<input
			type="checkbox"
			checked={locationPreferences.showItemQuantities}
			onchange={(event) =>
				locationPreferences.set('showItemQuantities', event.currentTarget.checked)}
		/>
		<span>
			<span class="block font-medium text-neutral-100">Show total item quantities</span>
			<span class="block text-body-sm text-neutral-400">
				Includes items stored in sublocations and containers.
			</span>
		</span>
	</label>
	<label class="flex cursor-pointer items-start gap-3">
		<input
			type="checkbox"
			checked={locationPreferences.containerLocationsOnly}
			onchange={(event) =>
				locationPreferences.set('containerLocationsOnly', event.currentTarget.checked)}
		/>
		<span>
			<span class="block font-medium text-neutral-100"
				>Only pick containers marked as locations</span
			>
			<span class="block text-body-sm text-neutral-400">
				Use the Homebox container/location type to choose a sublocation as the destination.
			</span>
		</span>
	</label>
</section>
