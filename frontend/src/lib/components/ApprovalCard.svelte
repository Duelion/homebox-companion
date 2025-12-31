<script lang="ts">
    /**
     * ApprovalCard - Displays a pending action awaiting user approval
     */
    import type { PendingApproval } from "../api/chat";
    import { chatStore } from "../stores/chat.svelte";

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

<div class="approval-card" class:expired={approval.is_expired}>
    <div class="header">
        <span class="icon">⚠️</span>
        <span class="title">Action Approval Required</span>
    </div>

    <div class="details">
        <div class="tool-name">
            <strong>Tool:</strong>
            <code>{approval.tool_name}</code>
        </div>

        {#if Object.keys(approval.parameters).length > 0}
            <div class="parameters">
                <strong>Parameters:</strong>
                <pre>{JSON.stringify(approval.parameters, null, 2)}</pre>
            </div>
        {/if}

        {#if expiresInSeconds !== null}
            <div class="expiry">
                {expiresInSeconds > 0
                    ? `Expires in ${expiresInSeconds}s`
                    : "Expired"}
            </div>
        {/if}
    </div>

    <div class="actions">
        <button
            class="reject"
            onclick={handleReject}
            disabled={isProcessing || approval.is_expired}
        >
            Reject
        </button>
        <button
            class="approve"
            onclick={handleApprove}
            disabled={isProcessing || approval.is_expired}
        >
            Approve
        </button>
    </div>
</div>

<style>
    .approval-card {
        background: var(--color-warning-bg, #fef3c7);
        border: 1px solid var(--color-warning-border, #f59e0b);
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }

    .approval-card.expired {
        opacity: 0.5;
        background: var(--color-surface, #f3f4f6);
        border-color: var(--color-border, #e5e7eb);
    }

    .header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.75rem;
    }

    .icon {
        font-size: 1.25rem;
    }

    .title {
        font-weight: 600;
        color: var(--color-warning-text, #92400e);
    }

    .details {
        font-size: 0.875rem;
        color: var(--color-text, #1f2937);
    }

    .tool-name {
        margin-bottom: 0.5rem;
    }

    code {
        background: rgba(0, 0, 0, 0.1);
        padding: 0.125rem 0.375rem;
        border-radius: 0.25rem;
        font-family: monospace;
    }

    .parameters pre {
        background: rgba(0, 0, 0, 0.05);
        padding: 0.5rem;
        border-radius: 0.25rem;
        margin: 0.25rem 0 0;
        font-size: 0.75rem;
        overflow-x: auto;
        max-height: 100px;
    }

    .expiry {
        color: var(--color-warning-text, #92400e);
        font-size: 0.75rem;
        margin-top: 0.5rem;
    }

    .actions {
        display: flex;
        gap: 0.5rem;
        margin-top: 0.75rem;
    }

    button {
        flex: 1;
        padding: 0.5rem 1rem;
        border: none;
        border-radius: 0.5rem;
        font-weight: 500;
        cursor: pointer;
        transition: opacity 0.2s;
    }

    button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .reject {
        background: var(--color-surface, #f3f4f6);
        color: var(--color-text, #1f2937);
    }

    .approve {
        background: var(--color-primary, #3b82f6);
        color: white;
    }

    .reject:hover:not(:disabled) {
        background: var(--color-border, #e5e7eb);
    }

    .approve:hover:not(:disabled) {
        background: var(--color-primary-dark, #2563eb);
    }
</style>
