/**
 * Tags API endpoints
 */

import { request } from './client';
import type { Tag } from '../types';

export const tags = {
	list: () => request<Tag[]>('/tags'),
};
