/**
 * Labels API endpoints
 */

import { request } from './client';
import type { Label } from '../types';

export const labels = {
	list: () => request<Label[]>('/labels'),
};
