/**
 * Locations API endpoints
 */

import { request } from './client';
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

	tree: () => request<LocationTreeNode[]>('/locations/tree'),

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
