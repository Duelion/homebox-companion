type LocationPreferences = {
	showItemQuantities: boolean;
	containerLocationsOnly: boolean;
};

const storageKey = 'hbc-location-preferences';

function loadPreferences(): LocationPreferences {
	const defaults = { showItemQuantities: false, containerLocationsOnly: false };
	if (typeof window === 'undefined') return defaults;
	try {
		const saved = JSON.parse(window.localStorage.getItem(storageKey) ?? '{}');
		return {
			showItemQuantities: saved?.showItemQuantities === true,
			containerLocationsOnly: saved?.containerLocationsOnly === true,
		};
	} catch {
		return defaults;
	}
}

const preferences = $state(loadPreferences());

export const locationPreferences = {
	get showItemQuantities() {
		return preferences.showItemQuantities;
	},

	get containerLocationsOnly() {
		return preferences.containerLocationsOnly;
	},

	set(key: keyof LocationPreferences, value: boolean) {
		preferences[key] = value;
		try {
			window.localStorage.setItem(storageKey, JSON.stringify(preferences));
		} catch {
			// Keep the in-memory selection when browser storage is unavailable.
		}
	},
};
