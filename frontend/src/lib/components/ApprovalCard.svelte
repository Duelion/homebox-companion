<script lang="ts">
    /**
     * ApprovalCard - Displays a pending action awaiting user approval
     */
    import type { PendingApproval } from "../api/chat";
    import { chatStore } from "../stores/chat.svelte";
    import Button from "./Button.svelte";

    interface Props {
        approval: PendingApproval;
    }

    let { approval }: Props = $props();

    let isProcessing = $state(false);
    let now = $state(Date.now());

    // Live countdown timer
    $effect(() => {
        if (!approval.expires_at) return;

        const interval = setInterval(() => {
            now = Date.now();
        }, 1000);

        return () => clearInterval(interval);
    });

    async function handleApprove() {
        isProcessing = true;
        try {
            await chatStore.approveAction(approval.id);
        } finally {
            isProcessing = false;
        }
    }

    async function handleReject() {
        isProcessing = true;
        try {
            await chatStore.rejectAction(approval.id);
        } finally {
            isProcessing = false;
        }
    }

    // Format expiry time - reactive countdown
    const expiresInSeconds = $derived.by(() => {
        if (!approval.expires_at) return null;
        const diff = new Date(approval.expires_at).getTime() - now;
        return Math.max(0, Math.floor(diff / 1000));
    });
</script>

<div
    class="overflow-hidden rounded-2xl border backdrop-blur-lg shadow-lg my-2 transition-all duration-200
        {approval.is_expired
        ? 'bg-neutral-900/60 border-neutral-700/50 opacity-60'
        : 'bg-warning-500/10 border-warning-500/30'}"
>
    <!-- Header -->
    <div
        class="flex items-center gap-3 px-4 py-3 border-b {approval.is_expired
            ? 'border-neutral-700/50'
            : 'border-warning-500/20'}"
    >
        <svg
            class="w-5 h-5 shrink-0 {approval.is_expired
                ? 'text-neutral-500'
                : 'text-warning-500'}"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
        >
            <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
        </svg>
        <span
            class="flex-1 text-sm font-semibold {approval.is_expired
                ? 'text-neutral-400'
                : 'text-warning-500'}"
        >
            Action Approval Required
        </span>
        {#if expiresInSeconds !== null}
            <span
                class="text-xs font-medium px-2 py-1 rounded-lg {approval.is_expired
                    ? 'bg-neutral-800 text-neutral-500'
                    : 'bg-warning-500/20 text-warning-500'}"
            >
                {expiresInSeconds > 0 ? `${expiresInSeconds}s` : "Expired"}
            </span>
        {/if}
    </div>

    <!-- Details -->
    <div class="px-4 py-3 space-y-3">
        <div class="flex items-center gap-2">
            <span
                class="text-xs font-medium text-neutral-400 uppercase tracking-wide"
                >Tool</span
            >
            <code
                class="px-2 py-1 text-sm font-mono bg-neutral-800/80 text-neutral-200 rounded-lg border border-neutral-700/50"
            >
                {approval.tool_name}
            </code>
        </div>

        {#if Object.keys(approval.parameters).length > 0}
            <div class="space-y-1.5">
                <span
                    class="text-xs font-medium text-neutral-400 uppercase tracking-wide"
                    >Parameters</span
                >
                <pre
                    class="p-3 text-xs font-mono bg-neutral-900/80 text-neutral-300 rounded-xl border border-neutral-700/50 overflow-x-auto max-h-24">{JSON.stringify(
                        approval.parameters,
                        null,
                        2,
                    )}</pre>
            </div>
        {/if}
    </div>

    <!-- Actions -->
    <div
        class="flex gap-2 px-4 py-3 border-t {approval.is_expired
            ? 'border-neutral-700/50'
            : 'border-warning-500/20'}"
    >
        <Button
            variant="secondary"
            size="sm"
            full
            disabled={isProcessing || approval.is_expired}
            loading={isProcessing}
            onclick={handleReject}
        >
            Reject
        </Button>
        <Button
            variant="warning"
            size="sm"
            full
            disabled={isProcessing || approval.is_expired}
            loading={isProcessing}
            onclick={handleApprove}
        >
            Approve
        </Button>
    </div>
</div>
