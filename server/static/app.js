/**
 * Homebox Scanner - Mobile Web App
 * Main application logic
 */

// ========================================
// State Management
// ========================================

const state = {
    token: null,
    locations: [],
    labels: [],
    selectedLocationId: null,
    selectedLocationName: null,
    capturedImage: null,
    detectedItems: [],
    confirmedItems: [],
    currentItemIndex: 0,
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
    locationSelect: document.getElementById('locationSelect'),
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
    state.labels = [];
    state.selectedLocationId = null;
    state.selectedLocationName = null;
    state.capturedImage = null;
    state.detectedItems = [];
    state.confirmedItems = [];
    showSection('loginSection');
    showToast('Logged out successfully', 'info');
}

// ========================================
// Locations
// ========================================

async function loadLocations() {
    try {
        const locations = await apiRequest('/api/locations');
        state.locations = locations;
        
        elements.locationSelect.innerHTML = '<option value="">Select a location...</option>';
        
        locations.forEach(location => {
            const option = document.createElement('option');
            option.value = location.id;
            option.textContent = location.name;
            elements.locationSelect.appendChild(option);
        });
        
        // Also load labels for later use
        try {
            const labels = await apiRequest('/api/labels');
            state.labels = labels;
        } catch (e) {
            console.warn('Could not load labels:', e);
        }
    } catch (error) {
        showToast('Failed to load locations: ' + error.message, 'error');
    }
}

function handleLocationChange() {
    const locationId = elements.locationSelect.value;
    state.selectedLocationId = locationId;
    
    const selectedOption = elements.locationSelect.options[elements.locationSelect.selectedIndex];
    state.selectedLocationName = selectedOption ? selectedOption.textContent : '';
    
    elements.continueToCapture.disabled = !locationId;
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
        
        state.detectedItems = data.items;
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
            </form>
        `;
        
        elements.itemCarousel.appendChild(card);
    });
    
    updateItemNavigation();
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
    
    const nameInput = document.getElementById(`itemName${index}`);
    const quantityInput = document.getElementById(`itemQuantity${index}`);
    const descriptionInput = document.getElementById(`itemDescription${index}`);
    
    if (!nameInput.value.trim()) {
        showToast('Please enter an item name', 'warning');
        return;
    }
    
    const confirmedItem = {
        name: nameInput.value.trim(),
        quantity: parseInt(quantityInput.value) || 1,
        description: descriptionInput.value.trim() || null,
        location_id: state.selectedLocationId,
        label_ids: state.detectedItems[index].label_ids || null,
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
    elements.summaryLocation.textContent = state.selectedLocationName || 'Unknown';
    
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
        const response = await apiRequest('/api/items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: state.confirmedItems,
                location_id: state.selectedLocationId,
            }),
        });
        
        const createdCount = response.created?.length || 0;
        const errorCount = response.errors?.length || 0;
        
        if (errorCount > 0) {
            showToast(`Created ${createdCount} items, ${errorCount} failed`, 'warning');
        } else {
            showToast(`Successfully created ${createdCount} items!`, 'success');
        }
        
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
    
    // Location
    elements.locationSelect.addEventListener('change', handleLocationChange);
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

