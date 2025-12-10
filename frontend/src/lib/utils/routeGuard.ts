/**
 * Centralized route guards for authentication and workflow state
 *
 * This module provides a single place to define navigation guards,
 * ensuring consistent access control across all protected pages.
 */

import { goto } from '$app/navigation';
import { get } from 'svelte/store';
import { isAuthenticated } from '$lib/stores/auth';
import { scanWorkflow } from '$lib/workflows/scan.svelte';
import type { ScanStatus } from '$lib/types';

/**
 * Route requirements configuration
 */
export interface RouteRequirements {
	/** Require authentication (default: true) */
	auth?: boolean;
	/** Require a location to be selected */
	requireLocation?: boolean;
	/** Require specific workflow status(es) - if not met, redirects based on current status */
	allowedStatuses?: ScanStatus[];
}

/**
 * Result of a route guard check
 */
export interface GuardResult {
	/** Whether access is allowed */
	allowed: boolean;
	/** Redirect path if not allowed (null if allowed) */
	redirectTo: string | null;
}

/**
 * Map of workflow status to the appropriate page
 */
const STATUS_TO_ROUTE: Record<ScanStatus, string> = {
	idle: '/location',
	location: '/location',
	capturing: '/capture',
	analyzing: '/capture',
	reviewing: '/review',
	confirming: '/summary',
	submitting: '/summary',
	complete: '/success',
};

/**
 * Check route requirements and return whether access is allowed
 *
 * @param requirements - The requirements for the route
 * @returns GuardResult indicating if access is allowed and where to redirect if not
 */
export function checkRouteAccess(requirements: RouteRequirements): GuardResult {
	const { auth = true, requireLocation = false, allowedStatuses } = requirements;

	// Check authentication
	if (auth && !get(isAuthenticated)) {
		return { allowed: false, redirectTo: '/' };
	}

	const workflow = scanWorkflow;

	// Check location requirement
	if (requireLocation && !workflow.state.locationId) {
		return { allowed: false, redirectTo: '/location' };
	}

	// Check workflow status requirements
	if (allowedStatuses && allowedStatuses.length > 0) {
		const currentStatus = workflow.state.status;
		if (!allowedStatuses.includes(currentStatus)) {
			// Redirect to the appropriate page for current status
			const redirectTo = STATUS_TO_ROUTE[currentStatus];
			return { allowed: false, redirectTo };
		}
	}

	return { allowed: true, redirectTo: null };
}

/**
 * Apply route guard and redirect if necessary
 *
 * Call this in onMount to protect a page. Returns true if access is allowed,
 * false if a redirect was triggered.
 *
 * @param requirements - The requirements for the route
 * @returns true if access is allowed, false if redirecting
 *
 * @example
 * ```ts
 * onMount(() => {
 *   if (!applyRouteGuard({ requireLocation: true, allowedStatuses: ['capturing', 'analyzing'] })) {
 *     return;
 *   }
 *   // ... rest of onMount logic
 * });
 * ```
 */
export function applyRouteGuard(requirements: RouteRequirements): boolean {
	const result = checkRouteAccess(requirements);

	if (!result.allowed && result.redirectTo) {
		goto(result.redirectTo);
		return false;
	}

	return true;
}

/**
 * Pre-configured guards for common page types
 */
export const routeGuards = {
	/**
	 * Guard for the location selection page
	 * - Requires authentication
	 * - If workflow is in capturing/analyzing, redirect to capture
	 */
	location: (): boolean => {
		const result = checkRouteAccess({ auth: true });
		if (!result.allowed && result.redirectTo) {
			goto(result.redirectTo);
			return false;
		}

		// If workflow already has a location and is in capturing/analyzing state
		const workflow = scanWorkflow;
		if (workflow.state.locationId) {
			const status = workflow.state.status;
			if (status === 'capturing' || status === 'analyzing') {
				goto('/capture');
				return false;
			}
		}

		return true;
	},

	/**
	 * Guard for the capture page
	 * - Requires authentication
	 * - Requires location to be selected
	 * - If in reviewing state (analysis finished), redirect to review
	 */
	capture: (): boolean => {
		const result = checkRouteAccess({
			auth: true,
			requireLocation: true,
		});

		if (!result.allowed && result.redirectTo) {
			goto(result.redirectTo);
			return false;
		}

		// If we're in reviewing state (analysis finished while away), redirect to review
		const workflow = scanWorkflow;
		if (workflow.state.status === 'reviewing') {
			goto('/review');
			return false;
		}

		return true;
	},

	/**
	 * Guard for the review page
	 * - Requires authentication
	 * - Requires location to be selected
	 * - Must be in reviewing status
	 */
	review: (): boolean => {
		const result = checkRouteAccess({
			auth: true,
			requireLocation: true,
			allowedStatuses: ['reviewing'],
		});

		if (!result.allowed && result.redirectTo) {
			goto(result.redirectTo);
			return false;
		}

		return true;
	},

	/**
	 * Guard for the summary page
	 * - Requires authentication
	 * - Requires location to be selected
	 * - Must be in confirming or submitting status
	 */
	summary: (): boolean => {
		const result = checkRouteAccess({
			auth: true,
			requireLocation: true,
			allowedStatuses: ['confirming', 'submitting'],
		});

		if (!result.allowed && result.redirectTo) {
			goto(result.redirectTo);
			return false;
		}

		return true;
	},

	/**
	 * Guard for the success page
	 * - Requires authentication only
	 */
	success: (): boolean => {
		const result = checkRouteAccess({ auth: true });

		if (!result.allowed && result.redirectTo) {
			goto(result.redirectTo);
			return false;
		}

		return true;
	},
} as const;
