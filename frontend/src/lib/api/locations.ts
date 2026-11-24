/**
 * Locations API endpoints
 */

import { request } from './client';
import { locationPreferences } from '$lib/stores/locationPreferences.svelte';
import type {
	Location,
	LocationTreeNode,
	LocationCreateRequest,
	LocationUpdateRequest,
} from '../types';

export const locations = {
	list: (filterChildren?: boolean) => {
		const params = filterChildren !== undefined ? `?filterChildren=${filterChildren}` : '';
		return request<Location[]>(`/locations${params}`);
	},

	tree: (signal?: AbortSignal) =>
		request<LocationTreeNode[]>(
			locationPreferences.showItemQuantities
				? '/locations/tree?include_item_totals=true'
				: '/locations/tree',
			{ signal }
		),

	get: (id: string) => request<Location>(`/locations/${id}`),

	create: (data: LocationCreateRequest) =>
		request<Location>('/locations', {
			method: 'POST',
			body: JSON.stringify(data),
		}),

	update: (id: string, data: LocationUpdateRequest) =>
		request<Location>(`/locations/${id}`, {
			method: 'PUT',
			body: JSON.stringify(data),
		}),
};
