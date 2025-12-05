const API_BASE = '';

// Check if already logged in
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('pharmacheck_token');
    if (token) {
        window.location.href = '/dashboard/';
    }
    
    // Load doctors list
    loadDoctors();
});

async function loadDoctors() {
    try {
        const response = await fetch(`${API_BASE}/doctors/all`);
        if (response.ok) {
            const doctors = await response.json();
            const select = document.getElementById('doctorSelect');
            
            doctors.forEach(doctor => {
                const option = document.createElement('option');
                option.value = doctor.user_id;
                option.textContent = `Dr. ${doctor.username}`;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading doctors:', error);
    }
}

function toggleDoctorSelect() {
    const role = document.querySelector('input[name="role"]:checked').value;
    const doctorGroup = document.getElementById('doctorSelectGroup');
    
    if (role === 'PATIENT') {
        doctorGroup.style.display = 'block';
    } else {
        doctorGroup.style.display = 'none';
    }
}

async function handleRegister(event) {
    event.preventDefault();
    
    const submitBtn = document.getElementById('submitBtn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');
    
    const username = document.getElementById('username').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const role = document.querySelector('input[name="role"]:checked').value;
    const selectedDoctor = document.getElementById('doctorSelect').value;
    
    // Reset messages
    errorMessage.classList.remove('show');
    successMessage.classList.remove('show');
    errorMessage.textContent = '';
    successMessage.textContent = '';
    
    // Validate passwords match
    if (password !== confirmPassword) {
        errorMessage.textContent = 'Passwords do not match.';
        errorMessage.classList.add('show');
        return;
    }
    
    // Validate password strength
    if (password.length < 8) {
        errorMessage.textContent = 'Password must be at least 8 characters long.';
        errorMessage.classList.add('show');
        return;
    }
    
    // Show loading state
    submitBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';
    
    try {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, email, password, role })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            // Store token and user info
            localStorage.setItem('pharmacheck_token', data.token);
            localStorage.setItem('pharmacheck_user', JSON.stringify(data.user));
            
            // If patient selected a doctor, request their oversight
            if (role === 'PATIENT' && selectedDoctor) {
                try {
                    await fetch(`${API_BASE}/patients/request_doctor`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${data.token}`
                        },
                        body: JSON.stringify({ doctor_id: parseInt(selectedDoctor) })
                    });
                } catch (err) {
                    console.error('Error requesting doctor:', err);
                }
            }
            
            // Show success message briefly
            successMessage.textContent = 'Account created successfully! Redirecting...';
            successMessage.classList.add('show');
            
            // Redirect after short delay
            setTimeout(() => {
                window.location.href = '/dashboard/';
            }, 1500);
        } else {
            // Show error message
            errorMessage.textContent = data.error || 'Registration failed. Please try again.';
            errorMessage.classList.add('show');
            
            // Reset button state
            submitBtn.disabled = false;
            btnText.style.display = 'inline';
            btnLoading.style.display = 'none';
        }
    } catch (error) {
        console.error('Registration error:', error);
        errorMessage.textContent = 'Unable to connect to server. Please try again later.';
        errorMessage.classList.add('show');
        
        // Reset button state
        submitBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

