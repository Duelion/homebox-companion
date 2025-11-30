/**
 * Homebox Scanner - Mobile Web App
 * Main application logic
 */

// ========================================
// State Management
// ========================================

const state = {
    token: null,
    locations: [],          // All locations flat list
    locationTree: [],       // Current level locations to display
    locationPath: [],       // Navigation path: [{id, name}, ...]
    labels: [],
    selectedLocationId: null,
    selectedLocationName: null,
    selectedLocationPath: '', // Full path string for display
    capturedImage: null,
    detectedItems: [],       // Items with additionalImages array
    confirmedItems: [],
    currentItemIndex: 0,
    originalImageDataUrl: null, // Base64 of original detection image
};

// ========================================
// DOM Elements
// ========================================

const elements = {
    // Sections
    loginSection: document.getElementById('loginSection'),
    locationSection: document.getElementById('locationSection'),
    captureSection: document.getElementById('captureSection'),
    reviewSection: document.getElementById('reviewSection'),
    summarySection: document.getElementById('summarySection'),
    successSection: document.getElementById('successSection'),
    
    // Login
    loginForm: document.getElementById('loginForm'),
    emailInput: document.getElementById('email'),
    passwordInput: document.getElementById('password'),
    logoutBtn: document.getElementById('logoutBtn'),
    
    // Location
    locationBreadcrumb: document.getElementById('locationBreadcrumb'),
    locationList: document.getElementById('locationList'),
    selectedLocationDisplay: document.getElementById('selectedLocationDisplay'),
    selectedLocationName: document.getElementById('selectedLocationName'),
    clearLocationBtn: document.getElementById('clearLocationBtn'),
    selectCurrentLocationBtn: document.getElementById('selectCurrentLocationBtn'),
    continueToCapture: document.getElementById('continueToCapture'),
    
    // Capture
    captureZone: document.getElementById('captureZone'),
    capturePlaceholder: document.getElementById('capturePlaceholder'),
    capturePreview: document.getElementById('capturePreview'),
    previewImage: document.getElementById('previewImage'),
    imageInput: document.getElementById('imageInput'),
    cameraBtn: document.getElementById('cameraBtn'),
    uploadBtn: document.getElementById('uploadBtn'),
    removeImage: document.getElementById('removeImage'),
    analyzeBtn: document.getElementById('analyzeBtn'),
    analyzeLoader: document.getElementById('analyzeLoader'),
    
    // Review
    itemCarousel: document.getElementById('itemCarousel'),
    itemCounter: document.getElementById('itemCounter'),
    prevItem: document.getElementById('prevItem'),
    nextItem: document.getElementById('nextItem'),
    skipItem: document.getElementById('skipItem'),
    confirmItem: document.getElementById('confirmItem'),
    
    // Summary
    summarySubtitle: document.getElementById('summarySubtitle'),
    summaryList: document.getElementById('summaryList'),
    summaryLocation: document.getElementById('summaryLocation'),
    addMoreBtn: document.getElementById('addMoreBtn'),
    submitAllBtn: document.getElementById('submitAllBtn'),
    submitLoader: document.getElementById('submitLoader'),
    
    // Success
    successMessage: document.getElementById('successMessage'),
    startOverBtn: document.getElementById('startOverBtn'),
    
    // Toast
    toastContainer: document.getElementById('toastContainer'),
};

// ========================================
// Utility Functions
// ========================================

function showSection(sectionId) {
    const sections = [
        elements.loginSection,
        elements.locationSection,
        elements.captureSection,
        elements.reviewSection,
        elements.summarySection,
        elements.successSection,
    ];
    
    sections.forEach(section => {
        section.classList.remove('active');
    });
    
    const target = document.getElementById(sectionId);
    if (target) {
        target.classList.add('active');
    }
}

function showToast(message, type = 'info') {
    // Ensure message is a string
    if (typeof message !== 'string') {
        message = message?.message || message?.detail || String(message) || 'An error occurred';
    }
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        error: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
        warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
        info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>',
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${message}</span>
    `;
    
    elements.toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'toastOut 0.25s ease forwards';
        setTimeout(() => toast.remove(), 250);
    }, 3000);
}

function getAuthHeaders() {
    return {
        'Authorization': `Bearer ${state.token}`,
    };
}

async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            ...(state.token ? getAuthHeaders() : {}),
        },
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || 'Request failed');
    }
    
    return response.json();
}

// ========================================
// Authentication
// ========================================

function saveToken(token) {
    state.token = token;
    sessionStorage.setItem('homebox_token', token);
    elements.logoutBtn.style.display = 'block';
}

function loadToken() {
    const token = sessionStorage.getItem('homebox_token');
    if (token) {
        state.token = token;
        elements.logoutBtn.style.display = 'block';
        return true;
    }
    return false;
}

function clearToken() {
    state.token = null;
    sessionStorage.removeItem('homebox_token');
    elements.logoutBtn.style.display = 'none';
}

async function handleLogin(event) {
    event.preventDefault();
    
    const email = elements.emailInput.value.trim();
    const password = elements.passwordInput.value;
    
    if (!email || !password) {
        showToast('Please enter email and password', 'error');
        return;
    }
    
    const submitBtn = elements.loginForm.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>Signing in...</span>';
    
    try {
        const data = await apiRequest('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: email, password }),
        });
        
        saveToken(data.token);
        showToast('Login successful!', 'success');
        await loadLocations();
        showSection('locationSection');
    } catch (error) {
        showToast(error.message || 'Login failed', 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Sign In</span><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>';
    }
}

function handleLogout() {
    clearToken();
    state.locations = [];
    state.locationTree = [];
    state.locationPath = [];
    state.labels = [];
    state.selectedLocationId = null;
    state.selectedLocationName = null;
    state.selectedLocationPath = '';
    state.capturedImage = null;
    state.detectedItems = [];
    state.confirmedItems = [];
    
    // Reset location UI
    elements.selectedLocationDisplay.style.display = 'none';
    elements.selectCurrentLocationBtn.style.display = 'none';
    elements.continueToCapture.disabled = true;
    
    showSection('loginSection');
    showToast('Logged out successfully', 'info');
}

// ========================================
// Locations - Hierarchical Navigation
// ========================================

async function loadLocations() {
    try {
        // Show loading state
        elements.locationList.innerHTML = `
            <div class="location-loading">
                <div class="loader-spinner small"></div>
                <span>Loading locations...</span>
            </div>
        `;
        
        // Fetch top-level locations with children info
        const locations = await apiRequest('/api/locations/tree');
        state.locations = locations;
        
        // Build tree structure and display top-level locations
        state.locationPath = [];
        renderLocationLevel();
        
        // Also load labels for later use
        try {
            const labels = await apiRequest('/api/labels');
            state.labels = labels;
        } catch (e) {
            console.warn('Could not load labels:', e);
        }
    } catch (error) {
        showToast('Failed to load locations: ' + error.message, 'error');
        elements.locationList.innerHTML = `
            <div class="location-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <p>Failed to load locations</p>
            </div>
        `;
    }
}

function getLocationById(locationId) {
    // Recursively search through locations and their children
    function findInTree(locations) {
        for (const loc of locations) {
            if (loc.id === locationId) {
                return loc;
            }
            if (loc.children && loc.children.length > 0) {
                const found = findInTree(loc.children);
                if (found) return found;
            }
        }
        return null;
    }
    return findInTree(state.locations);
}

async function renderLocationLevel() {
    const currentParentId = state.locationPath.length > 0 
        ? state.locationPath[state.locationPath.length - 1].id 
        : null;
    
    let childLocations;
    
    if (!currentParentId) {
        // At root level - show top-level locations
        childLocations = state.locations;
    } else {
        // At a child level - get children from the current parent
        // First check if we have the children cached in state
        const currentParent = state.locationPath[state.locationPath.length - 1];
        if (currentParent.children) {
            childLocations = currentParent.children;
        } else {
            // Need to fetch from API
            try {
                elements.locationList.innerHTML = `
                    <div class="location-loading">
                        <div class="loader-spinner small"></div>
                        <span>Loading...</span>
                    </div>
                `;
                const locationDetail = await apiRequest(`/api/locations/${currentParentId}`);
                childLocations = locationDetail.children || [];
                // Cache the children in the path
                currentParent.children = childLocations;
            } catch (e) {
                console.warn('Could not fetch location children:', e);
                childLocations = [];
            }
        }
    }
    
    state.locationTree = childLocations;
    
    // Render breadcrumb
    renderBreadcrumb();
    
    // Render location list
    renderLocationList(childLocations);
    
    // Show "Use This Location" button if we're in a sublocation
    updateSelectCurrentButton();
}

function renderBreadcrumb() {
    // Keep the root button, clear the rest
    const rootBtn = elements.locationBreadcrumb.querySelector('.breadcrumb-root');
    elements.locationBreadcrumb.innerHTML = '';
    elements.locationBreadcrumb.appendChild(rootBtn);
    
    // Add path items
    state.locationPath.forEach((loc, index) => {
        // Add separator
        const separator = document.createElement('span');
        separator.className = 'breadcrumb-separator';
        separator.innerHTML = `
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
        `;
        elements.locationBreadcrumb.appendChild(separator);
        
        // Add location button
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'breadcrumb-item' + (index === state.locationPath.length - 1 ? ' active' : '');
        btn.dataset.id = loc.id;
        btn.dataset.index = index;
        btn.innerHTML = `<span>${escapeHtml(loc.name)}</span>`;
        btn.addEventListener('click', () => handleBreadcrumbClick(index));
        elements.locationBreadcrumb.appendChild(btn);
    });
}

function renderLocationList(locations) {
    if (locations.length === 0) {
        elements.locationList.innerHTML = `
            <div class="location-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                    <circle cx="12" cy="10" r="3"></circle>
                </svg>
                <p>No sub-locations here</p>
                <span style="font-size: 0.875rem; color: var(--text-muted);">
                    ${state.locationPath.length > 0 ? 'You can use the current location or go back' : 'Create locations in Homebox first'}
                </span>
            </div>
        `;
        return;
    }
    
    elements.locationList.innerHTML = '';
    
    locations.forEach(location => {
        const hasChildren = location.children && location.children.length > 0;
        const itemCount = location.itemCount || location.items?.length || 0;
        
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'location-item' + (hasChildren ? ' has-children' : '');
        item.dataset.id = location.id;
        item.dataset.name = location.name;
        item.dataset.hasChildren = hasChildren;
        
        item.innerHTML = `
            <div class="location-item-icon">
                ${hasChildren 
                    ? `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                       </svg>`
                    : `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                        <circle cx="12" cy="10" r="3"></circle>
                       </svg>`
                }
            </div>
            <div class="location-item-info">
                <span class="location-item-name">${escapeHtml(location.name)}</span>
                <span class="location-item-meta">
                    ${hasChildren 
                        ? `<span class="location-item-count">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                            </svg>
                            ${location.children.length} sub-location${location.children.length !== 1 ? 's' : ''}
                           </span>`
                        : ''
                    }
                    ${itemCount > 0 
                        ? `<span class="location-item-count">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                            </svg>
                            ${itemCount} item${itemCount !== 1 ? 's' : ''}
                           </span>`
                        : ''
                    }
                </span>
            </div>
            ${hasChildren 
                ? `<div class="location-item-arrow">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                   </div>`
                : ''
            }
        `;
        
        item.addEventListener('click', () => handleLocationItemClick(location));
        elements.locationList.appendChild(item);
    });
}

function handleLocationItemClick(location) {
    const hasChildren = location.children && location.children.length > 0;
    
    if (hasChildren) {
        // Drill down into this location - cache children for navigation
        state.locationPath.push({ 
            id: location.id, 
            name: location.name,
            children: location.children 
        });
        renderLocationLevel();
    } else {
        // Select this location (no children)
        selectLocation(location.id, location.name);
    }
}

function handleBreadcrumbClick(index) {
    // Navigate back to this level
    state.locationPath = state.locationPath.slice(0, index + 1);
    renderLocationLevel();
}

function handleBreadcrumbRootClick() {
    // Go back to root level
    state.locationPath = [];
    renderLocationLevel();
}

function selectLocation(locationId, locationName) {
    state.selectedLocationId = locationId;
    state.selectedLocationName = locationName;
    
    // Build full path string
    const pathNames = state.locationPath.map(p => p.name);
    pathNames.push(locationName);
    state.selectedLocationPath = pathNames.join(' › ');
    
    // Update UI
    elements.selectedLocationDisplay.style.display = 'flex';
    elements.selectedLocationName.textContent = state.selectedLocationPath;
    elements.continueToCapture.disabled = false;
    
    // Hide location list and breadcrumb after selection
    elements.locationList.style.display = 'none';
    elements.locationBreadcrumb.style.display = 'none';
    
    // Hide select current button
    if (elements.selectCurrentLocationBtn) {
        elements.selectCurrentLocationBtn.style.display = 'none';
    }
    
    showToast(`Selected: ${state.selectedLocationPath}`, 'success');
}

function clearLocationSelection() {
    state.selectedLocationId = null;
    state.selectedLocationName = null;
    state.selectedLocationPath = '';
    
    elements.selectedLocationDisplay.style.display = 'none';
    
    // Show location list and breadcrumb again
    elements.locationList.style.display = 'flex';
    elements.locationBreadcrumb.style.display = 'flex';
    elements.continueToCapture.disabled = true;
    
    updateSelectCurrentButton();
}

function updateSelectCurrentButton() {
    // Show "Use This Location" button when:
    // 1. We're at a sublocation (path has items)
    // 2. Current level has children (we can go deeper)
    // 3. No location is currently selected
    const currentLocation = state.locationPath.length > 0 
        ? state.locationPath[state.locationPath.length - 1] 
        : null;
    
    if (currentLocation && !state.selectedLocationId) {
        elements.selectCurrentLocationBtn.style.display = 'flex';
        elements.selectCurrentLocationBtn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                <circle cx="12" cy="10" r="3"></circle>
            </svg>
            <span>Use "${escapeHtml(currentLocation.name)}"</span>
        `;
    } else {
        elements.selectCurrentLocationBtn.style.display = 'none';
    }
}

function handleSelectCurrentLocation() {
    if (state.locationPath.length > 0) {
        const current = state.locationPath[state.locationPath.length - 1];
        selectLocation(current.id, current.name);
    }
}

function handleContinueToCapture() {
    if (!state.selectedLocationId) {
        showToast('Please select a location', 'warning');
        return;
    }
    showSection('captureSection');
}

// ========================================
// Image Capture
// ========================================

function handleCaptureZoneClick() {
    elements.imageInput.click();
}

function handleCameraClick() {
    elements.imageInput.setAttribute('capture', 'environment');
    elements.imageInput.click();
}

function handleUploadClick() {
    elements.imageInput.removeAttribute('capture');
    elements.imageInput.click();
}

function handleImageSelect(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    
    if (!file.type.startsWith('image/')) {
        showToast('Please select an image file', 'error');
        return;
    }
    
    state.capturedImage = file;
    
    const reader = new FileReader();
    reader.onload = (e) => {
        elements.previewImage.src = e.target.result;
        state.originalImageDataUrl = e.target.result; // Store for later use
        elements.capturePreview.style.display = 'block';
        elements.capturePlaceholder.style.display = 'none';
        elements.analyzeBtn.disabled = false;
    };
    reader.readAsDataURL(file);
}

function handleRemoveImage() {
    state.capturedImage = null;
    elements.previewImage.src = '';
    elements.capturePreview.style.display = 'none';
    elements.capturePlaceholder.style.display = 'flex';
    elements.analyzeBtn.disabled = true;
    elements.imageInput.value = '';
}

async function handleAnalyze() {
    if (!state.capturedImage) {
        showToast('Please capture or upload an image first', 'warning');
        return;
    }
    
    elements.analyzeBtn.style.display = 'none';
    elements.analyzeLoader.style.display = 'flex';
    
    try {
        const formData = new FormData();
        formData.append('image', state.capturedImage);
        
        const response = await fetch('/api/detect', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: formData,
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || 'Detection failed');
        }
        
        const data = await response.json();
        
        if (!data.items || data.items.length === 0) {
            showToast('No items detected in the image', 'warning');
            elements.analyzeBtn.style.display = 'flex';
            elements.analyzeLoader.style.display = 'none';
            return;
        }
        
        // Initialize additional fields for each item
        state.detectedItems = data.items.map(item => ({
            ...item,
            additionalImages: [],      // Files for additional photos
            advancedFields: {},        // AI-analyzed advanced fields
            showAdvanced: false,       // Whether advanced section is expanded
        }));
        state.currentItemIndex = 0;
        
        showToast(`Detected ${data.items.length} item(s)`, 'success');
        renderItemCards();
        showSection('reviewSection');
    } catch (error) {
        showToast(error.message || 'Analysis failed', 'error');
    } finally {
        elements.analyzeBtn.style.display = 'flex';
        elements.analyzeLoader.style.display = 'none';
    }
}

// ========================================
// Item Review
// ========================================

function renderItemCards() {
    elements.itemCarousel.innerHTML = '';
    
    state.detectedItems.forEach((item, index) => {
        const card = document.createElement('div');
        card.className = `item-card${index === state.currentItemIndex ? ' active' : ''}`;
        card.dataset.index = index;
        
        const imageCount = item.additionalImages?.length || 0;
        const advancedFields = item.advancedFields || {};
        const showAdvanced = item.showAdvanced || false;
        const selectedLabelIds = item.label_ids || [];
        
        card.innerHTML = `
            <form class="form" onsubmit="return false;">
                <div class="form-group">
                    <label for="itemName${index}">Item Name</label>
                    <input type="text" id="itemName${index}" value="${escapeHtml(item.name)}" required>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label for="itemQuantity${index}">Quantity</label>
                        <input type="number" id="itemQuantity${index}" value="${item.quantity || 1}" min="1" required>
                    </div>
                </div>
                <div class="form-group">
                    <label for="itemDescription${index}">Description</label>
                    <textarea id="itemDescription${index}" placeholder="Optional description...">${escapeHtml(item.description || '')}</textarea>
                </div>
                
                <!-- Labels Section -->
                <div class="form-group labels-section">
                    <label>Labels</label>
                    <div class="labels-grid" id="labelsGrid${index}">
                        ${renderLabelCheckboxes(index, selectedLabelIds)}
                    </div>
                </div>
                
                <!-- Additional Images Section -->
                <div class="additional-images-section">
                    <label>Additional Photos</label>
                    <div class="additional-images-grid" id="additionalImagesGrid${index}">
                        ${renderAdditionalImageThumbnails(item.additionalImages || [], index)}
                        <button type="button" class="add-image-btn" onclick="handleAddImage(${index})">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="12" y1="5" x2="12" y2="19"></line>
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                            </svg>
                            <span>Add Photo</span>
                        </button>
                    </div>
                    <input type="file" id="additionalImageInput${index}" accept="image/*" multiple style="display: none;" onchange="handleAdditionalImageSelect(event, ${index})">
                    
                    ${imageCount > 0 ? `
                    <button type="button" class="btn btn-secondary btn-sm analyze-advanced-btn" onclick="handleAnalyzeAdvanced(${index})">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="11" cy="11" r="8"></circle>
                            <path d="m21 21-4.35-4.35"></path>
                        </svg>
                        <span>Analyze Details with AI</span>
                    </button>
                    <div id="analyzeLoader${index}" class="loader-inline" style="display: none;">
                        <div class="loader-spinner small"></div>
                        <span>Analyzing...</span>
                    </div>
                    ` : ''}
                </div>
                
                <!-- Advanced Fields Section (Collapsible) -->
                <div class="advanced-fields-section">
                    <button type="button" class="advanced-toggle" onclick="toggleAdvancedFields(${index})">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="${showAdvanced ? 'rotated' : ''}">
                            <polyline points="9 18 15 12 9 6"></polyline>
                        </svg>
                        <span>Advanced Fields</span>
                        ${hasAdvancedFieldValues(advancedFields) ? '<span class="badge">Filled</span>' : ''}
                    </button>
                    <div class="advanced-fields-content" id="advancedFields${index}" style="display: ${showAdvanced ? 'block' : 'none'};">
                        <div class="form-row">
                            <div class="form-group">
                                <label for="itemSerialNumber${index}">Serial Number</label>
                                <input type="text" id="itemSerialNumber${index}" value="${escapeHtml(advancedFields.serialNumber || '')}" placeholder="e.g., SN123456">
                            </div>
                            <div class="form-group">
                                <label for="itemModelNumber${index}">Model Number</label>
                                <input type="text" id="itemModelNumber${index}" value="${escapeHtml(advancedFields.modelNumber || '')}" placeholder="e.g., XYZ-100">
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="itemManufacturer${index}">Manufacturer</label>
                            <input type="text" id="itemManufacturer${index}" value="${escapeHtml(advancedFields.manufacturer || '')}" placeholder="e.g., Sony, Samsung">
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="itemPurchasePrice${index}">Purchase Price</label>
                                <input type="number" id="itemPurchasePrice${index}" value="${advancedFields.purchasePrice || ''}" placeholder="0.00" step="0.01" min="0">
                            </div>
                            <div class="form-group">
                                <label for="itemPurchaseFrom${index}">Purchased From</label>
                                <input type="text" id="itemPurchaseFrom${index}" value="${escapeHtml(advancedFields.purchaseFrom || '')}" placeholder="e.g., Amazon">
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="itemNotes${index}">Notes</label>
                            <textarea id="itemNotes${index}" placeholder="Additional notes...">${escapeHtml(advancedFields.notes || '')}</textarea>
                        </div>
                    </div>
                </div>
            </form>
        `;
        
        elements.itemCarousel.appendChild(card);
    });
    
    updateItemNavigation();
}

function renderAdditionalImageThumbnails(images, itemIndex) {
    if (!images || images.length === 0) return '';
    
    return images.map((img, imgIndex) => `
        <div class="additional-image-thumb">
            <img src="${img.dataUrl}" alt="Image ${imgIndex + 1}">
            <button type="button" class="remove-image-btn" onclick="handleRemoveAdditionalImage(${itemIndex}, ${imgIndex})">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        </div>
    `).join('');
}

function hasAdvancedFieldValues(fields) {
    if (!fields) return false;
    return !!(fields.serialNumber || fields.modelNumber || fields.manufacturer || 
              fields.purchasePrice || fields.purchaseFrom || fields.notes);
}

function toggleAdvancedFields(index) {
    const item = state.detectedItems[index];
    item.showAdvanced = !item.showAdvanced;
    
    const content = document.getElementById(`advancedFields${index}`);
    const toggle = content.previousElementSibling;
    const arrow = toggle.querySelector('svg');
    
    if (item.showAdvanced) {
        content.style.display = 'block';
        arrow.classList.add('rotated');
    } else {
        content.style.display = 'none';
        arrow.classList.remove('rotated');
    }
}

function handleAddImage(index) {
    document.getElementById(`additionalImageInput${index}`).click();
}

function handleAdditionalImageSelect(event, itemIndex) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    const item = state.detectedItems[itemIndex];
    if (!item.additionalImages) item.additionalImages = [];
    
    Array.from(files).forEach(file => {
        if (!file.type.startsWith('image/')) return;
        
        const reader = new FileReader();
        reader.onload = (e) => {
            item.additionalImages.push({
                file: file,
                dataUrl: e.target.result,
            });
            // Re-render the current card only
            updateItemCardImages(itemIndex);
        };
        reader.readAsDataURL(file);
    });
}

function handleRemoveAdditionalImage(itemIndex, imageIndex) {
    const item = state.detectedItems[itemIndex];
    if (item.additionalImages) {
        item.additionalImages.splice(imageIndex, 1);
        updateItemCardImages(itemIndex);
    }
}

function updateItemCardImages(index) {
    const grid = document.getElementById(`additionalImagesGrid${index}`);
    if (!grid) return;
    
    const item = state.detectedItems[index];
    const images = item.additionalImages || [];
    
    // Update thumbnails
    grid.innerHTML = renderAdditionalImageThumbnails(images, index) + `
        <button type="button" class="add-image-btn" onclick="handleAddImage(${index})">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            <span>Add Photo</span>
        </button>
    `;
    
    // Show/hide analyze button based on image count
    const section = grid.closest('.additional-images-section');
    let analyzeBtn = section.querySelector('.analyze-advanced-btn');
    let analyzeLoader = section.querySelector('.loader-inline');
    
    if (images.length > 0 && !analyzeBtn) {
        // Add the analyze button
        const btnHtml = `
            <button type="button" class="btn btn-secondary btn-sm analyze-advanced-btn" onclick="handleAnalyzeAdvanced(${index})">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="8"></circle>
                    <path d="m21 21-4.35-4.35"></path>
                </svg>
                <span>Analyze Details with AI</span>
            </button>
            <div id="analyzeLoader${index}" class="loader-inline" style="display: none;">
                <div class="loader-spinner small"></div>
                <span>Analyzing...</span>
            </div>
        `;
        grid.insertAdjacentHTML('afterend', btnHtml);
    } else if (images.length === 0 && analyzeBtn) {
        analyzeBtn.remove();
        if (analyzeLoader) analyzeLoader.remove();
    }
}

async function handleAnalyzeAdvanced(itemIndex) {
    const item = state.detectedItems[itemIndex];
    const images = item.additionalImages || [];
    
    if (images.length === 0) {
        showToast('Add at least one photo to analyze', 'warning');
        return;
    }
    
    const analyzeBtn = document.querySelector(`#additionalImagesGrid${itemIndex}`).parentElement.querySelector('.analyze-advanced-btn');
    const loader = document.getElementById(`analyzeLoader${itemIndex}`);
    
    if (analyzeBtn) analyzeBtn.style.display = 'none';
    if (loader) loader.style.display = 'flex';
    
    try {
        const formData = new FormData();
        
        // Add the original image first
        if (state.capturedImage) {
            formData.append('images', state.capturedImage);
        }
        
        // Add all additional images
        images.forEach(img => {
            formData.append('images', img.file);
        });
        
        // Get current item name and description
        const nameInput = document.getElementById(`itemName${itemIndex}`);
        const descInput = document.getElementById(`itemDescription${itemIndex}`);
        
        formData.append('item_name', nameInput?.value || item.name);
        if (descInput?.value) {
            formData.append('item_description', descInput.value);
        }
        
        const response = await fetch('/api/analyze-advanced', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: formData,
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || 'Analysis failed');
        }
        
        const details = await response.json();
        
        // Update the item's advanced fields
        item.advancedFields = {
            serialNumber: details.serial_number || '',
            modelNumber: details.model_number || '',
            manufacturer: details.manufacturer || '',
            purchasePrice: details.purchase_price || '',
            purchaseFrom: '',
            notes: details.notes || '',
        };
        
        // Update name if AI found a better one
        if (details.name && details.name.trim()) {
            const nameInput = document.getElementById(`itemName${itemIndex}`);
            if (nameInput) {
                nameInput.value = details.name;
                item.name = details.name;
            }
        }
        
        // Update description if AI found a better one
        if (details.description && details.description.trim()) {
            const descInput = document.getElementById(`itemDescription${itemIndex}`);
            if (descInput) {
                descInput.value = details.description;
                item.description = details.description;
            }
        }
        
        // Update labels if AI suggested any
        if (details.label_ids && Array.isArray(details.label_ids) && details.label_ids.length > 0) {
            updateItemLabels(itemIndex, details.label_ids);
        }
        
        // Expand and populate advanced fields
        item.showAdvanced = true;
        populateAdvancedFields(itemIndex, item.advancedFields);
        
        showToast('Analysis complete! Fields updated.', 'success');
    } catch (error) {
        showToast(error.message || 'Analysis failed', 'error');
    } finally {
        if (analyzeBtn) analyzeBtn.style.display = 'flex';
        if (loader) loader.style.display = 'none';
    }
}

function populateAdvancedFields(index, fields) {
    const content = document.getElementById(`advancedFields${index}`);
    const toggle = content.previousElementSibling;
    const arrow = toggle.querySelector('svg');
    
    // Show the section
    content.style.display = 'block';
    arrow.classList.add('rotated');
    
    // Update the badge
    const badge = toggle.querySelector('.badge');
    if (hasAdvancedFieldValues(fields)) {
        if (!badge) {
            toggle.insertAdjacentHTML('beforeend', '<span class="badge">Filled</span>');
        }
    }
    
    // Populate fields
    const setField = (id, value) => {
        const el = document.getElementById(id);
        if (el && value) el.value = value;
    };
    
    setField(`itemSerialNumber${index}`, fields.serialNumber);
    setField(`itemModelNumber${index}`, fields.modelNumber);
    setField(`itemManufacturer${index}`, fields.manufacturer);
    setField(`itemPurchasePrice${index}`, fields.purchasePrice);
    setField(`itemPurchaseFrom${index}`, fields.purchaseFrom);
    setField(`itemNotes${index}`, fields.notes);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderLabelCheckboxes(itemIndex, selectedLabelIds = []) {
    if (!state.labels || state.labels.length === 0) {
        return '<span class="no-labels">No labels available</span>';
    }
    
    return state.labels.map(label => {
        const isChecked = selectedLabelIds.includes(label.id);
        return `
            <label class="label-checkbox ${isChecked ? 'checked' : ''}">
                <input type="checkbox" 
                       name="itemLabels${itemIndex}" 
                       value="${label.id}" 
                       ${isChecked ? 'checked' : ''}
                       onchange="handleLabelChange(${itemIndex}, '${label.id}', this.checked)">
                <span class="label-name">${escapeHtml(label.name)}</span>
            </label>
        `;
    }).join('');
}

function handleLabelChange(itemIndex, labelId, isChecked) {
    const item = state.detectedItems[itemIndex];
    if (!item.label_ids) item.label_ids = [];
    
    if (isChecked) {
        if (!item.label_ids.includes(labelId)) {
            item.label_ids.push(labelId);
        }
    } else {
        item.label_ids = item.label_ids.filter(id => id !== labelId);
    }
    
    // Update checkbox visual state
    const checkbox = document.querySelector(`input[name="itemLabels${itemIndex}"][value="${labelId}"]`);
    if (checkbox) {
        checkbox.closest('.label-checkbox').classList.toggle('checked', isChecked);
    }
}

function getSelectedLabels(itemIndex) {
    const checkboxes = document.querySelectorAll(`input[name="itemLabels${itemIndex}"]:checked`);
    return Array.from(checkboxes).map(cb => cb.value);
}

function updateItemLabels(itemIndex, labelIds) {
    const item = state.detectedItems[itemIndex];
    item.label_ids = labelIds || [];
    
    // Update all checkboxes for this item
    const grid = document.getElementById(`labelsGrid${itemIndex}`);
    if (grid) {
        grid.innerHTML = renderLabelCheckboxes(itemIndex, item.label_ids);
    }
}

function updateItemNavigation() {
    const total = state.detectedItems.length;
    const current = state.currentItemIndex + 1;
    
    elements.itemCounter.textContent = `${current} / ${total}`;
    elements.prevItem.disabled = state.currentItemIndex === 0;
    elements.nextItem.disabled = state.currentItemIndex >= total - 1;
    
    // Update active card
    document.querySelectorAll('.item-card').forEach((card, index) => {
        card.classList.toggle('active', index === state.currentItemIndex);
    });
}

function handlePrevItem() {
    if (state.currentItemIndex > 0) {
        state.currentItemIndex--;
        updateItemNavigation();
    }
}

function handleNextItem() {
    if (state.currentItemIndex < state.detectedItems.length - 1) {
        state.currentItemIndex++;
        updateItemNavigation();
    }
}

function handleSkipItem() {
    moveToNextOrSummary();
}

function handleConfirmItem() {
    const index = state.currentItemIndex;
    const item = state.detectedItems[index];
    
    const nameInput = document.getElementById(`itemName${index}`);
    const quantityInput = document.getElementById(`itemQuantity${index}`);
    const descriptionInput = document.getElementById(`itemDescription${index}`);
    
    if (!nameInput.value.trim()) {
        showToast('Please enter an item name', 'warning');
        return;
    }
    
    // Gather advanced fields
    const serialNumber = document.getElementById(`itemSerialNumber${index}`)?.value.trim() || null;
    const modelNumber = document.getElementById(`itemModelNumber${index}`)?.value.trim() || null;
    const manufacturer = document.getElementById(`itemManufacturer${index}`)?.value.trim() || null;
    const purchasePrice = parseFloat(document.getElementById(`itemPurchasePrice${index}`)?.value) || null;
    const purchaseFrom = document.getElementById(`itemPurchaseFrom${index}`)?.value.trim() || null;
    const notes = document.getElementById(`itemNotes${index}`)?.value.trim() || null;
    
    // Collect images to upload (original + additional)
    const imagesToUpload = [];
    if (state.capturedImage) {
        imagesToUpload.push({ file: state.capturedImage, isPrimary: true });
    }
    if (item.additionalImages && item.additionalImages.length > 0) {
        item.additionalImages.forEach(img => {
            imagesToUpload.push({ file: img.file, isPrimary: false });
        });
    }
    
    // Get selected labels from checkboxes
    const selectedLabels = getSelectedLabels(index);
    
    const confirmedItem = {
        name: nameInput.value.trim(),
        quantity: parseInt(quantityInput.value) || 1,
        description: descriptionInput.value.trim() || null,
        location_id: state.selectedLocationId,
        label_ids: selectedLabels.length > 0 ? selectedLabels : null,
        serial_number: serialNumber,
        model_number: modelNumber,
        manufacturer: manufacturer,
        purchase_price: purchasePrice,
        purchase_from: purchaseFrom,
        notes: notes,
        images: imagesToUpload,
    };
    
    state.confirmedItems.push(confirmedItem);
    showToast(`"${confirmedItem.name}" confirmed`, 'success');
    
    moveToNextOrSummary();
}

function moveToNextOrSummary() {
    if (state.currentItemIndex < state.detectedItems.length - 1) {
        state.currentItemIndex++;
        updateItemNavigation();
    } else {
        // All items reviewed
        if (state.confirmedItems.length === 0) {
            showToast('No items confirmed. Going back to capture.', 'warning');
            resetCaptureState();
            showSection('captureSection');
        } else {
            renderSummary();
            showSection('summarySection');
        }
    }
}

// ========================================
// Summary
// ========================================

function renderSummary() {
    elements.summarySubtitle.textContent = `${state.confirmedItems.length} item(s) ready to submit`;
    elements.summaryLocation.textContent = state.selectedLocationPath || state.selectedLocationName || 'Unknown';
    
    elements.summaryList.innerHTML = '';
    
    state.confirmedItems.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'summary-item';
        div.innerHTML = `
            <div class="summary-item-info">
                <span class="summary-item-name">${escapeHtml(item.name)}</span>
                ${item.description ? `<span class="summary-item-meta">${escapeHtml(item.description.substring(0, 50))}${item.description.length > 50 ? '...' : ''}</span>` : ''}
            </div>
            <span class="summary-item-quantity">×${item.quantity}</span>
        `;
        elements.summaryList.appendChild(div);
    });
}

function handleAddMore() {
    resetCaptureState();
    showSection('captureSection');
}

async function handleSubmitAll() {
    if (state.confirmedItems.length === 0) {
        showToast('No items to submit', 'warning');
        return;
    }
    
    elements.submitAllBtn.style.display = 'none';
    elements.addMoreBtn.style.display = 'none';
    elements.submitLoader.style.display = 'flex';
    
    try {
        // Prepare items for API (without images array)
        const itemsForApi = state.confirmedItems.map(item => ({
            name: item.name,
            quantity: item.quantity,
            description: item.description,
            location_id: item.location_id,
            label_ids: item.label_ids,
            serial_number: item.serial_number,
            model_number: item.model_number,
            manufacturer: item.manufacturer,
            purchase_price: item.purchase_price,
            purchase_from: item.purchase_from,
            notes: item.notes,
        }));
        
        const response = await apiRequest('/api/items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: itemsForApi,
                location_id: state.selectedLocationId,
            }),
        });
        
        const createdItems = response.created || [];
        const createdCount = createdItems.length;
        const errorCount = response.errors?.length || 0;
        
        // Upload images for each created item
        let imageUploadErrors = 0;
        for (let i = 0; i < createdItems.length; i++) {
            const createdItem = createdItems[i];
            const originalItem = state.confirmedItems[i];
            
            if (originalItem?.images && originalItem.images.length > 0) {
                for (const img of originalItem.images) {
                    try {
                        await uploadItemImage(createdItem.id, img.file);
                    } catch (err) {
                        console.error('Failed to upload image:', err);
                        imageUploadErrors++;
                    }
                }
            }
        }
        
        let message = `Created ${createdCount} items`;
        if (errorCount > 0) message += `, ${errorCount} failed`;
        if (imageUploadErrors > 0) message += `, ${imageUploadErrors} image upload(s) failed`;
        
        showToast(message, errorCount > 0 || imageUploadErrors > 0 ? 'warning' : 'success');
        
        elements.successMessage.textContent = `${createdCount} item(s) have been added to your inventory`;
        showSection('successSection');
        
        // Reset state for next batch
        state.confirmedItems = [];
        state.detectedItems = [];
        resetCaptureState();
    } catch (error) {
        showToast(error.message || 'Failed to create items', 'error');
    } finally {
        elements.submitAllBtn.style.display = 'flex';
        elements.addMoreBtn.style.display = 'flex';
        elements.submitLoader.style.display = 'none';
    }
}

async function uploadItemImage(itemId, file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`/api/items/${itemId}/attachments`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: formData,
    });
    
    if (!response.ok) {
        throw new Error('Failed to upload image');
    }
    
    return response.json();
}

function handleStartOver() {
    state.confirmedItems = [];
    state.detectedItems = [];
    resetCaptureState();
    showSection('captureSection');
}

function resetCaptureState() {
    state.capturedImage = null;
    state.detectedItems = [];
    state.currentItemIndex = 0;
    elements.previewImage.src = '';
    elements.capturePreview.style.display = 'none';
    elements.capturePlaceholder.style.display = 'flex';
    elements.analyzeBtn.disabled = true;
    elements.imageInput.value = '';
}

// ========================================
// Event Listeners
// ========================================

function initEventListeners() {
    // Login
    elements.loginForm.addEventListener('submit', handleLogin);
    elements.logoutBtn.addEventListener('click', handleLogout);
    
    // Location - Hierarchical Navigation
    elements.locationBreadcrumb.querySelector('.breadcrumb-root').addEventListener('click', handleBreadcrumbRootClick);
    elements.clearLocationBtn.addEventListener('click', clearLocationSelection);
    elements.selectCurrentLocationBtn.addEventListener('click', handleSelectCurrentLocation);
    elements.continueToCapture.addEventListener('click', handleContinueToCapture);
    
    // Capture
    elements.captureZone.addEventListener('click', handleCaptureZoneClick);
    elements.cameraBtn.addEventListener('click', handleCameraClick);
    elements.uploadBtn.addEventListener('click', handleUploadClick);
    elements.imageInput.addEventListener('change', handleImageSelect);
    elements.removeImage.addEventListener('click', (e) => {
        e.stopPropagation();
        handleRemoveImage();
    });
    elements.analyzeBtn.addEventListener('click', handleAnalyze);
    
    // Review
    elements.prevItem.addEventListener('click', handlePrevItem);
    elements.nextItem.addEventListener('click', handleNextItem);
    elements.skipItem.addEventListener('click', handleSkipItem);
    elements.confirmItem.addEventListener('click', handleConfirmItem);
    
    // Summary
    elements.addMoreBtn.addEventListener('click', handleAddMore);
    elements.submitAllBtn.addEventListener('click', handleSubmitAll);
    
    // Success
    elements.startOverBtn.addEventListener('click', handleStartOver);
}

// ========================================
// Initialization
// ========================================

async function init() {
    initEventListeners();
    
    // Check for existing token
    if (loadToken()) {
        try {
            await loadLocations();
            showSection('locationSection');
        } catch (error) {
            // Token expired or invalid
            clearToken();
            showSection('loginSection');
        }
    } else {
        showSection('loginSection');
    }
}

// Start the app
document.addEventListener('DOMContentLoaded', init);

