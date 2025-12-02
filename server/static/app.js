/**
 * Homebox Scanner - Mobile Web App
 * Main application logic
 * Version: 0.15.3 (2025-12-02)
 */

// Debug: Log when script loads to verify cache is cleared
console.log('=== Homebox Scanner v0.15.3 loaded ===');

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
    capturedImages: [],      // Array of {file, dataUrl, additionalImages, separateItems, extraInstructions} for multi-image upload
    detectedItems: [],       // Items with additionalImages array and sourceImageIndex
    confirmedItems: [],
    currentItemIndex: 0,
    // Merge state
    isMergeReview: false,    // Whether we're reviewing a merged item
    mergedItemImages: [],    // Images from items being merged
    // Edit from summary state
    isEditingFromSummary: false,  // Whether we're editing a confirmed item from summary
    editingConfirmedIndex: null,  // Index of the confirmed item being edited
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
    
    // Capture - Multi-image
    captureZone: document.getElementById('captureZone'),
    capturePlaceholder: document.getElementById('capturePlaceholder'),
    multiImageContainer: document.getElementById('multiImageContainer'),
    multiImageGrid: document.getElementById('multiImageGrid'),
    addMoreImagesZone: document.getElementById('addMoreImagesZone'),
    imageInput: document.getElementById('imageInput'),
    cameraInput: document.getElementById('cameraInput'),
    cameraBtn: document.getElementById('cameraBtn'),
    uploadBtn: document.getElementById('uploadBtn'),
    imageCountDisplay: document.getElementById('imageCountDisplay'),
    imageCountText: document.getElementById('imageCountText'),
    clearAllImages: document.getElementById('clearAllImages'),
    analyzeBtn: document.getElementById('analyzeBtn'),
    analyzeLoader: document.getElementById('analyzeLoader'),
    analyzeProgress: document.getElementById('analyzeProgress'),
    progressBar: document.getElementById('progressBar'),
    progressText: document.getElementById('progressText'),
    progressStatus: document.getElementById('progressStatus'),
    
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
    
    // Navigation
    backToLocationBtn: document.getElementById('backToLocationBtn'),
    backToCaptureBtn: document.getElementById('backToCaptureBtn'),
    
    // Offline banner
    offlineBanner: document.getElementById('offlineBanner'),
};

// ========================================
// Constants
// ========================================

const MAX_IMAGES = 10;
const MAX_FILE_SIZE_MB = 10;

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
    
    // Scroll to top when showing a new section
    window.scrollTo(0, 0);
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

// Check if user is online
function isOnline() {
    return navigator.onLine;
}

// API request with timeout and better error handling
async function apiRequest(url, options = {}, timeoutMs = 30000) {
    // Check network status first
    if (!isOnline()) {
        throw new Error('No internet connection. Please check your network.');
    }
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    
    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal,
            headers: {
                ...options.headers,
                ...(state.token ? getAuthHeaders() : {}),
            },
        });
        
        clearTimeout(timeoutId);
        
        // Handle session expiration
        if (response.status === 401) {
            clearToken();
            showToast('Session expired. Please log in again.', 'warning');
            showSection('loginSection');
            throw new Error('SESSION_EXPIRED');
        }
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || 'Request failed');
        }
        
        return response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        
        if (error.name === 'AbortError') {
            throw new Error('Request timed out. Please check your connection and try again.');
        }
        
        throw error;
    }
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
        // Don't show duplicate error for session expiration (already handled)
        if (error.message !== 'SESSION_EXPIRED') {
            showToast(error.message || 'Login failed', 'error');
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Sign In</span><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>';
    }
}

function handleLogout() {
    // Confirm if there's unsaved work
    const hasUnsavedWork = state.capturedImages.length > 0 || 
                          state.detectedItems.length > 0 || 
                          state.confirmedItems.length > 0;
    
    if (hasUnsavedWork) {
        if (!confirm('You have unsaved items. Are you sure you want to logout?')) {
            return;
        }
    }
    
    clearToken();
    state.locations = [];
    state.locationTree = [];
    state.locationPath = [];
    state.labels = [];
    state.selectedLocationId = null;
    state.selectedLocationName = null;
    state.selectedLocationPath = '';
    state.capturedImages = [];
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
    
    // Reset multi-image UI
    elements.multiImageGrid.innerHTML = '';
    elements.multiImageContainer.classList.remove('active');
    elements.captureZone.classList.remove('hidden');
    elements.imageCountDisplay.style.display = 'none';
    
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
            // Ignore label loading errors if session expired (already handled)
            if (e.message !== 'SESSION_EXPIRED') {
                console.warn('Could not load labels:', e);
            }
        }
    } catch (error) {
        // Don't show error UI for session expiration - apiRequest already handled it
        if (error.message === 'SESSION_EXPIRED') {
            throw error; // Re-throw so callers know to stop
        }
        
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
                // Don't log or render if session expired (already handled)
                if (e.message === 'SESSION_EXPIRED') {
                    return;
                }
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
// Image Capture - Multi-Image Support
// ========================================

function handleCaptureZoneClick() {
    elements.imageInput.click();
}

function handleCameraClick() {
    // Use separate camera input for single photo capture
    elements.cameraInput.click();
}

function handleUploadClick() {
    elements.imageInput.click();
}

function handleAddMoreImagesClick() {
    elements.imageInput.click();
}

function handleImageSelect(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    // Check if adding these files would exceed the limit
    const remainingSlots = MAX_IMAGES - state.capturedImages.length;
    if (remainingSlots <= 0) {
        showToast(`Maximum ${MAX_IMAGES} photos allowed`, 'warning');
        event.target.value = '';
        return;
    }
    
    const filesToProcess = Array.from(files).slice(0, remainingSlots);
    if (files.length > remainingSlots) {
        showToast(`Only adding ${remainingSlots} photo(s). Maximum is ${MAX_IMAGES}.`, 'warning');
    }
    
    // Process each selected file
    filesToProcess.forEach(file => {
        if (!file.type.startsWith('image/')) {
            showToast(`Skipped ${file.name}: not an image`, 'warning');
            return;
        }
        
        // Check file size
        if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
            showToast(`${file.name} is too large (max ${MAX_FILE_SIZE_MB}MB)`, 'warning');
            return;
        }
        
        const reader = new FileReader();
        reader.onload = (e) => {
            state.capturedImages.push({
                file: file,
                dataUrl: e.target.result,
                additionalImages: [],     // Additional images for the same item
                separateItems: false,     // If true, separate into multiple items (default: keep as one)
                extraInstructions: '',    // User hint about image contents
            });
            updateMultiImageUI();
        };
        reader.readAsDataURL(file);
    });
    
    // Reset input so same file can be selected again
    event.target.value = '';
}

function handleCameraCapture(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    
    // Check image limit
    if (state.capturedImages.length >= MAX_IMAGES) {
        showToast(`Maximum ${MAX_IMAGES} photos allowed`, 'warning');
        event.target.value = '';
        return;
    }
    
    if (!file.type.startsWith('image/')) {
        showToast('Please capture an image', 'error');
        return;
    }
    
    // Check file size
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        showToast(`Photo is too large (max ${MAX_FILE_SIZE_MB}MB)`, 'warning');
        event.target.value = '';
        return;
    }
    
    const reader = new FileReader();
    reader.onload = (e) => {
        state.capturedImages.push({
            file: file,
            dataUrl: e.target.result,
            additionalImages: [],     // Additional images for the same item
            separateItems: false,     // If true, separate into multiple items (default: keep as one)
            extraInstructions: '',    // User hint about image contents
        });
        updateMultiImageUI();
    };
    reader.readAsDataURL(file);
    
    // Reset input
    event.target.value = '';
}

function updateMultiImageUI() {
    const hasImages = state.capturedImages.length > 0;
    const count = state.capturedImages.length;
    const atMaxImages = count >= MAX_IMAGES;
    
    // Toggle visibility of capture zone vs multi-image container
    if (hasImages) {
        elements.captureZone.classList.add('hidden');
        elements.multiImageContainer.classList.add('active');
    } else {
        elements.captureZone.classList.remove('hidden');
        elements.multiImageContainer.classList.remove('active');
    }
    
    // Update image count display
    if (hasImages) {
        elements.imageCountDisplay.style.display = 'flex';
        const remaining = MAX_IMAGES - count;
        if (atMaxImages) {
            elements.imageCountText.textContent = `${count} photos selected (maximum reached)`;
        } else {
            elements.imageCountText.textContent = `${count} photo${count !== 1 ? 's' : ''} selected${remaining < 3 ? ` (${remaining} more allowed)` : ''}`;
        }
    } else {
        elements.imageCountDisplay.style.display = 'none';
    }
    
    // Disable/enable capture buttons when at max images
    const cameraBtn = document.getElementById('cameraBtn');
    const uploadBtn = document.getElementById('uploadBtn');
    const addMoreZone = document.getElementById('addMoreImagesZone');
    
    if (cameraBtn) {
        cameraBtn.disabled = atMaxImages;
        cameraBtn.style.opacity = atMaxImages ? '0.5' : '1';
        cameraBtn.style.cursor = atMaxImages ? 'not-allowed' : 'pointer';
    }
    if (uploadBtn) {
        uploadBtn.disabled = atMaxImages;
        uploadBtn.style.opacity = atMaxImages ? '0.5' : '1';
        uploadBtn.style.cursor = atMaxImages ? 'not-allowed' : 'pointer';
    }
    if (addMoreZone) {
        addMoreZone.style.opacity = atMaxImages ? '0.5' : '1';
        addMoreZone.style.cursor = atMaxImages ? 'not-allowed' : 'pointer';
        addMoreZone.style.pointerEvents = atMaxImages ? 'none' : 'auto';
    }
    
    // Render image grid
    renderMultiImageGrid();
    
    // Enable/disable analyze button and update text
    elements.analyzeBtn.disabled = !hasImages;
    const analyzeSpan = elements.analyzeBtn.querySelector('span');
    if (analyzeSpan) {
        analyzeSpan.textContent = hasImages ? `Analyze ${count} Photo${count !== 1 ? 's' : ''} with AI` : 'Analyze with AI';
    }
}

function renderMultiImageGrid() {
    elements.multiImageGrid.innerHTML = '';
    
    state.capturedImages.forEach((img, index) => {
        const item = document.createElement('div');
        item.className = 'image-row-card';
        item.dataset.index = index;
        
        const additionalImages = img.additionalImages || [];
        const additionalImagesHtml = renderCaptureAdditionalImages(additionalImages, index);
        
        // Check if card has any expanded content (additional images, separate checked, or instructions)
        const hasExpandedContent = additionalImages.length > 0 || img.separateItems || img.extraInstructions;
        const isExpanded = img.isExpanded || false;
        
        item.innerHTML = `
            <div class="image-row-header">
                <div class="image-row-thumb">
                    <img src="${img.dataUrl}" alt="Photo ${index + 1}">
                    <span class="image-row-index">${index + 1}</span>
                </div>
                <div class="image-row-info">
                    <span class="image-row-name">${escapeHtml(img.file.name)}</span>
                    <span class="image-row-size">${formatFileSize(img.file.size)}${additionalImages.length > 0 ? ` • +${additionalImages.length} more` : ''}</span>
                </div>
                <div class="image-row-actions">
                    <button type="button" class="btn-icon image-row-toggle ${isExpanded ? 'expanded' : ''}" onclick="handleToggleImageOptions(${index})" title="${isExpanded ? 'Hide options' : 'Show options'}">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>
                    <button type="button" class="btn-icon image-row-remove" onclick="handleRemoveMultiImage(${index})" title="Remove photo">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>
            </div>
            
            <!-- Collapsible Options Section -->
            <div class="image-row-collapsible ${isExpanded ? 'expanded' : ''}">
                <div class="image-row-collapsible-inner">
                    <!-- Additional Images for this item -->
                    <div class="image-row-additional">
                        <div class="additional-images-capture-grid" id="captureAdditionalGrid${index}">
                            ${additionalImagesHtml}
                            <button type="button" class="add-capture-image-btn" onclick="handleAddCaptureImage(${index})" title="Add more photos for this item">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="12" y1="5" x2="12" y2="19"></line>
                                    <line x1="5" y1="12" x2="19" y2="12"></line>
                                </svg>
                            </button>
                        </div>
                        <input type="file" id="captureAdditionalInput${index}" accept="image/*" multiple style="display: none;" onchange="handleCaptureAdditionalImageSelect(event, ${index})">
                    </div>
                    
                    <div class="image-row-options">
                        <label class="image-option-checkbox">
                            <input type="checkbox" 
                                ${img.separateItems ? 'checked' : ''} 
                                onchange="handleImageOptionChange(${index}, 'separateItems', this.checked)">
                            <span class="checkbox-visual">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                                    <polyline points="20 6 9 17 4 12"></polyline>
                                </svg>
                            </span>
                            <span class="checkbox-label">Separate into multiple items</span>
                        </label>
                        <div class="image-option-hint">
                            <input type="text" 
                                class="hint-input"
                                placeholder="Optional: describe what's in this photo..."
                                value="${escapeHtml(img.extraInstructions || '')}"
                                onchange="handleImageOptionChange(${index}, 'extraInstructions', this.value)"
                                oninput="handleImageOptionChange(${index}, 'extraInstructions', this.value)">
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        elements.multiImageGrid.appendChild(item);
    });
}

// Render additional images thumbnails for capture section
function renderCaptureAdditionalImages(images, rowIndex) {
    if (!images || images.length === 0) return '';
    
    return images.map((img, imgIndex) => `
        <div class="capture-additional-thumb">
            <img src="${img.dataUrl}" alt="Additional ${imgIndex + 1}">
            <button type="button" class="capture-thumb-remove" onclick="handleRemoveCaptureAdditionalImage(${rowIndex}, ${imgIndex})">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        </div>
    `).join('');
}

// Handle adding additional image to a capture row
function handleAddCaptureImage(rowIndex) {
    document.getElementById(`captureAdditionalInput${rowIndex}`).click();
}

// Handle selection of additional images for a capture row
function handleCaptureAdditionalImageSelect(event, rowIndex) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    const capturedImage = state.capturedImages[rowIndex];
    if (!capturedImage.additionalImages) capturedImage.additionalImages = [];
    
    Array.from(files).forEach(file => {
        if (!file.type.startsWith('image/')) return;
        
        // Check file size
        if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
            showToast(`${file.name} is too large (max ${MAX_FILE_SIZE_MB}MB)`, 'warning');
            return;
        }
        
        const reader = new FileReader();
        reader.onload = (e) => {
            capturedImage.additionalImages.push({
                file: file,
                dataUrl: e.target.result,
            });
            updateCaptureAdditionalImagesUI(rowIndex);
        };
        reader.readAsDataURL(file);
    });
    
    // Reset input
    event.target.value = '';
}

// Handle removing an additional image from a capture row
function handleRemoveCaptureAdditionalImage(rowIndex, imageIndex) {
    const capturedImage = state.capturedImages[rowIndex];
    if (capturedImage.additionalImages) {
        capturedImage.additionalImages.splice(imageIndex, 1);
        updateCaptureAdditionalImagesUI(rowIndex);
    }
}

// Update the additional images grid for a specific capture row
function updateCaptureAdditionalImagesUI(rowIndex) {
    const grid = document.getElementById(`captureAdditionalGrid${rowIndex}`);
    if (!grid) return;
    
    const capturedImage = state.capturedImages[rowIndex];
    const images = capturedImage.additionalImages || [];
    
    // Update thumbnails
    grid.innerHTML = renderCaptureAdditionalImages(images, rowIndex) + `
        <button type="button" class="add-capture-image-btn" onclick="handleAddCaptureImage(${rowIndex})" title="Add more photos for this item">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
        </button>
    `;
    
    // Update the image row info to show additional count
    const rowCard = grid.closest('.image-row-card');
    if (rowCard) {
        const sizeSpan = rowCard.querySelector('.image-row-size');
        if (sizeSpan) {
            const baseSize = formatFileSize(capturedImage.file.size);
            sizeSpan.textContent = images.length > 0 ? `${baseSize} • +${images.length} more` : baseSize;
        }
    }
}

// Handle image option changes (checkbox or hint input)
function handleImageOptionChange(index, option, value) {
    if (index >= 0 && index < state.capturedImages.length) {
        state.capturedImages[index][option] = value;
    }
}

// Format file size for display
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function handleRemoveMultiImage(index) {
    state.capturedImages.splice(index, 1);
    updateMultiImageUI();
}

function handleToggleImageOptions(index) {
    const img = state.capturedImages[index];
    if (img) {
        img.isExpanded = !img.isExpanded;
        // Update UI without full re-render for smoother animation
        const card = document.querySelector(`.image-row-card[data-index="${index}"]`);
        if (card) {
            const collapsible = card.querySelector('.image-row-collapsible');
            const toggleBtn = card.querySelector('.image-row-toggle');
            if (collapsible) {
                collapsible.classList.toggle('expanded', img.isExpanded);
            }
            if (toggleBtn) {
                toggleBtn.classList.toggle('expanded', img.isExpanded);
                toggleBtn.title = img.isExpanded ? 'Hide options' : 'Show options';
            }
        }
    }
}

function handleClearAllImages() {
    // Confirm before clearing multiple images
    if (state.capturedImages.length > 1) {
        if (!confirm(`Remove all ${state.capturedImages.length} photos?`)) {
            return;
        }
    }
    
    state.capturedImages = [];
    updateMultiImageUI();
    elements.imageInput.value = '';
    elements.cameraInput.value = '';
}

async function handleAnalyze() {
    if (state.capturedImages.length === 0) {
        showToast('Please capture or upload at least one image', 'warning');
        return;
    }
    
    const totalImages = state.capturedImages.length;
    
    // Hide analyze button and show progress
    elements.analyzeBtn.style.display = 'none';
    elements.analyzeProgress.style.display = 'block';
    
    // Initialize progress
    updateProgress(0, totalImages, 'Starting analysis...');
    
    // Store all detected items from all images
    const allDetectedItems = [];
    let processedCount = 0;
    let errorCount = 0;
    
    // Process images in parallel (max 3 concurrent)
    const concurrentLimit = 3;
    const imageQueue = [...state.capturedImages.map((img, index) => ({ 
        ...img, 
        index,
        additionalImages: img.additionalImages || [],
        separateItems: img.separateItems || false,
        extraInstructions: img.extraInstructions || '',
    }))];
    const activePromises = new Map();
    
    const processImage = async (imageData) => {
        const { file, dataUrl, index, additionalImages: captureAdditionalImages, separateItems, extraInstructions } = imageData;
        
        try {
            const formData = new FormData();
            formData.append('image', file);
            
            // Add additional images for this item (for AI analysis)
            captureAdditionalImages.forEach((addImg, addIndex) => {
                formData.append('additional_images', addImg.file);
            });
            
            // Invert logic: separateItems=true means separate, so single_item should be false
            // separateItems=false means keep as one, so single_item should be true
            formData.append('single_item', separateItems ? 'false' : 'true');
            if (extraInstructions && extraInstructions.trim()) {
                formData.append('extra_instructions', extraInstructions.trim());
            }
            
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
            
            if (data.items && data.items.length > 0) {
                // Add source image info to each detected item
                // Map extended fields from API response to advancedFields object
                console.log('Detection API response items:', JSON.stringify(data.items, null, 2));
                
                const itemsWithSource = data.items.map(item => {
                    // Check if any extended fields were detected
                    const hasExtendedFields = item.manufacturer || item.model_number || 
                        item.serial_number || item.purchase_price || item.purchase_from || item.notes;
                    
                    console.log(`Item "${item.name}" extended fields:`, {
                        manufacturer: item.manufacturer,
                        model_number: item.model_number,
                        serial_number: item.serial_number,
                        purchase_price: item.purchase_price,
                        purchase_from: item.purchase_from,
                        notes: item.notes,
                        hasExtendedFields
                    });
                    
                    return {
                        ...item,
                        // Preserve additional images from capture phase
                        additionalImages: captureAdditionalImages.map(img => ({
                            file: img.file,
                            dataUrl: img.dataUrl
                        })),
                        // Map API response extended fields to advancedFields
                        advancedFields: {
                            manufacturer: item.manufacturer || '',
                            modelNumber: item.model_number || '',
                            serialNumber: item.serial_number || '',
                            purchasePrice: item.purchase_price || '',
                            purchaseFrom: item.purchase_from || '',
                            notes: item.notes || '',
                        },
                        // Auto-show advanced section if extended fields were detected
                        showAdvanced: hasExtendedFields,
                        sourceImageIndex: index,
                        sourceImageDataUrl: dataUrl,
                        sourceImageFile: file,
                    };
                });
                
                return itemsWithSource;
            }
            
            return [];
        } catch (error) {
            console.error(`Failed to process image ${index + 1}:`, error);
            errorCount++;
            return [];
        }
    };
    
    // Process images with concurrency control
    while (imageQueue.length > 0 || activePromises.size > 0) {
        // Start new tasks up to the concurrency limit
        while (imageQueue.length > 0 && activePromises.size < concurrentLimit) {
            const imageData = imageQueue.shift();
            const promise = processImage(imageData).then(items => {
                processedCount++;
                updateProgress(processedCount, totalImages, `Processing photo ${processedCount} of ${totalImages}...`);
                
                if (items.length > 0) {
                    allDetectedItems.push(...items);
                }
                
                activePromises.delete(imageData.index);
                return items;
            });
            
            activePromises.set(imageData.index, promise);
        }
        
        // Wait for at least one to complete
        if (activePromises.size > 0) {
            await Promise.race(activePromises.values());
        }
    }
    
    // Hide progress
    elements.analyzeProgress.style.display = 'none';
    elements.analyzeBtn.style.display = 'flex';
    
    // Check results
    if (allDetectedItems.length === 0) {
        if (errorCount > 0) {
            showToast(`Analysis failed for ${errorCount} image(s). Please check your connection and try again.`, 'error');
        } else {
            showToast('No items detected. Try: better lighting, closer photos, or less cluttered backgrounds.', 'warning');
        }
        return;
    }
    
    // Set detected items and proceed to review
    state.detectedItems = allDetectedItems;
    state.currentItemIndex = 0;
    
    let successMsg = `Detected ${allDetectedItems.length} item(s) from ${totalImages} photo${totalImages !== 1 ? 's' : ''}`;
    if (errorCount > 0) {
        successMsg += ` (${errorCount} failed)`;
    }
    showToast(successMsg, 'success');
    
    renderItemCards();
    showSection('reviewSection');
}

function updateProgress(current, total, statusText) {
    const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
    
    elements.progressBar.style.width = `${percentage}%`;
    elements.progressText.textContent = `${current} / ${total}`;
    elements.progressStatus.textContent = statusText;
}

// ========================================
// Item Review
// ========================================

function renderItemCards() {
    elements.itemCarousel.innerHTML = '';
    
    // In editing from summary mode, show the single item
    // Otherwise, show the current item in the sequence
    const index = state.currentItemIndex;
    const item = state.detectedItems[index];
    
    // If no item at current index, we're done - go to summary
    if (!item && !state.isEditingFromSummary) {
        if (state.confirmedItems.length > 0) {
            renderSummary();
            showSection('summarySection');
        }
        return;
    }
    
    if (!item) return;
    
    // Render only the current item
    const card = document.createElement('div');
    card.className = 'item-card active';
    card.dataset.index = index;
    
    const imageCount = item.additionalImages?.length || 0;
        const advancedFields = item.advancedFields || {};
        const showAdvanced = item.showAdvanced || false;
        const selectedLabelIds = item.label_ids || [];
        
        // Source image thumbnail
        const sourceImageHtml = item.sourceImageDataUrl ? `
            <div class="source-image-header">
                <div class="source-image-thumb">
                    <img src="${item.sourceImageDataUrl}" alt="Source photo">
                </div>
                <div class="source-image-info">
                    <span class="source-label">Detected from photo ${(item.sourceImageIndex || 0) + 1}</span>
                </div>
            </div>
        ` : '';
        
        // Cover image selection section
        const allItemImages = getDetectedItemImages(item);
        const coverImageHtml = allItemImages.length > 0 ? `
            <div class="cover-image-section">
                <label>Cover Image</label>
                <div class="cover-image-preview" id="coverImagePreview${index}">
                    <img src="${item.coverImageDataUrl || allItemImages[item.selectedImageIndex || 0]?.dataUrl || allItemImages[0]?.dataUrl}" alt="Cover preview">
                    <div class="cover-image-hint">Tap an image below to select & crop</div>
                </div>
                <div class="cover-image-gallery" id="coverImageGallery${index}">
                    ${allItemImages.map((img, imgIdx) => `
                        <div class="cover-gallery-item ${imgIdx === (item.selectedImageIndex || 0) ? 'selected' : ''}" 
                             data-index="${imgIdx}" 
                             onclick="handleReviewCoverImageSelect(${index}, ${imgIdx})">
                            <img src="${img.dataUrl}" alt="Image ${imgIdx + 1}">
                            <div class="crop-icon">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M6.13 1L6 16a2 2 0 0 0 2 2h15"></path>
                                    <path d="M1 6.13L16 6a2 2 0 0 1 2 2v15"></path>
                                </svg>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : '';
        
        card.innerHTML = `
            ${sourceImageHtml}
            ${coverImageHtml}
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
                
                <!-- Correction Section (hide when editing from summary) -->
                ${!state.isEditingFromSummary ? `
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
                ` : ''}
            </form>
        `;
    
    elements.itemCarousel.appendChild(card);
    updateItemNavigation();
}

// Get all images for a detected item (for cover image selection)
function getDetectedItemImages(item) {
    const images = [];
    
    // Add source image first
    if (item.sourceImageDataUrl && item.sourceImageFile) {
        images.push({
            file: item.sourceImageFile,
            dataUrl: item.sourceImageDataUrl,
            isPrimary: true,
            isSource: true
        });
    }
    
    // Add additional images
    if (item.additionalImages && item.additionalImages.length > 0) {
        item.additionalImages.forEach(img => {
            if (img.dataUrl) {
                images.push({
                    file: img.file,
                    dataUrl: img.dataUrl,
                    isPrimary: false
                });
            }
        });
    }
    
    return images;
}

// Handle cover image selection in review section
function handleReviewCoverImageSelect(itemIndex, imageIndex) {
    const item = state.detectedItems[itemIndex];
    item.selectedImageIndex = imageIndex;
    
    // Update selected state in gallery
    const gallery = document.getElementById(`coverImageGallery${itemIndex}`);
    if (gallery) {
        gallery.querySelectorAll('.cover-gallery-item').forEach((el, i) => {
            el.classList.toggle('selected', i === imageIndex);
        });
    }
    
    // Open cropper for this image
    openReviewImageCropper(itemIndex, imageIndex);
}

// Open image cropper in review mode
function openReviewImageCropper(itemIndex, imageIndex) {
    const item = state.detectedItems[itemIndex];
    const allImages = getDetectedItemImages(item);
    
    if (!allImages[imageIndex]) return;
    
    // Store reference to which item we're editing
    reviewCropperState.itemIndex = itemIndex;
    reviewCropperState.imageIndex = imageIndex;
    
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

// State for review cropper
const reviewCropperState = {
    itemIndex: null,
    imageIndex: null
};

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
        
        // Add the source image for this specific item
        if (item.sourceImageFile) {
            formData.append('image', item.sourceImageFile);
        } else {
            showToast('Source image not available for this item', 'error');
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
            // Check if any extended fields were returned
            const hasExtendedFields = correctedItem.manufacturer || correctedItem.model_number ||
                correctedItem.serial_number || correctedItem.purchase_price ||
                correctedItem.purchase_from || correctedItem.notes;
            
            state.detectedItems[index] = {
                ...item,
                name: correctedItem.name,
                quantity: correctedItem.quantity,
                description: correctedItem.description || '',
                label_ids: correctedItem.label_ids || [],
                advancedFields: {
                    manufacturer: correctedItem.manufacturer || item.advancedFields?.manufacturer || '',
                    modelNumber: correctedItem.model_number || item.advancedFields?.modelNumber || '',
                    serialNumber: correctedItem.serial_number || item.advancedFields?.serialNumber || '',
                    purchasePrice: correctedItem.purchase_price || item.advancedFields?.purchasePrice || '',
                    purchaseFrom: correctedItem.purchase_from || item.advancedFields?.purchaseFrom || '',
                    notes: correctedItem.notes || item.advancedFields?.notes || '',
                },
                showAdvanced: hasExtendedFields || item.showAdvanced,
            };
            
            showToast('Item corrected successfully!', 'success');
        } else {
            // Multiple items - replace current item with new items
            // Preserve source image info for all split items
            const newItems = data.items.map(correctedItem => {
                // Check if any extended fields were returned
                const hasExtendedFields = correctedItem.manufacturer || correctedItem.model_number ||
                    correctedItem.serial_number || correctedItem.purchase_price ||
                    correctedItem.purchase_from || correctedItem.notes;

                return {
                    name: correctedItem.name,
                    quantity: correctedItem.quantity,
                    description: correctedItem.description || '',
                    label_ids: correctedItem.label_ids || [],
                    additionalImages: [],
                    advancedFields: {
                        manufacturer: correctedItem.manufacturer || '',
                        modelNumber: correctedItem.model_number || '',
                        serialNumber: correctedItem.serial_number || '',
                        purchasePrice: correctedItem.purchase_price || '',
                        purchaseFrom: correctedItem.purchase_from || '',
                        notes: correctedItem.notes || '',
                    },
                    showAdvanced: hasExtendedFields,
                    sourceImageIndex: item.sourceImageIndex,
                    sourceImageDataUrl: item.sourceImageDataUrl,
                    sourceImageFile: item.sourceImageFile,
                };
            });
            
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
    
    // Update additional images thumbnails
    grid.innerHTML = renderAdditionalImageThumbnails(images, index) + `
        <button type="button" class="add-image-btn" onclick="handleAddImage(${index})">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            <span>Add Photo</span>
        </button>
    `;
    
    // Update cover image gallery (to include new additional images)
    updateCoverImageGallery(index);
    
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

// Update the cover image gallery for a specific item
function updateCoverImageGallery(index) {
    const gallery = document.getElementById(`coverImageGallery${index}`);
    const preview = document.getElementById(`coverImagePreview${index}`);
    if (!gallery) return;
    
    const item = state.detectedItems[index];
    const allItemImages = getDetectedItemImages(item);
    
    if (allItemImages.length === 0) return;
    
    // Update gallery thumbnails
    gallery.innerHTML = allItemImages.map((img, imgIdx) => `
        <div class="cover-gallery-item ${imgIdx === (item.selectedImageIndex || 0) ? 'selected' : ''}" 
             data-index="${imgIdx}" 
             onclick="handleReviewCoverImageSelect(${index}, ${imgIdx})">
            <img src="${img.dataUrl}" alt="Image ${imgIdx + 1}">
            <div class="crop-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M6.13 1L6 16a2 2 0 0 0 2 2h15"></path>
                    <path d="M1 6.13L16 6a2 2 0 0 1 2 2v15"></path>
                </svg>
            </div>
        </div>
    `).join('');
    
    // Update preview image if needed
    if (preview && !item.coverImageDataUrl) {
        const selectedIdx = item.selectedImageIndex || 0;
        const previewImg = preview.querySelector('img');
        if (previewImg && allItemImages[selectedIdx]) {
            previewImg.src = allItemImages[selectedIdx].dataUrl;
        }
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
        
        // Add the source image for this specific item first
        if (item.sourceImageFile) {
            formData.append('images', item.sourceImageFile);
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
    
    // Show progress as "current / total" (total stays fixed)
    elements.itemCounter.textContent = `${current} / ${total}`;
    
    // Hide prev/next buttons - user can only confirm or skip
    elements.prevItem.style.display = 'none';
    elements.nextItem.style.display = 'none';
    
    // Update button text for editing from summary mode
    if (state.isEditingFromSummary) {
        elements.confirmItem.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            <span>Save Changes</span>
        `;
        elements.skipItem.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
            <span>Cancel</span>
        `;
        // Show nav buttons when editing (to allow cancel without changing position)
        elements.prevItem.style.display = '';
        elements.nextItem.style.display = '';
        elements.prevItem.disabled = true;
        elements.nextItem.disabled = true;
    } else {
        elements.confirmItem.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            <span>Confirm</span>
        `;
        elements.skipItem.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
            <span>Skip</span>
        `;
    }
}

function handlePrevItem() {
    // Navigation is disabled in normal mode, but kept for editing mode
    if (state.currentItemIndex > 0) {
        state.currentItemIndex--;
        renderItemCards();
    }
}

function handleNextItem() {
    // Navigation is disabled in normal mode, but kept for editing mode
    if (state.currentItemIndex < state.detectedItems.length - 1) {
        state.currentItemIndex++;
        renderItemCards();
    }
}

function handleSkipItem() {
    // If editing from summary, cancel and go back
    if (state.isEditingFromSummary) {
        cancelEditFromSummary();
        return;
    }
    moveToNextOrSummary();
}

function cancelEditFromSummary() {
    state.isEditingFromSummary = false;
    state.editingConfirmedIndex = null;
    state.detectedItems = [];
    state.currentItemIndex = 0;
    renderSummary();
    showSection('summarySection');
}

function handleConfirmItem() {
    // Get the actual item index from the card's data attribute
    const activeCard = document.querySelector('.item-card.active');
    const index = activeCard ? parseInt(activeCard.dataset.index) : state.currentItemIndex;
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
    
    console.log(`Confirming item "${nameInput.value}" - DEBUG INFO:`);
    console.log('  - Item from state:', JSON.stringify(item, null, 2));
    console.log('  - advancedFields object:', item.advancedFields);
    console.log('  - Form DOM values:', {
        serialNumber,
        modelNumber,
        manufacturer,
        purchasePrice,
        purchaseFrom,
        notes,
    });
    console.log('  - DOM element exists?', {
        serialNumberEl: !!document.getElementById(`itemSerialNumber${index}`),
        modelNumberEl: !!document.getElementById(`itemModelNumber${index}`),
        manufacturerEl: !!document.getElementById(`itemManufacturer${index}`),
    });
    
    // Collect images to upload (source image + additional) with dataUrls for preview
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
        // Use the source image from this specific item (each item tracks its source photo)
        if (item.sourceImageFile && item.sourceImageDataUrl) {
            imagesToUpload.push({ 
                file: item.sourceImageFile, 
                isPrimary: true,
                dataUrl: item.sourceImageDataUrl,
                isOriginal: true,
                sourceImageIndex: item.sourceImageIndex
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
        coverImageDataUrl: item.coverImageDataUrl || null, // Preserve cropped cover image
        selectedImageIndex: item.selectedImageIndex || 0,   // Preserve selected image index
        sourceImageIndex: item.sourceImageIndex, // Track which photo this came from
    };
    
    // If editing from summary, update existing confirmed item
    if (state.isEditingFromSummary && state.editingConfirmedIndex !== null) {
        state.confirmedItems[state.editingConfirmedIndex] = confirmedItem;
        state.isEditingFromSummary = false;
        state.editingConfirmedIndex = null;
        state.detectedItems = [];
        state.currentItemIndex = 0;
        renderSummary();
        showSection('summarySection');
        showToast(`"${confirmedItem.name}" updated`, 'success');
        return;
    }
    
    state.confirmedItems.push(confirmedItem);
    
    // Mark the item as confirmed (for reference, not for hiding)
    item.confirmed = true;
    
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
        renderItemCards(); // Re-render to show next item
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
            (item.images && item.images.length > 0 ? item.images[0].dataUrl : null);
        
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
        
        // Collect and deduplicate images from merged items
        // Use dataUrl as the unique identifier for each image
        const seenDataUrls = new Set();
        const uniqueImages = [];
        
        // Helper to add an image if not already seen
        const addUniqueImage = (img) => {
            if (!img || !img.dataUrl) return;
            
            // Skip if we've already seen this exact image (by dataUrl)
            if (seenDataUrls.has(img.dataUrl)) {
                return;
            }
            
            seenDataUrls.add(img.dataUrl);
            uniqueImages.push({
                file: img.file,
                dataUrl: img.dataUrl,
                isPrimary: false,
                sourceImageIndex: img.sourceImageIndex,
            });
        };
        
        itemsToMerge.forEach(item => {
            // First, check the item.images array (primary source for confirmed items)
            if (item.images && item.images.length > 0) {
                item.images.forEach(img => addUniqueImage(img));
            }
            
            // Also check for coverImageDataUrl (cropped image)
            if (item.coverImageDataUrl && !seenDataUrls.has(item.coverImageDataUrl)) {
                // If there's a cropped cover image that's different from what's in images,
                // we don't add it separately since the cropped version replaced the original
            }
            
            // Check sourceImageDataUrl as fallback (for items that might not have images array populated)
            if (item.sourceImageDataUrl && item.sourceImageFile && !seenDataUrls.has(item.sourceImageDataUrl)) {
                addUniqueImage({
                    file: item.sourceImageFile,
                    dataUrl: item.sourceImageDataUrl,
                    sourceImageIndex: item.sourceImageIndex,
                });
            }
        });
        
        // If there were duplicate images, notify the user
        const totalImagesBeforeDedup = itemsToMerge.reduce((count, item) => 
            count + (item.images?.length || 0), 0);
        const dupesRemoved = totalImagesBeforeDedup - uniqueImages.length;
        
        // Create merged item for review
        // Check if any extended fields were returned from the merge
        const hasExtendedFields = response.manufacturer || response.model_number ||
            response.serial_number || response.purchase_price ||
            response.purchase_from || response.notes;
        
        const mergedItem = {
            name: response.name,
            quantity: response.quantity,
            description: response.description,
            label_ids: response.label_ids,
            additionalImages: [],
            advancedFields: {
                manufacturer: response.manufacturer || '',
                modelNumber: response.model_number || '',
                serialNumber: response.serial_number || '',
                purchasePrice: response.purchase_price || '',
                purchaseFrom: response.purchase_from || '',
                notes: response.notes || '',
            },
            showAdvanced: hasExtendedFields,
            // Use the first unique image as source
            sourceImageIndex: uniqueImages[0]?.sourceImageIndex,
            sourceImageDataUrl: uniqueImages[0]?.dataUrl,
            sourceImageFile: uniqueImages[0]?.file,
            // Store original items for reference
            _mergedFrom: indices,
            _mergedImages: uniqueImages,
        };
        
        // Remove the original items from confirmed (in reverse order to maintain indices)
        for (let i = indices.length - 1; i >= 0; i--) {
            state.confirmedItems.splice(indices[i], 1);
        }
        
        // Add merged item to detected items for review
        state.detectedItems = [mergedItem];
        state.currentItemIndex = 0;
        state.isMergeReview = true;
        state.mergedItemImages = uniqueImages;
        
        // Go to review section for the merged item
        renderItemCards();
        showSection('reviewSection');
        
        let mergeMsg = 'Items merged! Review the combined item.';
        if (dupesRemoved > 0) {
            mergeMsg += ` (${dupesRemoved} duplicate image${dupesRemoved !== 1 ? 's' : ''} removed)`;
        }
        showToast(mergeMsg, 'success');
        
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
    const item = state.confirmedItems[index];
    
    // Convert confirmed item back to a detected item for editing
    const editableItem = {
        name: item.name,
        quantity: item.quantity,
        description: item.description || '',
        label_ids: item.label_ids || [],
        additionalImages: [],
        advancedFields: {
            serialNumber: item.serial_number || '',
            modelNumber: item.model_number || '',
            manufacturer: item.manufacturer || '',
            purchasePrice: item.purchase_price || '',
            purchaseFrom: item.purchase_from || '',
            notes: item.notes || '',
        },
        showAdvanced: !!(item.serial_number || item.model_number || item.manufacturer || 
                        item.purchase_price || item.purchase_from || item.notes),
        sourceImageIndex: item.sourceImageIndex,
        sourceImageDataUrl: item.images && item.images.length > 0 ? item.images[0].dataUrl : null,
        sourceImageFile: item.images && item.images.length > 0 ? item.images[0].file : null,
        coverImageDataUrl: item.coverImageDataUrl,
        selectedImageIndex: item.selectedImageIndex || 0,
    };
    
    // Add additional images (skip the first one which is the source)
    if (item.images && item.images.length > 1) {
        editableItem.additionalImages = item.images.slice(1).map(img => ({
            file: img.file,
            dataUrl: img.dataUrl
        }));
    }
    
    // Set up state for editing from summary
    state.isEditingFromSummary = true;
    state.editingConfirmedIndex = index;
    state.detectedItems = [editableItem];
    state.currentItemIndex = 0;
    
    // Navigate to review section
    renderItemCards();
    showSection('reviewSection');
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
    
    return images;
}

function updateEditPreviewImage(item) {
    const previewImg = document.getElementById('editPreviewImg');
    const allImages = getAllItemImages(item);
    
    if (item.coverImageDataUrl) {
        previewImg.src = item.coverImageDataUrl;
    } else if (allImages.length > 0) {
        const selectedIdx = item.selectedImageIndex || 0;
        previewImg.src = allImages[selectedIdx]?.dataUrl || allImages[0]?.dataUrl || '';
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
    // Standard transform - rotation compensation is handled in rotation functions
    image.style.transform = `translate(${cropperState.translateX}px, ${cropperState.translateY}px) scale(${cropperState.scale}) rotate(${cropperState.rotation}deg)`;
}

function getFrameCenterOffset() {
    // Calculate the offset from container center to frame center
    const container = document.getElementById('cropperContainer');
    const frame = document.getElementById('cropperFrame');
    
    if (!container || !frame) return { x: 0, y: 0 };
    
    const containerRect = container.getBoundingClientRect();
    const frameRect = frame.getBoundingClientRect();
    
    const frameCenterX = (frameRect.left - containerRect.left) + frameRect.width / 2;
    const frameCenterY = (frameRect.top - containerRect.top) + frameRect.height / 2;
    const containerCenterX = containerRect.width / 2;
    const containerCenterY = containerRect.height / 2;
    
    return {
        x: frameCenterX - containerCenterX,
        y: frameCenterY - containerCenterY
    };
}

function rotateAroundFrameCenter(newRotation) {
    // Rotate around the crop frame center instead of image center
    // This keeps the cropped area visually stable while rotating
    
    const oldRotation = cropperState.rotation;
    const deltaRotation = newRotation - oldRotation;
    
    if (Math.abs(deltaRotation) < 0.01) return; // No change
    
    const deltaRad = (deltaRotation * Math.PI) / 180;
    
    // Get the current point that's at the frame center (in image-relative coordinates)
    // This is the point we want to keep fixed
    const frameOffset = getFrameCenterOffset();
    
    // Current position of frame center relative to image center
    // (accounting for current translation)
    const pivotX = frameOffset.x - cropperState.translateX;
    const pivotY = frameOffset.y - cropperState.translateY;
    
    // When we rotate, the pivot point will move. We need to compensate.
    // The point at (pivotX, pivotY) will rotate around (0,0) by deltaRotation
    const cos = Math.cos(deltaRad);
    const sin = Math.sin(deltaRad);
    
    // New position of pivot point after rotation
    const newPivotX = pivotX * cos - pivotY * sin;
    const newPivotY = pivotX * sin + pivotY * cos;
    
    // Adjust translation to keep frame center fixed
    cropperState.translateX += (pivotX - newPivotX);
    cropperState.translateY += (pivotY - newPivotY);
    cropperState.rotation = newRotation;
    
    updateCropperTransform();
}

function handleRotateLeft() {
    // Quick 90° rotation around frame center
    let newRotation = Math.round((cropperState.rotation - 90) / 90) * 90;
    if (newRotation < -180) newRotation += 360;
    
    rotateAroundFrameCenter(newRotation);
    
    document.getElementById('rotationSlider').value = cropperState.rotation;
    document.getElementById('rotationLabel').textContent = `${cropperState.rotation}°`;
}

function handleRotateRight() {
    // Quick 90° rotation around frame center
    let newRotation = Math.round((cropperState.rotation + 90) / 90) * 90;
    if (newRotation > 180) newRotation -= 360;
    
    rotateAroundFrameCenter(newRotation);
    
    document.getElementById('rotationSlider').value = cropperState.rotation;
    document.getElementById('rotationLabel').textContent = `${cropperState.rotation}°`;
}

function handleRotationSlider(e) {
    const newRotation = parseInt(e.target.value);
    rotateAroundFrameCenter(newRotation);
    document.getElementById('rotationLabel').textContent = `${cropperState.rotation}°`;
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
            
            // Check if we're cropping from review section (detected items)
            if (reviewCropperState.itemIndex !== null) {
                const item = state.detectedItems[reviewCropperState.itemIndex];
                if (item) {
                    item.coverImageDataUrl = croppedDataUrl;
                    item.selectedImageIndex = reviewCropperState.imageIndex;
                    
                    // Update preview in review section
                    const preview = document.getElementById(`coverImagePreview${reviewCropperState.itemIndex}`);
                    if (preview) {
                        const previewImg = preview.querySelector('img');
                        if (previewImg) {
                            previewImg.src = croppedDataUrl;
                        }
                    }
                }
                
                // Reset review cropper state
                reviewCropperState.itemIndex = null;
                reviewCropperState.imageIndex = null;
                
                closeCropperModal();
                showToast('Cover image set', 'success');
                return;
            }
            
            // Save to confirmed item (editing from summary modal - legacy code)
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
    state.capturedImages = [];
    state.detectedItems = [];
    state.currentItemIndex = 0;
    
    // Reset multi-image UI
    elements.multiImageGrid.innerHTML = '';
    elements.multiImageContainer.classList.remove('active');
    elements.captureZone.classList.remove('hidden');
    elements.imageCountDisplay.style.display = 'none';
    
    // Hide progress
    elements.analyzeProgress.style.display = 'none';
    
    elements.analyzeBtn.disabled = true;
    elements.imageInput.value = '';
    elements.cameraInput.value = '';
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
    
    // Capture - Multi-image
    elements.captureZone.addEventListener('click', handleCaptureZoneClick);
    elements.cameraBtn.addEventListener('click', handleCameraClick);
    elements.uploadBtn.addEventListener('click', handleUploadClick);
    elements.addMoreImagesZone.addEventListener('click', handleAddMoreImagesClick);
    elements.imageInput.addEventListener('change', handleImageSelect);
    elements.cameraInput.addEventListener('change', handleCameraCapture);
    elements.clearAllImages.addEventListener('click', handleClearAllImages);
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
    
    // Back navigation
    elements.backToLocationBtn.addEventListener('click', handleBackToLocation);
    elements.backToCaptureBtn.addEventListener('click', handleBackToCapture);
    
    // Offline/Online detection
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    // Check initial offline state
    if (!navigator.onLine) {
        handleOffline();
    }
}

// ========================================
// Navigation Handlers
// ========================================

function handleBackToLocation() {
    // Confirm if images have been captured
    if (state.capturedImages.length > 0) {
        if (!confirm('Going back will keep your photos. Continue?')) {
            return;
        }
    }
    showSection('locationSection');
}

function handleBackToCapture() {
    // Confirm if items have been detected but not all confirmed
    const unconfirmedItems = state.detectedItems.filter(item => !item.confirmed);
    if (unconfirmedItems.length > 0) {
        if (!confirm('You have unreviewed items. Go back anyway?')) {
            return;
        }
    }
    showSection('captureSection');
}

// ========================================
// Offline Handling
// ========================================

function handleOnline() {
    elements.offlineBanner.style.display = 'none';
    showToast('Back online!', 'success');
}

function handleOffline() {
    elements.offlineBanner.style.display = 'flex';
}

// ========================================
// Version Display
// ========================================

async function fetchAndDisplayVersion() {
    try {
        const response = await fetch('/api/version');
        if (response.ok) {
            const data = await response.json();
            const versionDisplay = document.getElementById('versionDisplay');
            if (versionDisplay && data.version) {
                versionDisplay.textContent = `v${data.version}`;
            }
        }
    } catch (error) {
        // Silently ignore version fetch errors - not critical
        console.debug('Could not fetch version:', error);
    }
}

// ========================================
// Initialization
// ========================================

async function init() {
    initEventListeners();
    
    // Fetch and display version (non-blocking)
    fetchAndDisplayVersion();
    
    // Check for existing token
    if (loadToken()) {
        try {
            await loadLocations();
            showSection('locationSection');
        } catch (error) {
            // Token expired or invalid - apiRequest already handled 401
            // (cleared token, showed toast, switched to login)
            // Just make sure we're on login section
            if (error.message === 'SESSION_EXPIRED') {
                // Already handled by apiRequest
                return;
            }
            // For other errors, clear token and show login
            clearToken();
            showSection('loginSection');
        }
    } else {
        showSection('loginSection');
    }
}

// Start the app
document.addEventListener('DOMContentLoaded', init);

