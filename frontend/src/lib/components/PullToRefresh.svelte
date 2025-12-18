<script lang="ts">
    import type { Snippet } from "svelte";
    /**
     * Pull-to-refresh component for mobile touch devices.
     * Wraps content and triggers a refresh callback when user pulls down from top of page.
     * Only activates on touch events - desktop mouse scrolling is unaffected.
     */
    import { onMount, onDestroy } from "svelte";
    import { browser } from "$app/environment";

    interface Props {
        /**
         * Async function called when pull threshold is exceeded.
         * Component shows loading state until this promise resolves.
         */
        onRefresh: () => Promise<void>;
        /**
         * Distance in pixels user must pull to trigger refresh.
         * @default 80
         */
        threshold?: number;
        /**
         * Whether pull-to-refresh is enabled.
         * @default true
         */
        enabled?: boolean;
        /**
         * Content to wrap with pull-to-refresh functionality.
         */
        children: Snippet;
    }

    let {
        onRefresh,
        threshold = 80,
        enabled = true,
        children,
    }: Props = $props();

    // State
    let pullDistance = $state(0);
    let isRefreshing = $state(false);
    let isPulling = $state(false);

    // Touch tracking
    let startY = 0;
    let currentY = 0;

    // Progress towards threshold (0 to 1, capped)
    let progress = $derived(Math.min(pullDistance / threshold, 1));

    // Arrow rotation: stays pointing down (180deg) for first 40% of pull,
    // then rotates to point up (0deg) for the remaining 60%
    let arrowRotation = $derived.by(() => {
        if (progress < 0.4) return 180; // Stay pointing down
        // Map 0.4-1.0 progress to 180-0 degrees
        const rotationProgress = (progress - 0.4) / 0.6;
        return 180 - rotationProgress * 180;
    });

    // Visual states
    let shouldTrigger = $derived(pullDistance >= threshold);

    function handleTouchStart(e: TouchEvent) {
        if (!enabled || isRefreshing) return;

        // Only activate if at top of page (with tolerance for fractional scroll values)
        if (window.scrollY > 1) return;

        // Only handle single touch (ignore multi-touch gestures)
        if (e.touches.length !== 1) return;

        startY = e.touches[0].clientY;
        isPulling = true;
    }

    function handleTouchMove(e: TouchEvent) {
        if (!isPulling || !enabled || isRefreshing) return;

        // Ensure we're still in single-touch mode
        if (e.touches.length !== 1) {
            resetPullState();
            return;
        }

        currentY = e.touches[0].clientY;
        const diff = currentY - startY;

        // Only allow pulling down, not up
        if (diff > 0) {
            // Apply resistance - gets harder to pull as you go further
            pullDistance = Math.pow(diff, 0.8);

            // Prevent native scroll while pulling (with tolerance)
            if (window.scrollY <= 1 && diff > 10) {
                e.preventDefault();
            }
        } else {
            pullDistance = 0;
        }
    }

    async function handleTouchEnd() {
        if (!isPulling || !enabled) return;

        isPulling = false;

        if (shouldTrigger && !isRefreshing) {
            isRefreshing = true;
            // Keep indicator visible during refresh
            pullDistance = threshold;

            try {
                await onRefresh();
            } finally {
                isRefreshing = false;
                pullDistance = 0;
            }
        } else {
            // Snap back
            pullDistance = 0;
        }

        startY = 0;
        currentY = 0;
    }

    function handleTouchCancel() {
        // Reset state if touch is interrupted (e.g., by system gesture)
        resetPullState();
    }

    function resetPullState() {
        isPulling = false;
        pullDistance = 0;
        startY = 0;
        currentY = 0;
    }

    // Register global touch listeners for better gesture tracking
    onMount(() => {
        if (!browser) return;

        // Use passive: false to allow preventDefault on touchmove
        window.addEventListener("touchstart", handleTouchStart, {
            passive: true,
        });
        window.addEventListener("touchmove", handleTouchMove, {
            passive: false,
        });
        window.addEventListener("touchend", handleTouchEnd, { passive: true });
        window.addEventListener("touchcancel", handleTouchCancel, {
            passive: true,
        });
    });

    onDestroy(() => {
        if (!browser) return;

        window.removeEventListener("touchstart", handleTouchStart);
        window.removeEventListener("touchmove", handleTouchMove);
        window.removeEventListener("touchend", handleTouchEnd);
        window.removeEventListener("touchcancel", handleTouchCancel);
    });
</script>

<!-- 
    Pull indicator - fixed position with opacity-based visibility.
    Since the header uses glass/transparency, we can't rely solely on z-index.
    The arrow fades in as user pulls (opacity), while staying in place (no translateY).
    Combined with content sliding down, this creates a natural "reveal" effect.
-->
{#if enabled}
    <div
        class="fixed left-1/2 z-30 flex justify-center pointer-events-none transition-opacity duration-150"
        style="top: calc(4rem + env(safe-area-inset-top, 0px) + 0.75rem); transform: translateX(-50%); opacity: {Math.min(
            pullDistance / 40,
            1,
        )}"
    >
        <div
            class="w-10 h-10 rounded-full flex items-center justify-center shadow-lg transition-colors duration-200
				{isRefreshing || shouldTrigger
                ? 'bg-primary-600/20 border border-primary-500/50 text-primary-400'
                : 'bg-neutral-800/95 border border-neutral-600/50 text-neutral-400'}"
            style="transform: rotate({arrowRotation}deg)"
        >
            {#if isRefreshing}
                <!-- Spinner -->
                <svg
                    class="w-6 h-6 animate-spin"
                    fill="none"
                    viewBox="0 0 24 24"
                >
                    <circle
                        class="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        stroke-width="4"
                    ></circle>
                    <path
                        class="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                </svg>
            {:else}
                <!-- Arrow -->
                <svg
                    class="w-6 h-6"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    stroke-width="2"
                >
                    <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
            {/if}
        </div>
    </div>
{/if}

<!-- Content wrapper with pull transform -->
<div
    class="transition-transform duration-200 ease-out will-change-transform"
    style={pullDistance > 0 || isRefreshing
        ? `transform: translateY(${Math.min(pullDistance, threshold * 1.2)}px)`
        : ""}
>
    {@render children()}
</div>
