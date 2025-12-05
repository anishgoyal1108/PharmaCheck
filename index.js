const API_BASE = '';

// Auth state
let currentUser = null;
let authToken = null;

// Selected medications (max 5)
let selectedMedications = [];
const MAX_MEDICATIONS = 5;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkAuthState();
});

// ============== Authentication ==============

function checkAuthState() {
    authToken = localStorage.getItem('pharmacheck_token');
    const userJson = localStorage.getItem('pharmacheck_user');
    
    if (!authToken || !userJson) {
        // Not logged in - redirect to welcome page
        window.location.href = '/welcome.html';
        return;
    }
    
    try {
        currentUser = JSON.parse(userJson);
        showUserInfo();
        setupAutocomplete();
    } catch (e) {
        logout();
    }
}

function showUserInfo() {
    document.getElementById('userNameText').textContent = currentUser.username;
    const badge = document.getElementById('userRoleBadge');
    badge.textContent = currentUser.role;
    if (currentUser.role === 'DOCTOR') {
        badge.classList.add('doctor');
    }
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

// ============== Multi-Selector for Medications ==============

function addMedication(name) {
    if (selectedMedications.length >= MAX_MEDICATIONS) {
        showError('Maximum 5 medications allowed');
        return;
    }
    
    // Check if already added
    if (selectedMedications.find(m => m.toLowerCase() === name.toLowerCase())) {
        showError(`${name} is already added`);
        return;
    }
    
    selectedMedications.push(name);
    renderSelectedMedications();
    document.getElementById('medicationSearchInput').value = '';
    document.getElementById('medicationAutocomplete').classList.remove('show');
}

function removeMedication(name) {
    selectedMedications = selectedMedications.filter(m => m !== name);
    renderSelectedMedications();
}

function renderSelectedMedications() {
    const container = document.getElementById('selectedMedications');
    container.innerHTML = selectedMedications.map(med => `
        <span class="medication-tag">
            ${escapeHtml(med)}
            <button class="remove-btn" onclick="removeMedication('${escapeHtml(med)}')" type="button">&times;</button>
        </span>
    `).join('');
    
    document.getElementById('medCount').textContent = selectedMedications.length;
    
    // Disable input if max reached
    const input = document.getElementById('medicationSearchInput');
    if (selectedMedications.length >= MAX_MEDICATIONS) {
        input.disabled = true;
        input.placeholder = 'Maximum medications reached';
    } else {
        input.disabled = false;
        input.placeholder = 'Search and add medications...';
    }
}

// ============== Autocomplete ==============

function setupAutocomplete() {
    const drugInput = document.getElementById('drugInput');
    const conditionInput = document.getElementById('conditionInput');
    const medicationInput = document.getElementById('medicationSearchInput');
  
    const drugDropdown = document.getElementById('drugAutocomplete');
    const conditionDropdown = document.getElementById('conditionAutocomplete');
    const medicationDropdown = document.getElementById('medicationAutocomplete');
    
    let debounceTimer;
    
    // Drug autocomplete
    drugInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetchAutocomplete(e.target.value, 'drugs', drugDropdown, false);
        }, 300);
    });
    
    // Condition autocomplete
    conditionInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetchAutocomplete(e.target.value, 'conditions', conditionDropdown, false);
        }, 300);
    });
    
    // Medication multi-selector autocomplete
    medicationInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetchAutocomplete(e.target.value, 'drugs', medicationDropdown, true);
        }, 300);
    });

    // Close dropdowns on click outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.autocomplete-wrapper')) {
            drugDropdown.classList.remove('show');
            conditionDropdown.classList.remove('show');
            medicationDropdown.classList.remove('show');
        }
    });
    
    // Setup keyboard navigation for each input
    setupKeyboardNav(drugInput, drugDropdown, 'drugs');
    setupKeyboardNav(conditionInput, conditionDropdown, 'conditions');
    setupKeyboardNav(medicationInput, medicationDropdown, 'medications');
    }

function setupKeyboardNav(input, dropdown, type) {
    input.addEventListener('keydown', (e) => {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        const selected = dropdown.querySelector('.autocomplete-item.selected');
        let selectedIndex = Array.from(items).indexOf(selected);
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (selectedIndex < items.length - 1) {
                if (selected) selected.classList.remove('selected');
                items[selectedIndex + 1].classList.add('selected');
                items[selectedIndex + 1].scrollIntoView({ block: 'nearest' });
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (selectedIndex > 0) {
                if (selected) selected.classList.remove('selected');
                items[selectedIndex - 1].classList.add('selected');
                items[selectedIndex - 1].scrollIntoView({ block: 'nearest' });
            }
        } else if (e.key === 'Enter') {
            if (selected) {
                e.preventDefault();
                const name = selected.querySelector('.autocomplete-item-name').textContent;
                if (type === 'medications') {
                    addMedication(name);
                } else {
                    input.value = name;
                }
                dropdown.classList.remove('show');
            }
        } else if (e.key === 'Escape') {
            dropdown.classList.remove('show');
        }
    });
}

async function fetchAutocomplete(query, type, dropdown, isMultiSelect) {
    if (query.length < 2) {
        dropdown.classList.remove('show');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/${type}/autocomplete?q=${encodeURIComponent(query)}`);
    const data = await response.json();

        if (data.length === 0) {
            dropdown.classList.remove('show');
            return;
        }
        
        // Filter out already selected medications for multi-select
        let filteredData = data;
        if (isMultiSelect) {
            filteredData = data.filter(item => 
                !selectedMedications.find(m => m.toLowerCase() === item.name.toLowerCase())
            );
        }
        
        if (filteredData.length === 0) {
            dropdown.classList.remove('show');
            return;
        }
        
        dropdown.innerHTML = filteredData.map(item => `
            <div class="autocomplete-item" onclick="selectAutocomplete(this, '${type}', ${isMultiSelect})">
                <div class="autocomplete-item-name">${escapeHtml(item.name)}</div>
                ${item.generic_name ? `<div class="autocomplete-item-generic">${escapeHtml(item.generic_name)}</div>` : ''}
            </div>
        `).join('');
        
        dropdown.classList.add('show');
    } catch (error) {
        console.error('Autocomplete error:', error);
        dropdown.classList.remove('show');
    }
}

function selectAutocomplete(element, type, isMultiSelect) {
    const name = element.querySelector('.autocomplete-item-name').textContent;
    
    if (isMultiSelect || type === 'medications') {
        addMedication(name);
    } else {
        const inputId = type === 'drugs' ? 'drugInput' : 'conditionInput';
        document.getElementById(inputId).value = name;
    }

    element.closest('.autocomplete-dropdown').classList.remove('show');
}

// ============== Drug Interaction Check ==============

async function checkDrugInteraction() {
    const drugInput = document.getElementById("drugInput").value.trim();
    const conditionInput = document.getElementById("conditionInput").value.trim();
    const resultsContainer = document.getElementById("results");
    const checkBtn = document.getElementById("checkBtn");
    const btnText = checkBtn.querySelector('.btn-text');
    const btnLoading = checkBtn.querySelector('.btn-loading');

    // Validation
    if (!drugInput) {
        showError('Please enter the drug being prescribed');
        return;
    }

    if (!conditionInput) {
        showError('Please enter the condition being treated');
        return;
    }
    
    if (selectedMedications.length === 0) {
        showError('Please add at least one current medication');
        return; 
    }

    // Show loading state
    checkBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';
    resultsContainer.innerHTML = '<p style="text-align: center; color: #64748b;">Analyzing interactions...</p>';
    
    try {
        // Validate the prescribed drug
        const drugValidation = await fetch(`${API_BASE}/validate_drugs`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ drugs: [drugInput] })
        });
        const drugData = await drugValidation.json();
        
        if (drugData.not_found_drugs && drugData.not_found_drugs.length > 0) {
            showError(`Drug "${drugInput}" was not found. Please check the spelling or try a different name.`);
            resetButton();
            resultsContainer.innerHTML = '';
        return; 
    }

        // Check the condition exists
        const conditionResponse = await fetch(`${API_BASE}/search_conditions?input=${encodeURIComponent(conditionInput)}`, {
            headers: getAuthHeaders()
        });
        const conditionData = await conditionResponse.json();
        
        if (!conditionData || !conditionData[0]) {
            showError(`Condition "${conditionInput}" was not found. Please check the spelling.`);
            resetButton();
            resultsContainer.innerHTML = '';
        return;
    }

        // Validate current medications
        const medsValidation = await fetch(`${API_BASE}/validate_drugs`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ drugs: selectedMedications })
        });
        const medsData = await medsValidation.json();
        
        if (medsData.not_found_drugs && medsData.not_found_drugs.length > 0) {
            showError(`The following medications were not found: ${medsData.not_found_drugs.join(', ')}`);
            resetButton();
            resultsContainer.innerHTML = '';
            return;
        }

        // All validated - now check interactions
        const response = await fetch(`${API_BASE}/check_drug_interactions`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                drugs: selectedMedications,
                prescribed_drug: drugInput
            })
        });

        const data = await response.json();

        if (response.status === 401) {
            logout();
            return;
        }

        // Store data and redirect to interactions page
        localStorage.setItem('interactionsData', JSON.stringify(data));
        window.location.href = "/interactions/";
        
    } catch (error) {
        console.error('Error:', error);
        showError('Unable to connect to the server. Please try again.');
        resultsContainer.innerHTML = '';
    } finally {
        resetButton();
    }
    
    function resetButton() {
        checkBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

// ============== Modal Helpers ==============

function showError(message) {
    const modal = document.getElementById("errorModal");
    modal.style.display = "block";
    document.getElementById("errorMessage").innerText = message;
}

function closeModal() {
    document.getElementById("errorModal").style.display = "none";
}

window.onclick = function(event) {
    const modal = document.getElementById("errorModal");
    if (event.target == modal) {
      modal.style.display = "none";
    }
};

// ============== Helpers ==============

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
