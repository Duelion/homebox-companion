import type { scanWorkflow } from '../../src/lib/workflows/scan.svelte';

/** Compile-only contract: consumers edit drafts or call workflow methods. */
export function assertReadonlyScanViews(workflow: typeof scanWorkflow): void {
	// @ts-expect-error State transitions belong to workflow methods.
	workflow.state.status = 'idle';
	// @ts-expect-error Consumers cannot append captured photos.
	workflow.state.images.push(workflow.state.images[0]);
	// @ts-expect-error Captured photo options are readonly too.
	workflow.state.images[0].extraInstructions = 'changed';
	// @ts-expect-error Nested photo arrays cannot be reordered by consumers.
	workflow.state.images[0].additionalFiles?.reverse();
	// @ts-expect-error Confirmed records must be edited through the workflow.
	workflow.state.confirmedItems[0].name = 'changed';
	// @ts-expect-error Nested tag arrays are protected.
	workflow.state.detectedItems[0].tag_ids?.push('new-tag');
	// @ts-expect-error Status maps are readonly.
	workflow.state.imageStatuses[0] = 'pending';
	if (workflow.currentItem) {
		// @ts-expect-error The current item is a view, not an editable draft.
		workflow.currentItem.quantity = 3;
		if (workflow.currentItem.custom_fields) {
			// @ts-expect-error Custom field records are protected recursively.
			workflow.currentItem.custom_fields.Warranty = 'changed';
		}
	}
	if (workflow.submissionResult) {
		// @ts-expect-error Submission result arrays are readonly.
		workflow.submissionResult.createdItems.pop();
	}
	// Native file operations remain available on readonly views.
	void workflow.state.images[0].file.slice();
	workflow.clearError();
}
