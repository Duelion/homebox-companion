<script lang="ts">
	import Button from './Button.svelte';

	interface Props {
		onCamera: () => void;
		onUpload: () => void;
	}

	let { onCamera, onUpload }: Props = $props();
</script>

<div class="p-4 rounded-xl border-2 border-dashed border-border">
	<div class="flex justify-center gap-3">
		<Button variant="secondary" onclick={onCamera}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
				<circle cx="12" cy="13" r="4" />
			</svg>
			<span>Camera</span>
		</Button>
		<Button variant="secondary" onclick={onUpload}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
				<polyline points="17 8 12 3 7 8" />
				<line x1="12" y1="3" x2="12" y2="15" />
			</svg>
			<span>Upload</span>
		</Button>
	</div>
</div>



