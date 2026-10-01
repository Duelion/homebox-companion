import type { ConfigResponse, FieldPreferences } from '../../../src/lib/api/settings';
import type {
	BatchCreateResponse,
	DetectionResponse,
	LocationTreeNode,
} from '../../../src/lib/types';

export type AuthMode = ConfigResponse['auth_mode'];

export const config = (auth_mode: AuthMode = 'api_key'): ConfigResponse => ({
	auth_mode,
	is_demo_mode: false,
	demo_mode_explicit: false,
	homebox_url: 'http://homebox.test',
	llm_model: 'gpt-5.6-luna',
	update_check_enabled: false,
	image_quality: 'high',
	log_level: 'INFO',
	capture_max_images: 10,
	capture_max_file_size_mb: 20,
	print_enabled: false,
});

export const groups = () => [
	{ id: 'g2', name: 'Shared' },
	{ id: 'g1', name: 'Personal' },
];

export const location = (id = 'loc-1', name = 'Storage'): LocationTreeNode => ({
	id,
	name,
	description: '',
	itemCount: 0,
	children: [],
});

export const fieldPreferences = (): FieldPreferences => ({
	output_language: null,
	default_tag_id: null,
	name: null,
	description: null,
	quantity: null,
	manufacturer: null,
	model_number: null,
	serial_number: null,
	purchase_price: null,
	purchase_from: null,
	notes: null,
	naming_examples: null,
});

export const detectedItems = (names: string[]): DetectionResponse => ({
	items: names.map((name) => ({ name, quantity: 1, description: `${name} photo` })),
	message: `Detected ${names.length} items`,
	compressed_images: [],
});

export const createdItem = (id: string, name = 'Created item'): BatchCreateResponse => ({
	created: [{ id, name, quantity: 1 }],
	errors: [],
	message: 'Created 1 item',
});
export const rejectedItem = (name: string): BatchCreateResponse => ({
	created: [],
	errors: [`${name} rejected`],
	message: 'Item rejected',
});
export const incompleteItem = (id: string, name: string): BatchCreateResponse => ({
	created: [{ id, name, quantity: 1 }],
	errors: [`Authentication failed for '${name}'`],
	message: 'Item created with incomplete details',
});
