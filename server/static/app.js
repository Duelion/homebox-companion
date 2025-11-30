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
    // Merge state
    isMergeReview: false,    // Whether we're reviewing a merged item
    mergedItemImages: [],    // Images from items being merged
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
    
    // Reset location UI completely
    elements.selectedLocationDisplay.style.display = 'none';
    elements.selectCurrentLocationBtn.style.display = 'none';
    elements.continueToCapture.disabled = true;
    
    // Reset location list and breadcrumb visibility (they get hidden when a location is selected)
    elements.locationList.style.display = 'flex';
    elements.locationBreadcrumb.style.display = 'flex';
    elements.locationList.innerHTML = '';  // Clear the list
    
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
                
                <!-- Correction Section -->
                <div class="correction-section">
                    <button type="button" class="correction-toggle" onclick="toggleCorrectionSection(${index})">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                        </svg>
                        <span>Correct Detection</span>
                    </button>
                    <div class="correction-content" id="correctionContent${index}" style="display: none;">
                        <p class="correction-hint">
                            Tell the AI what's wrong with this detection. You can:
                        </p>
                        <ul class="correction-examples">
                            <li>"Actually these are soldering tips, not screws"</li>
                            <li>"These are two separate items: wire solder and paste solder"</li>
                            <li>"This is a Fluke 87V multimeter, not a generic meter"</li>
                        </ul>
                        <div class="form-group">
                            <textarea 
                                id="correctionInput${index}" 
                                class="correction-input"
                                placeholder="Describe what's wrong or how to fix the detection..."
                                rows="3"
                            ></textarea>
                        </div>
                        <div class="correction-actions">
                            <button type="button" class="btn btn-secondary btn-sm" onclick="toggleCorrectionSection(${index})">
                                Cancel
                            </button>
                            <button type="button" class="btn btn-primary btn-sm" onclick="handleApplyCorrection(${index})">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="20 6 9 17 4 12"></polyline>
                                </svg>
                                <span>Apply Correction</span>
                            </button>
                        </div>
                        <div id="correctionLoader${index}" class="loader-inline" style="display: none;">
                            <div class="loader-spinner small"></div>
                            <span>AI is analyzing your correction...</span>
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

function toggleCorrectionSection(index) {
    const content = document.getElementById(`correctionContent${index}`);
    const isVisible = content.style.display !== 'none';
    content.style.display = isVisible ? 'none' : 'block';
    
    // Focus the textarea when opening
    if (!isVisible) {
        const textarea = document.getElementById(`correctionInput${index}`);
        if (textarea) {
            setTimeout(() => textarea.focus(), 100);
        }
    }
}

async function handleApplyCorrection(index) {
    const correctionInput = document.getElementById(`correctionInput${index}`);
    const correctionText = correctionInput?.value.trim();
    
    if (!correctionText) {
        showToast('Please describe what needs to be corrected', 'warning');
        return;
    }
    
    const item = state.detectedItems[index];
    const loader = document.getElementById(`correctionLoader${index}`);
    const content = document.getElementById(`correctionContent${index}`);
    
    // Get current values from the form
    const nameInput = document.getElementById(`itemName${index}`);
    const quantityInput = document.getElementById(`itemQuantity${index}`);
    const descriptionInput = document.getElementById(`itemDescription${index}`);
    
    const currentItem = {
        name: nameInput?.value || item.name,
        quantity: parseInt(quantityInput?.value) || item.quantity || 1,
        description: descriptionInput?.value || item.description || '',
    };
    
    // Show loader, hide action buttons
    const actionBtns = content.querySelector('.correction-actions');
    if (actionBtns) actionBtns.style.display = 'none';
    if (loader) loader.style.display = 'flex';
    
    try {
        // Prepare form data
        const formData = new FormData();
        
        // Add the original image
        if (state.capturedImage) {
            formData.append('image', state.capturedImage);
        } else {
            showToast('Original image not available', 'error');
            return;
        }
        
        formData.append('current_item', JSON.stringify(currentItem));
        formData.append('correction_instructions', correctionText);
        
        const response = await fetch('/api/correct-item', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: formData,
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || 'Correction failed');
        }
        
        const data = await response.json();
        
        if (!data.items || data.items.length === 0) {
            showToast('Correction did not produce any items', 'warning');
            return;
        }
        
        // Handle the corrected items
        if (data.items.length === 1) {
            // Single item - update the current item in place
            const correctedItem = data.items[0];
            state.detectedItems[index] = {
                ...item,
                name: correctedItem.name,
                quantity: correctedItem.quantity,
                description: correctedItem.description || '',
                label_ids: correctedItem.label_ids || [],
            };
            
            showToast('Item corrected successfully!', 'success');
        } else {
            // Multiple items - replace current item with new items
            const newItems = data.items.map(correctedItem => ({
                name: correctedItem.name,
                quantity: correctedItem.quantity,
                description: correctedItem.description || '',
                label_ids: correctedItem.label_ids || [],
                additionalImages: [],
                advancedFields: {},
                showAdvanced: false,
            }));
            
            // Remove current item and insert new items at the same position
            state.detectedItems.splice(index, 1, ...newItems);
            
            showToast(`Split into ${data.items.length} separate items!`, 'success');
        }
        
        // Re-render the cards
        renderItemCards();
        
    } catch (error) {
        showToast(error.message || 'Correction failed', 'error');
    } finally {
        if (loader) loader.style.display = 'none';
        if (actionBtns) actionBtns.style.display = 'flex';
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
    
    // Collect images to upload (original + additional) with dataUrls for preview
    const imagesToUpload = [];
    
    // In merge review mode, use the merged images
    if (state.isMergeReview && state.mergedItemImages) {
        state.mergedItemImages.forEach(img => {
            imagesToUpload.push({
                file: img.file,
                dataUrl: img.dataUrl,
                isPrimary: false,
            });
        });
    } else {
        if (state.capturedImage) {
            imagesToUpload.push({ 
                file: state.capturedImage, 
                isPrimary: true,
                dataUrl: state.originalImageDataUrl,
                isOriginal: true
            });
        }
        if (item.additionalImages && item.additionalImages.length > 0) {
            item.additionalImages.forEach(img => {
                imagesToUpload.push({ 
                    file: img.file, 
                    isPrimary: false,
                    dataUrl: img.dataUrl
                });
            });
        }
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
        coverImageDataUrl: null, // Will be set if user crops an image
        selectedImageIndex: 0,   // Index of selected image for cover
    };
    
    state.confirmedItems.push(confirmedItem);
    showToast(`"${confirmedItem.name}" confirmed`, 'success');
    
    moveToNextOrSummary();
}

function moveToNextOrSummary() {
    // Handle merge review mode differently
    if (state.isMergeReview) {
        // Merged item confirmed, go back to summary
        state.isMergeReview = false;
        state.detectedItems = [];
        state.currentItemIndex = 0;
        renderSummary();
        showSection('summarySection');
        showToast('Merged item added!', 'success');
        return;
    }
    
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

// Track selected items for merging
let selectedItemIndices = new Set();

function renderSummary() {
    elements.summarySubtitle.textContent = `${state.confirmedItems.length} item(s) ready to submit`;
    elements.summaryLocation.textContent = state.selectedLocationPath || state.selectedLocationName || 'Unknown';
    
    elements.summaryList.innerHTML = '';
    selectedItemIndices.clear();
    updateSelectionToolbar();
    
    state.confirmedItems.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'summary-item';
        div.dataset.index = index;
        
        // Get the cover image (cropped version if available, otherwise first image)
        const coverImage = item.coverImageDataUrl || 
            (item.images && item.images.length > 0 ? item.images[0].dataUrl : null) ||
            state.originalImageDataUrl;
        
        div.innerHTML = `
            <label class="summary-item-checkbox">
                <input type="checkbox" data-index="${index}" onchange="handleItemCheckboxChange(${index}, this.checked)">
                <span class="checkbox-custom">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                </span>
            </label>
            <div class="summary-item-image" data-index="${index}" onclick="handleSummaryImageClick(${index})">
                ${coverImage 
                    ? `<img src="${coverImage}" alt="${escapeHtml(item.name)}">`
                    : `<div class="image-placeholder">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                            <circle cx="8.5" cy="8.5" r="1.5"></circle>
                            <polyline points="21 15 16 10 5 21"></polyline>
                        </svg>
                       </div>`
                }
            </div>
            <div class="summary-item-info">
                <span class="summary-item-name">${escapeHtml(item.name)}</span>
                ${item.description ? `<span class="summary-item-meta">${escapeHtml(item.description.substring(0, 50))}${item.description.length > 50 ? '...' : ''}</span>` : ''}
            </div>
            <div class="summary-item-actions">
                <span class="summary-item-quantity">×${item.quantity}</span>
                <button type="button" class="btn-edit" onclick="handleEditItem(${index})" title="Edit item">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
            </div>
        `;
        elements.summaryList.appendChild(div);
    });
}

function handleItemCheckboxChange(index, checked) {
    if (checked) {
        selectedItemIndices.add(index);
    } else {
        selectedItemIndices.delete(index);
    }
    
    // Update visual state
    const item = document.querySelector(`.summary-item[data-index="${index}"]`);
    if (item) {
        item.classList.toggle('selected', checked);
    }
    
    updateSelectionToolbar();
}

function updateSelectionToolbar() {
    const toolbar = document.getElementById('selectionToolbar');
    const countSpan = document.getElementById('selectionCount');
    const mergeBtn = document.getElementById('mergeSelectedBtn');
    
    const count = selectedItemIndices.size;
    
    if (count > 0) {
        toolbar.style.display = 'flex';
        countSpan.textContent = `${count} selected`;
        mergeBtn.disabled = count < 2;
    } else {
        toolbar.style.display = 'none';
    }
}

function clearItemSelection() {
    selectedItemIndices.clear();
    
    // Uncheck all checkboxes
    document.querySelectorAll('.summary-item-checkbox input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });
    document.querySelectorAll('.summary-item.selected').forEach(item => {
        item.classList.remove('selected');
    });
    
    updateSelectionToolbar();
}

async function handleMergeSelected() {
    if (selectedItemIndices.size < 2) {
        showToast('Select at least 2 items to merge', 'warning');
        return;
    }
    
    const indices = Array.from(selectedItemIndices).sort((a, b) => a - b);
    const itemsToMerge = indices.map(i => state.confirmedItems[i]);
    
    // Show loader
    document.getElementById('mergeLoader').style.display = 'flex';
    document.getElementById('mergeSelectedBtn').disabled = true;
    
    try {
        // Call merge API
        const response = await apiRequest('/api/merge-items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: itemsToMerge.map(item => ({
                    name: item.name,
                    quantity: item.quantity,
                    description: item.description,
                })),
            }),
        });
        
        // Collect all images from merged items
        const mergedImages = [];
        itemsToMerge.forEach(item => {
            if (item.images) {
                item.images.forEach(img => {
                    mergedImages.push({
                        file: img.file,
                        dataUrl: img.dataUrl,
                        isPrimary: false,
                    });
                });
            }
            // Preserve cover image selections
            if (item.coverImageDataUrl) {
                mergedImages.unshift({
                    dataUrl: item.coverImageDataUrl,
                    isCover: true,
                });
            }
        });
        
        // Create merged item for review
        const mergedItem = {
            name: response.name,
            quantity: response.quantity,
            description: response.description,
            label_ids: response.label_ids,
            additionalImages: [],
            advancedFields: {},
            showAdvanced: false,
            // Store original items for reference
            _mergedFrom: indices,
            _mergedImages: mergedImages,
        };
        
        // Remove the original items from confirmed (in reverse order to maintain indices)
        for (let i = indices.length - 1; i >= 0; i--) {
            state.confirmedItems.splice(indices[i], 1);
        }
        
        // Add merged item to detected items for review
        state.detectedItems = [mergedItem];
        state.currentItemIndex = 0;
        state.isMergeReview = true;
        state.mergedItemImages = mergedImages;
        
        // Go to review section for the merged item
        renderItemCards();
        showSection('reviewSection');
        showToast('Items merged! Review the combined item.', 'success');
        
    } catch (error) {
        showToast(error.message || 'Failed to merge items', 'error');
    } finally {
        document.getElementById('mergeLoader').style.display = 'none';
        document.getElementById('mergeSelectedBtn').disabled = false;
    }
}

// ========================================
// Edit Item Modal
// ========================================

let editingItemIndex = null;
let selectedImageIndex = 0;

function handleEditItem(index) {
    editingItemIndex = index;
    const item = state.confirmedItems[index];
    
    // Populate form fields
    document.getElementById('editItemName').value = item.name || '';
    document.getElementById('editItemQuantity').value = item.quantity || 1;
    document.getElementById('editItemDescription').value = item.description || '';
    
    // Set up image gallery
    renderEditImageGallery(item);
    
    // Update preview image
    updateEditPreviewImage(item);
    
    // Show modal
    document.getElementById('editItemModal').style.display = 'flex';
}

function renderEditImageGallery(item) {
    const gallery = document.getElementById('editImageGallery');
    const allImages = getAllItemImages(item);
    
    if (allImages.length === 0) {
        gallery.innerHTML = '<span style="color: var(--text-muted); font-size: 0.875rem;">No images available</span>';
        return;
    }
    
    gallery.innerHTML = allImages.map((img, index) => `
        <div class="edit-image-gallery-item ${index === (item.selectedImageIndex || 0) ? 'selected' : ''}" 
             data-index="${index}" 
             onclick="handleGalleryImageSelect(${index})">
            <img src="${img.dataUrl}" alt="Image ${index + 1}">
            <div class="crop-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M6.13 1L6 16a2 2 0 0 0 2 2h15"></path>
                    <path d="M1 6.13L16 6a2 2 0 0 1 2 2v15"></path>
                </svg>
            </div>
        </div>
    `).join('');
}

function getAllItemImages(item) {
    const images = [];
    
    // Check if item.images already has the images (preferred source after editing)
    if (item.images && item.images.length > 0) {
        item.images.forEach((img, idx) => {
            if (img.dataUrl) {
                images.push(img);
            } else if (img.file) {
                // Generate data URL if not present
                const reader = new FileReader();
                reader.onload = (e) => {
                    img.dataUrl = e.target.result;
                };
                reader.readAsDataURL(img.file);
                // Still add the image reference (dataUrl will be populated async)
                images.push(img);
            }
        });
    }
    // Only add original image if no images in item.images array yet
    else if (state.originalImageDataUrl) {
        images.push({ 
            dataUrl: state.originalImageDataUrl, 
            file: state.capturedImage,
            isOriginal: true 
        });
    }
    
    return images;
}

function updateEditPreviewImage(item) {
    const previewImg = document.getElementById('editPreviewImg');
    const allImages = getAllItemImages(item);
    
    if (item.coverImageDataUrl) {
        previewImg.src = item.coverImageDataUrl;
    } else if (allImages.length > 0) {
        const selectedIdx = item.selectedImageIndex || 0;
        previewImg.src = allImages[selectedIdx]?.dataUrl || allImages[0].dataUrl;
    } else {
        previewImg.src = '';
    }
}

function handleGalleryImageSelect(index) {
    selectedImageIndex = index;
    const item = state.confirmedItems[editingItemIndex];
    item.selectedImageIndex = index;
    
    // Update selected state in gallery
    document.querySelectorAll('.edit-image-gallery-item').forEach((el, i) => {
        el.classList.toggle('selected', i === index);
    });
    
    // Open cropper for this image
    openImageCropper(index);
}

function handleSummaryImageClick(index) {
    // Open edit modal with focus on image
    handleEditItem(index);
}

function closeEditModal() {
    document.getElementById('editItemModal').style.display = 'none';
    editingItemIndex = null;
}

function saveEditChanges() {
    if (editingItemIndex === null) return;
    
    const item = state.confirmedItems[editingItemIndex];
    
    // Update item with form values
    item.name = document.getElementById('editItemName').value.trim();
    item.quantity = parseInt(document.getElementById('editItemQuantity').value) || 1;
    item.description = document.getElementById('editItemDescription').value.trim();
    
    // Re-render summary
    renderSummary();
    closeEditModal();
    showToast('Item updated', 'success');
}

// ========================================
// Image Cropper
// ========================================

let cropperState = {
    scale: 1,
    translateX: 0,
    translateY: 0,
    rotation: 0,
    isDragging: false,
    startX: 0,
    startY: 0,
    imageDataUrl: null,
    imageIndex: null,
    // Zoom limits based on image size
    minScale: 0.5,
    maxScale: 3,
    baseScale: 1, // Scale at which image fills the frame
    naturalWidth: 0,
    naturalHeight: 0,
};

function openImageCropper(imageIndex) {
    const item = state.confirmedItems[editingItemIndex];
    const allImages = getAllItemImages(item);
    
    if (!allImages[imageIndex]) return;
    
    cropperState = {
        scale: 1,
        translateX: 0,
        translateY: 0,
        rotation: 0,
        isDragging: false,
        startX: 0,
        startY: 0,
        imageDataUrl: allImages[imageIndex].dataUrl,
        imageIndex: imageIndex,
        minScale: 0.5,
        maxScale: 3,
        baseScale: 1,
        naturalWidth: 0,
        naturalHeight: 0,
    };
    
    const cropperImage = document.getElementById('cropperImage');
    
    // Load image to get natural dimensions and calculate zoom limits
    const tempImg = new Image();
    tempImg.onload = () => {
        cropperState.naturalWidth = tempImg.naturalWidth;
        cropperState.naturalHeight = tempImg.naturalHeight;
        
        // Calculate zoom limits based on image vs frame size
        calculateZoomLimits();
        
        // Set initial scale to fill the frame
        cropperState.scale = cropperState.baseScale;
        
        // Update UI
        updateZoomSlider();
        cropperImage.src = cropperState.imageDataUrl;
        updateCropperTransform();
    };
    tempImg.src = cropperState.imageDataUrl;
    
    // Reset rotation slider and label
    document.getElementById('rotationSlider').value = 0;
    document.getElementById('rotationLabel').textContent = '0°';
    
    // Show cropper modal
    document.getElementById('imageCropperModal').style.display = 'flex';
    
    // Initialize cropper interactions
    initCropperInteractions();
}

function calculateZoomLimits() {
    const container = document.getElementById('cropperContainer');
    const frame = document.getElementById('cropperFrame');
    
    if (!container || !frame) return;
    
    const containerRect = container.getBoundingClientRect();
    const frameRect = frame.getBoundingClientRect();
    
    // Frame is 80% of container (from CSS)
    const frameWidth = frameRect.width || containerRect.width * 0.8;
    const frameHeight = frameRect.height || containerRect.height * 0.8;
    
    const { naturalWidth, naturalHeight } = cropperState;
    
    if (!naturalWidth || !naturalHeight) return;
    
    // Calculate the scale needed to fill the frame (cover)
    const scaleToFillWidth = frameWidth / naturalWidth;
    const scaleToFillHeight = frameHeight / naturalHeight;
    const fillScale = Math.max(scaleToFillWidth, scaleToFillHeight);
    
    // Calculate the scale needed to fit the image (contain)
    const fitScale = Math.min(scaleToFillWidth, scaleToFillHeight);
    
    // Base scale is what makes the image fill the frame
    cropperState.baseScale = fillScale;
    
    // Min scale: allow zooming out to 50% of fill scale, but not smaller than fit
    cropperState.minScale = Math.max(fitScale * 0.5, fillScale * 0.5);
    
    // Max scale: allow zooming to 4x fill scale, but cap at 1:1 pixel ratio * 2
    const maxPixelScale = 2 / fillScale; // 2x the natural resolution relative to display
    cropperState.maxScale = Math.min(fillScale * 4, Math.max(fillScale * 2, maxPixelScale));
    
    // Ensure min < max
    if (cropperState.minScale >= cropperState.maxScale) {
        cropperState.minScale = cropperState.maxScale * 0.5;
    }
}

function updateZoomSlider() {
    const slider = document.getElementById('zoomSlider');
    const { minScale, maxScale, scale, baseScale } = cropperState;
    
    // Map scale to 0-100 slider range
    // 0 = minScale, 50 = baseScale (fill), 100 = maxScale
    let sliderValue;
    if (scale <= baseScale) {
        // 0-50 range
        sliderValue = ((scale - minScale) / (baseScale - minScale)) * 50;
    } else {
        // 50-100 range
        sliderValue = 50 + ((scale - baseScale) / (maxScale - baseScale)) * 50;
    }
    
    slider.min = 0;
    slider.max = 100;
    slider.value = Math.round(Math.max(0, Math.min(100, sliderValue)));
}

function initCropperInteractions() {
    const wrapper = document.getElementById('cropperImageWrapper');
    const image = document.getElementById('cropperImage');
    
    // Remove existing listeners
    wrapper.onpointerdown = null;
    wrapper.onpointermove = null;
    wrapper.onpointerup = null;
    wrapper.onwheel = null;
    
    // Pointer/touch handling for drag
    wrapper.onpointerdown = (e) => {
        e.preventDefault();
        cropperState.isDragging = true;
        cropperState.startX = e.clientX - cropperState.translateX;
        cropperState.startY = e.clientY - cropperState.translateY;
        wrapper.setPointerCapture(e.pointerId);
    };
    
    wrapper.onpointermove = (e) => {
        if (!cropperState.isDragging) return;
        e.preventDefault();
        
        cropperState.translateX = e.clientX - cropperState.startX;
        cropperState.translateY = e.clientY - cropperState.startY;
        
        updateCropperTransform();
    };
    
    wrapper.onpointerup = (e) => {
        cropperState.isDragging = false;
        wrapper.releasePointerCapture(e.pointerId);
    };
    
    // Mouse wheel for zoom
    wrapper.onwheel = (e) => {
        e.preventDefault();
        const { minScale, maxScale } = cropperState;
        const range = maxScale - minScale;
        const delta = e.deltaY > 0 ? -range * 0.05 : range * 0.05;
        cropperState.scale = Math.max(minScale, Math.min(maxScale, cropperState.scale + delta));
        updateZoomSlider();
        updateCropperTransform();
    };
    
    // Touch pinch-to-zoom
    let initialDistance = 0;
    let initialScale = 1;
    
    wrapper.ontouchstart = (e) => {
        if (e.touches.length === 2) {
            initialDistance = getDistance(e.touches[0], e.touches[1]);
            initialScale = cropperState.scale;
        }
    };
    
    wrapper.ontouchmove = (e) => {
        if (e.touches.length === 2) {
            e.preventDefault();
            const { minScale, maxScale } = cropperState;
            const currentDistance = getDistance(e.touches[0], e.touches[1]);
            const scaleFactor = currentDistance / initialDistance;
            cropperState.scale = Math.max(minScale, Math.min(maxScale, initialScale * scaleFactor));
            updateZoomSlider();
            updateCropperTransform();
        }
    };
}

function getDistance(touch1, touch2) {
    return Math.hypot(touch1.clientX - touch2.clientX, touch1.clientY - touch2.clientY);
}

function updateCropperTransform() {
    const image = document.getElementById('cropperImage');
    image.style.transform = `translate(${cropperState.translateX}px, ${cropperState.translateY}px) scale(${cropperState.scale}) rotate(${cropperState.rotation}deg)`;
}

function handleRotateLeft() {
    // Quick 90° rotation
    cropperState.rotation = Math.round((cropperState.rotation - 90) / 90) * 90;
    if (cropperState.rotation < -180) cropperState.rotation += 360;
    document.getElementById('rotationSlider').value = cropperState.rotation;
    document.getElementById('rotationLabel').textContent = `${cropperState.rotation}°`;
    updateCropperTransform();
}

function handleRotateRight() {
    // Quick 90° rotation
    cropperState.rotation = Math.round((cropperState.rotation + 90) / 90) * 90;
    if (cropperState.rotation > 180) cropperState.rotation -= 360;
    document.getElementById('rotationSlider').value = cropperState.rotation;
    document.getElementById('rotationLabel').textContent = `${cropperState.rotation}°`;
    updateCropperTransform();
}

function handleRotationSlider(e) {
    cropperState.rotation = parseInt(e.target.value);
    document.getElementById('rotationLabel').textContent = `${cropperState.rotation}°`;
    updateCropperTransform();
}

function handleZoomIn() {
    const { minScale, maxScale, baseScale } = cropperState;
    const step = (maxScale - minScale) * 0.1;
    cropperState.scale = Math.min(maxScale, cropperState.scale + step);
    updateZoomSlider();
    updateCropperTransform();
}

function handleZoomOut() {
    const { minScale, maxScale } = cropperState;
    const step = (maxScale - minScale) * 0.1;
    cropperState.scale = Math.max(minScale, cropperState.scale - step);
    updateZoomSlider();
    updateCropperTransform();
}

function handleZoomSlider(e) {
    const sliderValue = parseFloat(e.target.value);
    const { minScale, maxScale, baseScale } = cropperState;
    
    // Map 0-100 slider to scale range
    // 0 = minScale, 50 = baseScale (fill), 100 = maxScale
    if (sliderValue <= 50) {
        // 0-50 range maps to minScale-baseScale
        cropperState.scale = minScale + (sliderValue / 50) * (baseScale - minScale);
    } else {
        // 50-100 range maps to baseScale-maxScale
        cropperState.scale = baseScale + ((sliderValue - 50) / 50) * (maxScale - baseScale);
    }
    
    updateCropperTransform();
}

function closeCropperModal() {
    document.getElementById('imageCropperModal').style.display = 'none';
}

function applyCrop() {
    const container = document.getElementById('cropperContainer');
    const image = document.getElementById('cropperImage');
    const frame = document.getElementById('cropperFrame');
    
    // Get dimensions
    const containerRect = container.getBoundingClientRect();
    const frameRect = frame.getBoundingClientRect();
    
    // Create canvas for cropped image
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    // Set output size (square)
    const outputSize = 256;
    canvas.width = outputSize;
    canvas.height = outputSize;
    
    // Create temp image to get natural dimensions
    const tempImg = new Image();
    tempImg.onload = () => {
        const rotation = cropperState.rotation;
        const rotationRad = (rotation * Math.PI) / 180;
        const scale = cropperState.scale;
        const translateX = cropperState.translateX;
        const translateY = cropperState.translateY;
        
        const naturalWidth = tempImg.naturalWidth;
        const naturalHeight = tempImg.naturalHeight;
        
        // The image is displayed at: translate -> scale -> rotate (CSS transform order is right-to-left)
        // To reverse: un-rotate -> un-scale -> un-translate
        
        // Frame center in container coordinates
        const containerCenterX = containerRect.width / 2;
        const containerCenterY = containerRect.height / 2;
        const frameCenterX = (frameRect.left - containerRect.left) + frameRect.width / 2;
        const frameCenterY = (frameRect.top - containerRect.top) + frameRect.height / 2;
        
        // Frame center relative to the transformed image center
        // Image center after translate is at (containerCenterX + translateX, containerCenterY + translateY)
        const relX = frameCenterX - (containerCenterX + translateX);
        const relY = frameCenterY - (containerCenterY + translateY);
        
        // Un-rotate the relative position
        const cos = Math.cos(-rotationRad);
        const sin = Math.sin(-rotationRad);
        const unrotatedX = relX * cos - relY * sin;
        const unrotatedY = relX * sin + relY * cos;
        
        // Un-scale to get position in natural image coordinates
        // The image at scale=1 would be naturalWidth x naturalHeight centered in container
        // At current scale, it's naturalWidth*scale x naturalHeight*scale
        const naturalX = unrotatedX / scale + naturalWidth / 2;
        const naturalY = unrotatedY / scale + naturalHeight / 2;
        
        // Frame size in natural image coordinates (un-scaled)
        const cropWidth = frameRect.width / scale;
        const cropHeight = frameRect.height / scale;
        
        // Create a temporary canvas to handle rotation
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        
        // Set temp canvas size to accommodate rotated image
        const maxDim = Math.max(naturalWidth, naturalHeight) * 2;
        tempCanvas.width = maxDim;
        tempCanvas.height = maxDim;
        
        // Draw the rotated image
        tempCtx.translate(maxDim / 2, maxDim / 2);
        tempCtx.rotate(rotationRad);
        tempCtx.drawImage(tempImg, -naturalWidth / 2, -naturalHeight / 2);
        
        // The crop center in the temp canvas coordinates
        // The natural image center is at (maxDim/2, maxDim/2) before rotation
        // After rotation, we need to find where (naturalX, naturalY) from the original image maps to
        const offsetFromCenter = {
            x: naturalX - naturalWidth / 2,
            y: naturalY - naturalHeight / 2
        };
        
        // Rotate this offset
        const rotatedOffset = {
            x: offsetFromCenter.x * Math.cos(rotationRad) - offsetFromCenter.y * Math.sin(rotationRad),
            y: offsetFromCenter.x * Math.sin(rotationRad) + offsetFromCenter.y * Math.cos(rotationRad)
        };
        
        const srcCenterX = maxDim / 2 + rotatedOffset.x;
        const srcCenterY = maxDim / 2 + rotatedOffset.y;
        
        // Source coordinates for the crop
        const srcX = srcCenterX - cropWidth / 2;
        const srcY = srcCenterY - cropHeight / 2;
        
        // Draw the cropped area to final canvas
        ctx.drawImage(
            tempCanvas,
            srcX, srcY, cropWidth, cropHeight,
            0, 0, outputSize, outputSize
        );
        
        // Get data URL of cropped image
        const croppedDataUrl = canvas.toDataURL('image/jpeg', 0.9);
        
        // Convert canvas to Blob/File for upload
        canvas.toBlob((blob) => {
            if (!blob) {
                showToast('Failed to create cropped image', 'error');
                return;
            }
            
            // Create a File object from the blob
            const croppedFile = new File([blob], 'cropped-image.jpg', { type: 'image/jpeg' });
            
            // Save to item
            if (editingItemIndex !== null) {
                const item = state.confirmedItems[editingItemIndex];
                item.coverImageDataUrl = croppedDataUrl;
                item.selectedImageIndex = cropperState.imageIndex;
                
                // Replace the image in the images array with the cropped version
                if (item.images && item.images[cropperState.imageIndex]) {
                    item.images[cropperState.imageIndex] = {
                        file: croppedFile,
                        dataUrl: croppedDataUrl,
                        isPrimary: item.images[cropperState.imageIndex].isPrimary || false,
                        isCropped: true
                    };
                } else if (item.images && item.images.length > 0) {
                    // If index doesn't match (e.g., original image was added separately), 
                    // update the first image or add as primary
                    item.images[0] = {
                        file: croppedFile,
                        dataUrl: croppedDataUrl,
                        isPrimary: true,
                        isCropped: true
                    };
                } else {
                    // No images array, create one
                    item.images = [{
                        file: croppedFile,
                        dataUrl: croppedDataUrl,
                        isPrimary: true,
                        isCropped: true
                    }];
                }
                
                // Update preview in edit modal
                updateEditPreviewImage(item);
                
                // Update gallery with the new cropped image
                renderEditImageGallery(item);
            }
            
            closeCropperModal();
            showToast('Image cropped and saved', 'success');
        }, 'image/jpeg', 0.9);
    };
    tempImg.src = cropperState.imageDataUrl;
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
    
    // Go back to location selection, but keep the last selected location
    // This allows the user to either continue with the same location or navigate elsewhere
    if (state.selectedLocationId) {
        // Show location list and breadcrumb so user can navigate further if desired
        elements.locationList.style.display = 'flex';
        elements.locationBreadcrumb.style.display = 'flex';
        
        // Re-render the current location level so user can navigate to sub-locations
        renderLocationLevel();
        
        // Keep the selected location display visible
        elements.selectedLocationDisplay.style.display = 'flex';
        elements.continueToCapture.disabled = false;
    }
    
    showSection('locationSection');
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
    
    // Merge functionality
    document.getElementById('mergeSelectedBtn').addEventListener('click', handleMergeSelected);
    document.getElementById('clearSelectionBtn').addEventListener('click', clearItemSelection);
    
    // Edit Item Modal
    document.getElementById('closeEditModal').addEventListener('click', closeEditModal);
    document.getElementById('cancelEditBtn').addEventListener('click', closeEditModal);
    document.getElementById('saveEditBtn').addEventListener('click', saveEditChanges);
    document.getElementById('changeImageBtn').addEventListener('click', () => {
        // Open cropper with first image if available
        if (editingItemIndex !== null) {
            const item = state.confirmedItems[editingItemIndex];
            const allImages = getAllItemImages(item);
            if (allImages.length > 0) {
                openImageCropper(item.selectedImageIndex || 0);
            }
        }
    });
    
    // Image Cropper Modal
    document.getElementById('closeCropperModal').addEventListener('click', closeCropperModal);
    document.getElementById('cancelCropBtn').addEventListener('click', closeCropperModal);
    document.getElementById('applyCropBtn').addEventListener('click', applyCrop);
    document.getElementById('zoomInBtn').addEventListener('click', handleZoomIn);
    document.getElementById('zoomOutBtn').addEventListener('click', handleZoomOut);
    document.getElementById('zoomSlider').addEventListener('input', handleZoomSlider);
    document.getElementById('rotateLeftBtn').addEventListener('click', handleRotateLeft);
    document.getElementById('rotateRightBtn').addEventListener('click', handleRotateRight);
    document.getElementById('rotationSlider').addEventListener('input', handleRotationSlider);
    
    // Close modals on overlay click
    document.getElementById('editItemModal').addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
            closeEditModal();
        }
    });
    document.getElementById('imageCropperModal').addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
            closeCropperModal();
        }
    });
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

