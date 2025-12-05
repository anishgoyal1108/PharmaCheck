const API_BASE = '';

let currentInteraction = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadInteractionDetails();
});

function loadInteractionDetails() {
    const data = localStorage.getItem('selectedInteraction');
    
    if (!data) {
        showError('No interaction selected. Please go back and select an interaction.');
        return;
    }
    
    try {
        currentInteraction = JSON.parse(data);
        renderDetails();
    } catch (e) {
        console.error('Error parsing interaction data:', e);
        showError('Error loading interaction details.');
    }
}

function renderDetails() {
    const severity = currentInteraction.severity || 'Unknown';
    const name = currentInteraction.drug || currentInteraction.interaction_name || 
                 currentInteraction.disease_name || currentInteraction.name || 'Interaction';
    
    // Update title
    document.getElementById('interactionTitle').textContent = name;
    
    // Update severity badge
    const severityIndicator = document.getElementById('severityIndicator');
    severityIndicator.innerHTML = `<span class="severity-badge ${severity}">${severity} Severity</span>`;
    
    // Build details
    const detailsCard = document.getElementById('detailsCard');
    let detailsHTML = '';
    
    // Hazard and Plausibility (for food/disease interactions)
    if (currentInteraction.hazard_level || currentInteraction.plausibility) {
        detailsHTML += `
            <div class="detail-section">
                <div class="detail-label">Risk Assessment</div>
                <div class="detail-value">
                    ${currentInteraction.hazard_level ? `Hazard: ${escapeHtml(currentInteraction.hazard_level)}<br>` : ''}
                    ${currentInteraction.plausibility ? `Plausibility: ${escapeHtml(currentInteraction.plausibility)}` : ''}
                </div>
            </div>
        `;
    }
    
    // Applicable conditions (for disease interactions)
    if (currentInteraction.applicable_conditions) {
        detailsHTML += `
            <div class="detail-section">
                <div class="detail-label">Applicable Conditions</div>
                <div class="detail-value">${escapeHtml(currentInteraction.applicable_conditions)}</div>
            </div>
        `;
    }
    
    // Professional description
    if (currentInteraction.professional_description) {
        detailsHTML += `
            <div class="detail-section">
                <div class="detail-label">Professional Description</div>
                <div class="detail-value">${escapeHtml(currentInteraction.professional_description)}</div>
            </div>
        `;
    }
    
    // Patient description
    if (currentInteraction.patient_description && 
        currentInteraction.patient_description !== currentInteraction.professional_description) {
        detailsHTML += `
            <div class="detail-section">
                <div class="detail-label">Patient Description</div>
                <div class="detail-value">${escapeHtml(currentInteraction.patient_description)}</div>
            </div>
        `;
    }
    
    detailsCard.innerHTML = detailsHTML || '<p>No additional details available.</p>';
    
    // Show AI section if we have an AI description
    if (currentInteraction.ai_description) {
        showAIDescription(currentInteraction.ai_description);
    }
}

async function requestTranslation() {
    if (!currentInteraction || !currentInteraction.professional_description) {
        return;
    }
    
    const button = document.getElementById('translateBtn');
    button.disabled = true;
    button.textContent = 'Translating...';
    
    try {
        const response = await fetch(`${API_BASE}/translate_description`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                professional_description: currentInteraction.professional_description,
                interaction_id: currentInteraction.interaction_id
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            currentInteraction.ai_description = data.consumer_description;
            
            // Update localStorage
            localStorage.setItem('selectedInteraction', JSON.stringify(currentInteraction));
            
            showAIDescription(data.consumer_description);
            button.style.display = 'none';
        } else {
            const error = await response.json();
            alert(error.error || 'Translation failed. Please try again.');
            button.disabled = false;
            button.textContent = '✨ Generate Patient-Friendly Version';
        }
    } catch (error) {
        console.error('Translation error:', error);
        alert('Unable to connect to translation service. Please try again later.');
        button.disabled = false;
        button.textContent = '✨ Generate Patient-Friendly Version';
    }
}

function showAIDescription(description) {
    const aiSection = document.getElementById('aiSection');
    const aiContent = document.getElementById('aiContent');
    const translateBtn = document.getElementById('translateBtn');
    
    aiContent.textContent = description;
    aiSection.style.display = 'block';
    translateBtn.style.display = 'none';
}

function showError(message) {
    document.querySelector('.main-content').innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <p style="color: #64748b; margin-bottom: 16px;">${message}</p>
            <a href="../interactions/" class="btn-secondary">Go to Interactions</a>
        </div>
    `;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

