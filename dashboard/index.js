const API_BASE = '';

let currentUser = null;
let authToken = null;
let searchHistory = [];
let patients = [];
let myDoctors = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    setupNavigation();
});

// ============== Authentication ==============

function checkAuth() {
    authToken = localStorage.getItem('pharmacheck_token');
    const userJson = localStorage.getItem('pharmacheck_user');
    
    if (!authToken || !userJson) {
        window.location.href = '/welcome.html';
        return;
    }
    
    try {
        currentUser = JSON.parse(userJson);
        initializeDashboard();
    } catch (e) {
        logout();
    }
}

function initializeDashboard() {
    // Update user info
    document.getElementById('welcomeName').textContent = currentUser.username;
    document.getElementById('sidebarUserName').textContent = currentUser.username;
    document.getElementById('sidebarUserRole').textContent = currentUser.role;
    
    // Show doctor-specific elements
    if (currentUser.role === 'DOCTOR') {
        document.querySelectorAll('.doctor-only').forEach(el => {
            el.style.display = '';
        });
        document.getElementById('userAvatar').textContent = '⚕️';
        loadPatients();
    }
    
    // Show patient-specific elements
    if (currentUser.role === 'PATIENT') {
        document.querySelectorAll('.patient-only').forEach(el => {
            el.style.display = '';
        });
        loadMyDoctors();
        setupDoctorSearch();
    }
    
    // Load data
    loadSearchHistory();
}

function logout() {
    localStorage.removeItem('pharmacheck_token');
    localStorage.removeItem('pharmacheck_user');
    window.location.href = '/welcome.html';
}

function getAuthHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
    };
}

// ============== Navigation ==============

function setupNavigation() {
    document.querySelectorAll('.nav-item[data-section]').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;
            showSection(section);
            
            // Update active state
            document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
        });
    });
}

function showSection(sectionId) {
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(`${sectionId}-section`).classList.add('active');
    
    // Refresh data when switching sections
    if (sectionId === 'history') {
        renderHistory();
    } else if (sectionId === 'patients') {
        renderPatients();
    } else if (sectionId === 'my-doctor') {
        renderMyDoctors();
    }
}

// ============== Search History ==============

async function loadSearchHistory() {
    try {
        const response = await fetch(`${API_BASE}/users/search_history?limit=100`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            searchHistory = await response.json();
            updateStats();
            renderRecentActivity();
            renderHistory();
        } else if (response.status === 401) {
            logout();
        }
    } catch (error) {
        console.error('Error loading search history:', error);
    }
}

function updateStats() {
    const total = searchHistory.length;
    const drugs = searchHistory.filter(h => h.search_type === 'DRUG').length;
    const interactions = searchHistory.filter(h => h.search_type === 'INTERACTION').length;
    
    document.getElementById('totalSearches').textContent = total;
    document.getElementById('drugSearches').textContent = drugs;
    document.getElementById('interactionSearches').textContent = interactions;
}

function renderRecentActivity() {
    const container = document.getElementById('recentActivityList');
    const recent = searchHistory.slice(0, 5);
    
    if (recent.length === 0) {
        container.innerHTML = '<p class="empty-state">No recent activity</p>';
        return;
    }
    
    container.innerHTML = recent.map(item => `
        <div class="activity-item">
            <div class="activity-info">
                <span class="activity-type">${getTypeIcon(item.search_type)}</span>
                <div>
                    <div class="activity-query">${escapeHtml(item.query)}</div>
                    <div class="activity-search-type">${item.search_type}</div>
                </div>
            </div>
            <span class="activity-time">${formatTime(item.created_at)}</span>
        </div>
    `).join('');
}

function renderHistory() {
    const container = document.getElementById('historyList');
    const filterInput = document.getElementById('historySearch');
    const filter = filterInput?.value?.toLowerCase() || '';
    
    const filtered = filter 
        ? searchHistory.filter(h => h.query.toLowerCase().includes(filter))
        : searchHistory;
    
    if (filtered.length === 0) {
        container.innerHTML = '<p class="empty-state">No search history found</p>';
        return;
    }
    
    container.innerHTML = filtered.map(item => `
        <div class="history-item clickable" onclick="restoreSearch(${item.search_id}, event)">
            <div class="activity-info">
                <span class="activity-type">${getTypeIcon(item.search_type)}</span>
                <div>
                    <div class="activity-query">${escapeHtml(item.query)}</div>
                    <div class="activity-search-type">${item.search_type} - ${formatTime(item.created_at)}</div>
                </div>
            </div>
            <button class="history-delete" onclick="deleteHistoryItem(${item.search_id}, event)">Delete</button>
        </div>
    `).join('');
}

// Filter history on input
document.getElementById('historySearch')?.addEventListener('input', renderHistory);

async function restoreSearch(searchId, event) {
    if (event) {
        event.stopPropagation();
    }
    
    try {
        const response = await fetch(`${API_BASE}/users/search_history/${searchId}`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.search_data) {
                // Store the search data and redirect to interactions page
                localStorage.setItem('interactionsData', JSON.stringify(data.search_data));
                window.location.href = '/interactions/';
            } else {
                alert('No search data available for this entry.');
            }
        } else {
            alert('Failed to restore search.');
        }
    } catch (error) {
        console.error('Error restoring search:', error);
        alert('Error restoring search.');
    }
}

async function deleteHistoryItem(searchId, event) {
    if (event) {
        event.stopPropagation();
    }
    
    try {
        const response = await fetch(`${API_BASE}/users/search_history/${searchId}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            searchHistory = searchHistory.filter(h => h.search_id !== searchId);
            updateStats();
            renderRecentActivity();
            renderHistory();
        }
    } catch (error) {
        console.error('Error deleting history item:', error);
    }
}

async function clearAllHistory() {
    if (!confirm('Are you sure you want to clear all search history?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/users/search_history`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            searchHistory = [];
            updateStats();
            renderRecentActivity();
            renderHistory();
        }
    } catch (error) {
        console.error('Error clearing history:', error);
    }
}

// ============== Patients (Doctor Only) ==============

async function loadPatients() {
    try {
        const response = await fetch(`${API_BASE}/doctors/patients`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            patients = await response.json();
            document.getElementById('patientCount').textContent = patients.length;
            renderPatients();
        }
    } catch (error) {
        console.error('Error loading patients:', error);
    }
}

function renderPatients() {
    const container = document.getElementById('patientsList');
    
    if (patients.length === 0) {
        container.innerHTML = '<p class="empty-state">No patients have requested your oversight yet. When patients select you as their doctor during registration, they will appear here.</p>';
        return;
    }
    
    container.innerHTML = patients.map(patient => `
        <div class="patient-card">
            <div class="patient-header">
                <div class="patient-info">
                    <span class="patient-avatar">👤</span>
                    <div>
                        <div class="patient-name">${escapeHtml(patient.username)}</div>
                        <div class="patient-email">${escapeHtml(patient.email)}</div>
                    </div>
                </div>
                <div class="patient-stats">
                    <span class="stat-badge">${patient.total_searches || 0} searches</span>
                    <button class="history-delete" onclick="removePatient(${patient.user_id})">Remove</button>
                </div>
            </div>
            <div class="patient-recent-searches">
                <h4>Recent Searches</h4>
                ${patient.recent_searches && patient.recent_searches.length > 0 
                    ? `<div class="mini-activity-list">
                        ${patient.recent_searches.map(search => `
                            <div class="mini-activity-item">
                                <span class="activity-type">${getTypeIcon(search.search_type)}</span>
                                <span class="activity-query">${escapeHtml(search.query)}</span>
                                <span class="activity-time">${formatTime(search.created_at)}</span>
                            </div>
                        `).join('')}
                       </div>`
                    : '<p class="empty-state-small">No searches yet</p>'
                }
            </div>
            <div class="patient-actions">
                <button class="btn-secondary" onclick="viewPatientHistory(${patient.user_id})">View Full History</button>
            </div>
        </div>
    `).join('');
}

async function removePatient(patientId) {
    if (!confirm('Are you sure you want to remove this patient?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/doctors/patients/${patientId}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            loadPatients();
        }
    } catch (error) {
        console.error('Error removing patient:', error);
    }
}

async function viewPatientHistory(patientId) {
    try {
        const response = await fetch(`${API_BASE}/doctors/patients/${patientId}/search_history?limit=50`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const history = await response.json();
            const patient = patients.find(p => p.user_id === patientId);
            showPatientHistoryModal(patient, history);
        }
    } catch (error) {
        console.error('Error loading patient history:', error);
    }
}

function showPatientHistoryModal(patient, history) {
    // Create modal dynamically
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 600px;">
            <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
            <h2>${escapeHtml(patient.username)}'s Search History</h2>
            <p style="margin-bottom: 20px;">Email: ${escapeHtml(patient.email)}</p>
            <div class="activity-list" style="max-height: 400px; overflow-y: auto;">
                ${history.length === 0 
                    ? '<p class="empty-state">No search history</p>'
                    : history.map(item => `
                        <div class="activity-item">
                            <div class="activity-info">
                                <span class="activity-type">${getTypeIcon(item.search_type)}</span>
                                <div>
                                    <div class="activity-query">${escapeHtml(item.query)}</div>
                                    <div class="activity-search-type">${item.search_type}</div>
                                </div>
                            </div>
                            <span class="activity-time">${formatTime(item.created_at)}</span>
                        </div>
                    `).join('')
                }
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Close on click outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// ============== Helpers ==============

function getTypeIcon(type) {
    switch (type) {
        case 'DRUG': return '💊';
        case 'CONDITION': return '🏥';
        case 'INTERACTION': return '⚠️';
        case 'FOOD_INTERACTION': return '🍎';
        case 'DISEASE_INTERACTION': return '🏥';
        default: return '🔍';
    }
}

function formatTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;
    
    // Less than 1 hour
    if (diff < 3600000) {
        const mins = Math.floor(diff / 60000);
        return mins <= 1 ? 'Just now' : `${mins} minutes ago`;
    }
    
    // Less than 24 hours
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    }
    
    // Less than 7 days
    if (diff < 604800000) {
        const days = Math.floor(diff / 86400000);
        return `${days} day${days > 1 ? 's' : ''} ago`;
    }
    
    // Otherwise show date
    return date.toLocaleDateString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============== My Doctors (Patient Only) ==============

async function loadMyDoctors() {
    try {
        const response = await fetch(`${API_BASE}/patients/doctors`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            myDoctors = await response.json();
            renderMyDoctors();
        }
    } catch (error) {
        console.error('Error loading my doctors:', error);
    }
}

function renderMyDoctors() {
    const container = document.getElementById('currentDoctorInfo');
    
    if (myDoctors.length === 0) {
        container.innerHTML = `
            <div class="no-doctor-card">
                <span class="no-doctor-icon">⚕️</span>
                <h3>No Doctor Selected</h3>
                <p>Search for a doctor below to request their oversight. They will be able to view your search history.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = myDoctors.map(doctor => `
        <div class="doctor-card">
            <div class="doctor-info">
                <span class="doctor-avatar">⚕️</span>
                <div>
                    <div class="doctor-name">Dr. ${escapeHtml(doctor.username)}</div>
                    <div class="doctor-email">${escapeHtml(doctor.email)}</div>
                </div>
            </div>
            <button class="history-delete" onclick="removeMyDoctor(${doctor.user_id})">Remove</button>
        </div>
    `).join('');
}

function setupDoctorSearch() {
    const searchInput = document.getElementById('doctorSearchInput');
    if (!searchInput) return;
    
    let debounceTimer;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchDoctors(e.target.value);
        }, 300);
    });
}

async function searchDoctors(query) {
    const resultsDiv = document.getElementById('doctorSearchResults');
    
    if (!query || query.length < 2) {
        resultsDiv.classList.remove('show');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/doctors/search?query=${encodeURIComponent(query)}`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const doctors = await response.json();
            
            if (doctors.length === 0) {
                resultsDiv.innerHTML = '<div class="autocomplete-item">No doctors found</div>';
            } else {
                resultsDiv.innerHTML = doctors.map(doctor => `
                    <div class="autocomplete-item" onclick="requestDoctor(${doctor.user_id}, '${escapeHtml(doctor.username)}')">
                        <span>⚕️</span>
                        <span>Dr. ${escapeHtml(doctor.username)}</span>
                    </div>
                `).join('');
            }
            
            resultsDiv.classList.add('show');
        }
    } catch (error) {
        console.error('Error searching doctors:', error);
    }
}

async function requestDoctor(doctorId, doctorUsername) {
    const errorEl = document.getElementById('requestDoctorError');
    const resultsDiv = document.getElementById('doctorSearchResults');
    const searchInput = document.getElementById('doctorSearchInput');
    
    try {
        const response = await fetch(`${API_BASE}/patients/request_doctor`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ doctor_id: doctorId })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            // Clear search
            searchInput.value = '';
            resultsDiv.classList.remove('show');
            errorEl.classList.remove('show');
            
            // Reload doctors list
            loadMyDoctors();
            
            alert(`Successfully requested oversight from Dr. ${doctorUsername}`);
        } else {
            errorEl.textContent = data.error || 'Failed to request doctor';
            errorEl.classList.add('show');
        }
    } catch (error) {
        errorEl.textContent = 'Failed to connect to server';
        errorEl.classList.add('show');
    }
}

async function removeMyDoctor(doctorId) {
    if (!confirm('Are you sure you want to remove this doctor? They will no longer be able to view your search history.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/patients/my_doctor`, {
            method: 'DELETE',
            headers: getAuthHeaders(),
            body: JSON.stringify({ doctor_id: doctorId })
        });
        
        if (response.ok) {
            loadMyDoctors();
        }
    } catch (error) {
        console.error('Error removing doctor:', error);
    }
}

// ============== Food/Lifestyle Interaction Checker ==============

let foodDebounceTimer;

document.addEventListener('DOMContentLoaded', () => {
    // Setup autocomplete for food drug input
    const foodInput = document.getElementById('foodDrugInput');
    if (foodInput) {
        foodInput.addEventListener('input', (e) => {
            clearTimeout(foodDebounceTimer);
            foodDebounceTimer = setTimeout(() => {
                fetchDrugAutocomplete(e.target.value, 'foodDrugAutocomplete');
            }, 300);
        });
    }
    
    // Setup autocomplete for disease drug input
    const diseaseInput = document.getElementById('diseaseDrugInput');
    if (diseaseInput) {
        diseaseInput.addEventListener('input', (e) => {
            clearTimeout(foodDebounceTimer);
            foodDebounceTimer = setTimeout(() => {
                fetchDrugAutocomplete(e.target.value, 'diseaseDrugAutocomplete');
            }, 300);
        });
    }
    
    // Close dropdowns on click outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.autocomplete-wrapper')) {
            document.querySelectorAll('.autocomplete-dropdown').forEach(d => d.classList.remove('show'));
        }
    });
});

async function fetchDrugAutocomplete(query, dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    if (!dropdown) return;
    
    if (query.length < 2) {
        dropdown.classList.remove('show');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/drugs/autocomplete?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (data.length === 0) {
            dropdown.classList.remove('show');
            return;
        }
        
        dropdown.innerHTML = data.map(item => `
            <div class="autocomplete-item" onclick="selectDrugAutocomplete('${escapeHtml(item.name)}', '${dropdownId}')">
                <div class="autocomplete-item-name">${escapeHtml(item.name)}</div>
            </div>
        `).join('');
        
        dropdown.classList.add('show');
    } catch (error) {
        console.error('Autocomplete error:', error);
        dropdown.classList.remove('show');
    }
}

function selectDrugAutocomplete(name, dropdownId) {
    const inputId = dropdownId === 'foodDrugAutocomplete' ? 'foodDrugInput' : 'diseaseDrugInput';
    document.getElementById(inputId).value = name;
    document.getElementById(dropdownId).classList.remove('show');
}

async function checkFoodInteractions() {
    const drug = document.getElementById('foodDrugInput').value.trim();
    const resultsDiv = document.getElementById('foodResults');
    const btnText = document.getElementById('foodBtnText');
    const btnLoading = document.getElementById('foodBtnLoading');
    
    if (!drug) {
        resultsDiv.innerHTML = '<div class="error">Please enter a drug name</div>';
        return;
    }
    
    // Show loading
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';
    resultsDiv.innerHTML = '<div class="loading">Loading food/lifestyle interactions...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/food_interactions?active_ingredient=${encodeURIComponent(drug)}`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const interactions = await response.json();
            renderFoodResults(interactions, drug);
        } else {
            resultsDiv.innerHTML = '<div class="error">Failed to load interactions. Please try again.</div>';
        }
    } catch (error) {
        console.error('Error:', error);
        resultsDiv.innerHTML = '<div class="error">Error loading interactions. Please check your connection.</div>';
    } finally {
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

function renderFoodResults(interactions, drug) {
    const resultsDiv = document.getElementById('foodResults');
    
    if (!interactions || interactions.length === 0) {
        resultsDiv.innerHTML = `<div class="empty-state">No food/lifestyle interactions found for ${escapeHtml(drug)}</div>`;
        return;
    }
    
    // Store interactions globally for translation
    window.foodInteractions = interactions;
    
    resultsDiv.innerHTML = `
        <h3 style="margin-bottom: 16px; color: #1e293b;">Found ${interactions.length} interaction(s) for ${escapeHtml(drug)}</h3>
        ${interactions.map((interaction, index) => `
            <div class="interaction-card severity-${interaction.severity || 'Unknown'}">
                <h3>
                    ${escapeHtml(interaction.interaction_name || 'Food/Lifestyle Interaction')}
                    <span class="severity-badge">${interaction.severity || 'Unknown'}</span>
                </h3>
                ${(interaction.hazard_level || interaction.plausibility) ? `
                    <div class="meta">
                        ${interaction.hazard_level ? `<span class="meta-item"><strong>Hazard:</strong> ${escapeHtml(interaction.hazard_level)}</span>` : ''}
                        ${interaction.plausibility ? `<span class="meta-item"><strong>Plausibility:</strong> ${escapeHtml(interaction.plausibility)}</span>` : ''}
                    </div>
                ` : ''}
                <div class="description" id="food-desc-${index}">${escapeHtml(interaction.ai_description || interaction.professional_description || 'No description available')}</div>
                ${!interaction.ai_description && interaction.professional_description ? `
                    <button class="translate-btn" onclick="translateFoodInteraction(${index}, event)">
                        ✨ Translate to Patient-Friendly
                    </button>
                ` : ''}
                ${interaction.ai_description ? `
                    <div class="ai-description">
                        <div class="ai-description-label">✨ AI Translated</div>
                    </div>
                ` : ''}
            </div>
        `).join('')}
    `;
}

// ============== Disease Interaction Checker ==============

async function checkDiseaseInteractions() {
    const drug = document.getElementById('diseaseDrugInput').value.trim();
    const resultsDiv = document.getElementById('diseaseResults');
    const btnText = document.getElementById('diseaseBtnText');
    const btnLoading = document.getElementById('diseaseBtnLoading');
    
    if (!drug) {
        resultsDiv.innerHTML = '<div class="error">Please enter a drug name</div>';
        return;
    }
    
    // Show loading
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';
    resultsDiv.innerHTML = '<div class="loading">Loading disease interactions...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/disease_interactions?active_ingredient=${encodeURIComponent(drug)}`, {
            headers: getAuthHeaders()
        });
        
        if (response.ok) {
            const interactions = await response.json();
            renderDiseaseResults(interactions, drug);
        } else {
            resultsDiv.innerHTML = '<div class="error">Failed to load interactions. Please try again.</div>';
        }
    } catch (error) {
        console.error('Error:', error);
        resultsDiv.innerHTML = '<div class="error">Error loading interactions. Please check your connection.</div>';
    } finally {
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

function renderDiseaseResults(interactions, drug) {
    const resultsDiv = document.getElementById('diseaseResults');
    
    // Store interactions globally for translation
    window.diseaseInteractions = interactions;
    
    if (!interactions || interactions.length === 0) {
        resultsDiv.innerHTML = `<div class="empty-state">No disease interactions found for ${escapeHtml(drug)}</div>`;
        return;
    }
    
    resultsDiv.innerHTML = `
        <h3 style="margin-bottom: 16px; color: #1e293b;">Found ${interactions.length} interaction(s) for ${escapeHtml(drug)}</h3>
        ${interactions.map((interaction, index) => `
            <div class="interaction-card severity-${interaction.severity || 'Unknown'}">
                <h3>
                    ${escapeHtml(interaction.disease_name || 'Disease Interaction')}
                    <span class="severity-badge">${interaction.severity || 'Unknown'}</span>
                </h3>
                ${(interaction.hazard_level || interaction.plausibility) ? `
                    <div class="meta">
                        ${interaction.hazard_level ? `<span class="meta-item"><strong>Hazard:</strong> ${escapeHtml(interaction.hazard_level)}</span>` : ''}
                        ${interaction.plausibility ? `<span class="meta-item"><strong>Plausibility:</strong> ${escapeHtml(interaction.plausibility)}</span>` : ''}
                    </div>
                ` : ''}
                ${interaction.applicable_conditions ? `
                    <div class="meta" style="margin-top: 8px;">
                        <span class="meta-item"><strong>Applicable Conditions:</strong> ${escapeHtml(interaction.applicable_conditions)}</span>
                    </div>
                ` : ''}
                <div class="description" id="disease-desc-${index}">${escapeHtml(interaction.ai_description || interaction.professional_description || 'No description available')}</div>
                ${!interaction.ai_description && interaction.professional_description ? `
                    <button class="translate-btn" onclick="translateDiseaseInteraction(${index}, event)">
                        ✨ Translate to Patient-Friendly
                    </button>
                ` : ''}
                ${interaction.ai_description ? `
                    <div class="ai-description">
                        <div class="ai-description-label">✨ AI Translated</div>
                    </div>
                ` : ''}
            </div>
        `).join('')}
    `;
}

async function translateFoodInteraction(index, event) {
    if (event) event.stopPropagation();
    
    if (!window.foodInteractions || !window.foodInteractions[index]) {
        return;
    }
    
    const interaction = window.foodInteractions[index];
    const button = event.target;
    
    button.disabled = true;
    button.innerHTML = '<span class="loading-dots">Translating<span>.</span><span>.</span><span>.</span></span>';
    
    try {
        const token = localStorage.getItem('pharmacheck_token');
        const response = await fetch(`${API_BASE}/translate_description`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                professional_description: interaction.professional_description
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            interaction.ai_description = data.consumer_description;
            document.getElementById(`food-desc-${index}`).textContent = data.consumer_description;
            button.outerHTML = '<div class="ai-description"><div class="ai-description-label">✨ AI Translated</div></div>';
        } else {
            button.textContent = 'Translation failed';
            setTimeout(() => {
                button.disabled = false;
                button.innerHTML = '✨ Translate to Patient-Friendly';
            }, 2000);
        }
    } catch (error) {
        console.error('Translation error:', error);
        button.textContent = 'Translation failed';
        setTimeout(() => {
            button.disabled = false;
            button.innerHTML = '✨ Translate to Patient-Friendly';
        }, 2000);
    }
}

async function translateDiseaseInteraction(index, event) {
    if (event) event.stopPropagation();
    
    if (!window.diseaseInteractions || !window.diseaseInteractions[index]) {
        return;
    }
    
    const interaction = window.diseaseInteractions[index];
    const button = event.target;
    
    button.disabled = true;
    button.innerHTML = '<span class="loading-dots">Translating<span>.</span><span>.</span><span>.</span></span>';
    
    try {
        const token = localStorage.getItem('pharmacheck_token');
        const response = await fetch(`${API_BASE}/translate_description`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                professional_description: interaction.professional_description
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            interaction.ai_description = data.consumer_description;
            document.getElementById(`disease-desc-${index}`).textContent = data.consumer_description;
            button.outerHTML = '<div class="ai-description"><div class="ai-description-label">✨ AI Translated</div></div>';
        } else {
            button.textContent = 'Translation failed';
            setTimeout(() => {
                button.disabled = false;
                button.innerHTML = '✨ Translate to Patient-Friendly';
            }, 2000);
        }
    } catch (error) {
        console.error('Translation error:', error);
        button.textContent = 'Translation failed';
        setTimeout(() => {
            button.disabled = false;
            button.innerHTML = '✨ Translate to Patient-Friendly';
        }, 2000);
    }
}

