const API_BASE = '';

let drugDrugInteractions = [];
let foodInteractions = [];
let diseaseInteractions = [];
let prescribedDrug = '';
let currentMedications = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check if logged in
    const token = localStorage.getItem('pharmacheck_token');
    if (!token) {
        window.location.href = '/welcome.html';
        return;
    }
    
    loadInteractionsData();
    setupTabs();
});

function loadInteractionsData() {
    const data = localStorage.getItem('interactionsData');
    
    if (!data) {
        showError('No interaction data found. Please go back and search again.');
        return;
    }
    
    try {
        const parsed = JSON.parse(data);
        
        // Data structure from /check_drug_interactions API
        drugDrugInteractions = parsed.interactions || [];
        foodInteractions = parsed.food_interactions || [];
        diseaseInteractions = parsed.disease_interactions || [];
        
        // Support both old format (prescribed_drug + current_medications) and new format (drugs)
        if (parsed.drugs && parsed.drugs.length > 0) {
            prescribedDrug = parsed.drugs.join(', ');
            currentMedications = parsed.drugs;
        } else {
            prescribedDrug = parsed.prescribed_drug || 'the selected medication';
            currentMedications = parsed.current_medications || [];
        }
        
        // Update page info
        if (currentMedications.length > 1) {
            document.getElementById('drugInfo').textContent = 
                `Interactions between: ${currentMedications.join(', ')}`;
        } else if (currentMedications.length === 1) {
            document.getElementById('drugInfo').textContent = 
                `Interactions for: ${currentMedications[0]}`;
        } else {
            document.getElementById('drugInfo').textContent = 
                `Interactions for: ${prescribedDrug}`;
        }
        
        // Render all sections
        renderDrugDrugInteractions();
        renderFoodInteractions();
        renderDiseaseInteractions();
        updateCounts();
        
    } catch (e) {
        console.error('Error parsing interactions data:', e);
        showError('Error loading interaction data.');
    }
}

function updateCounts() {
    document.getElementById('drugDrugCount').textContent = drugDrugInteractions.length;
    document.getElementById('foodCount').textContent = foodInteractions.length;
    document.getElementById('diseaseCount').textContent = diseaseInteractions.length;
}

function setupTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            
            // Update active tab
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Update active content
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById(`${tabId}-content`).classList.add('active');
        });
    });
}

function renderDrugDrugInteractions() {
    const container = document.getElementById('drugDrugList');
    
    if (drugDrugInteractions.length === 0) {
        const drugsList = currentMedications.length > 0 ? currentMedications.join(' and ') : prescribedDrug;
        container.innerHTML = `
            <div class="empty-state">
                <p>✅ No drug-drug interactions found for ${escapeHtml(drugsList)}.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = drugDrugInteractions.map((interaction, index) => 
        createInteractionCard(interaction, 'drug', index)
    ).join('');
    
    setupCardListeners();
}

function renderFoodInteractions() {
    const container = document.getElementById('foodList');
    
    if (foodInteractions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No food/lifestyle interactions found for ${escapeHtml(prescribedDrug)}.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = foodInteractions.map((interaction, index) => 
        createFoodInteractionCard(interaction, index)
    ).join('');
    
    setupCardListeners();
}

function renderDiseaseInteractions() {
    const container = document.getElementById('diseaseList');
    
    if (diseaseInteractions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No disease/health condition interactions found for ${escapeHtml(prescribedDrug)}.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = diseaseInteractions.map((interaction, index) => 
        createDiseaseInteractionCard(interaction, index)
    ).join('');
    
    setupCardListeners();
}

function createInteractionCard(interaction, type, index) {
    const severity = interaction.severity || 'Unknown';
    const name = interaction.drug || interaction.interaction || interaction.name || 'Unknown Interaction';
    const professionalDesc = interaction.professional_description || 'No description available';
    const aiDesc = interaction.ai_description;
    
    const descriptionToShow = aiDesc || professionalDesc;
    
    return `
        <div class="interaction-card severity-${severity} expanded" data-index="${index}" data-type="${type}">
            <div class="interaction-header">
                <div class="interaction-title">
                    <span class="interaction-name">${escapeHtml(name)}</span>
                    <span class="severity-badge ${severity}">${severity}</span>
                </div>
                <span class="expand-icon">▼</span>
            </div>
            <div class="interaction-details">
                <div class="detail-section">
                    <div class="detail-label">Description</div>
                    <div class="detail-value">${escapeHtml(descriptionToShow)}</div>
                    ${!aiDesc && professionalDesc ? `
                        <button class="translate-btn" onclick="translateDescription(${index}, 'drug', event)">
                            ✨ Translate to Patient-Friendly
                        </button>
                    ` : ''}
                    ${aiDesc ? `
                        <div class="ai-description">
                            <div class="ai-description-label">✨ AI Translated</div>
                        </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

function createFoodInteractionCard(interaction, index) {
    const severity = interaction.severity || 'Unknown';
    const name = interaction.interaction_name || 'Food/Lifestyle Interaction';
    const hazard = interaction.hazard_level || '';
    const plausibility = interaction.plausibility || '';
    const professionalDesc = interaction.professional_description || 'No description available';
    const aiDesc = interaction.ai_description;
    
    const descriptionToShow = aiDesc || professionalDesc;
    
    return `
        <div class="interaction-card severity-${severity} expanded" data-index="${index}" data-type="food">
            <div class="interaction-header">
                <div class="interaction-title">
                    <span class="interaction-name">${escapeHtml(name)}</span>
                    <span class="severity-badge ${severity}">${severity}</span>
                </div>
                <span class="expand-icon">▼</span>
            </div>
            <div class="interaction-details">
                ${(hazard || plausibility) ? `
                    <div class="detail-section">
                        <div class="detail-meta">
                            ${hazard ? `<span class="meta-item"><strong>Hazard:</strong> ${escapeHtml(hazard)}</span>` : ''}
                            ${plausibility ? `<span class="meta-item"><strong>Plausibility:</strong> ${escapeHtml(plausibility)}</span>` : ''}
                        </div>
                    </div>
                ` : ''}
                <div class="detail-section">
                    <div class="detail-label">Description</div>
                    <div class="detail-value">${escapeHtml(descriptionToShow)}</div>
                    ${!aiDesc && professionalDesc ? `
                        <button class="translate-btn" onclick="translateFoodDescription(${index}, event)">
                            ✨ Translate to Patient-Friendly
                        </button>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

function createDiseaseInteractionCard(interaction, index) {
    const severity = interaction.severity || 'Unknown';
    const name = interaction.disease_name || 'Disease Interaction';
    const hazard = interaction.hazard_level || '';
    const plausibility = interaction.plausibility || '';
    const conditions = interaction.applicable_conditions || '';
    const professionalDesc = interaction.professional_description || 'No description available';
    const aiDesc = interaction.ai_description;
    
    const descriptionToShow = aiDesc || professionalDesc;
    
    return `
        <div class="interaction-card severity-${severity} expanded" data-index="${index}" data-type="disease">
            <div class="interaction-header">
                <div class="interaction-title">
                    <span class="interaction-name">${escapeHtml(name)}</span>
                    <span class="severity-badge ${severity}">${severity}</span>
                </div>
                <span class="expand-icon">▼</span>
            </div>
            <div class="interaction-details">
                <div class="detail-section">
                    <div class="detail-meta">
                        ${hazard ? `<span class="meta-item"><strong>Hazard:</strong> ${escapeHtml(hazard)}</span>` : ''}
                        ${plausibility ? `<span class="meta-item"><strong>Plausibility:</strong> ${escapeHtml(plausibility)}</span>` : ''}
                    </div>
                </div>
                ${conditions ? `
                    <div class="detail-section">
                        <div class="detail-label">Applicable Conditions</div>
                        <div class="detail-value">${escapeHtml(conditions)}</div>
                    </div>
                ` : ''}
                <div class="detail-section">
                    <div class="detail-label">Description</div>
                    <div class="detail-value">${escapeHtml(descriptionToShow)}</div>
                    ${!aiDesc && professionalDesc ? `
                        <button class="translate-btn" onclick="translateDiseaseDescription(${index}, event)">
                            ✨ Translate to Patient-Friendly
                        </button>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

function setupCardListeners() {
    document.querySelectorAll('.interaction-header').forEach(header => {
        header.addEventListener('click', (e) => {
            // Don't toggle if clicking on translate button
            if (e.target.classList.contains('translate-btn')) return;
            
            const card = header.closest('.interaction-card');
            card.classList.toggle('expanded');
        });
    });
}

async function translateDescription(index, type, event) {
    if (event) event.stopPropagation();
    
    const interaction = drugDrugInteractions[index];
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
                professional_description: interaction.professional_description,
                interaction_id: interaction.interaction_id
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            interaction.ai_description = data.consumer_description;
            interaction.patient_description = data.consumer_description;
            renderDrugDrugInteractions();
            // Re-expand the card after rendering
            const cards = document.querySelectorAll('.interaction-card[data-type="drug"]');
            if (cards[index]) {
                cards[index].classList.add('expanded');
            }
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

async function translateFoodDescription(index, event) {
    if (event) event.stopPropagation();
    
    const interaction = foodInteractions[index];
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
            renderFoodInteractions();
            // Re-expand the card after rendering
            const cards = document.querySelectorAll('.interaction-card[data-type="food"]');
            if (cards[index]) {
                cards[index].classList.add('expanded');
            }
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

async function translateDiseaseDescription(index, event) {
    if (event) event.stopPropagation();
    
    const interaction = diseaseInteractions[index];
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
            renderDiseaseInteractions();
            // Re-expand the card after rendering
            const cards = document.querySelectorAll('.interaction-card[data-type="disease"]');
            if (cards[index]) {
                cards[index].classList.add('expanded');
            }
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

function showError(message) {
    document.querySelector('.main-content').innerHTML = `
        <div class="empty-state">
            <p>${message}</p>
            <a href="/index.html" style="color: #1e40af; margin-top: 16px; display: inline-block;">Go back to search</a>
        </div>
    `;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
