/**
 * Groups (collections) API endpoints
 */

import { request } from './client';
import type { Group } from '../types';

export const groups = {
	/** Fetch all groups the authenticated user belongs to */
	list: () => request<Group[]>('/groups'),
};
