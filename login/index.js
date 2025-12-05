const API_BASE = '';

// Check if already logged in
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('pharmacheck_token');
    if (token) {
        // Verify token is still valid
        verifyToken(token);
    }
});

async function verifyToken(token) {
    try {
        const response = await fetch(`${API_BASE}/auth/me`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            // Token is valid, redirect to dashboard
            window.location.href = '/dashboard/';
        }
    } catch (error) {
        // Token invalid, stay on login page
        localStorage.removeItem('pharmacheck_token');
        localStorage.removeItem('pharmacheck_user');
    }
}

async function handleLogin(event) {
    event.preventDefault();
    
    const submitBtn = document.getElementById('submitBtn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');
    const errorMessage = document.getElementById('errorMessage');
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    
    // Reset error state
    errorMessage.classList.remove('show');
    errorMessage.textContent = '';
    
    // Show loading state
    submitBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';
    
    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            // Store token and user info
            localStorage.setItem('pharmacheck_token', data.token);
            localStorage.setItem('pharmacheck_user', JSON.stringify(data.user));
            
            // Redirect to dashboard
            window.location.href = '/dashboard/';
        } else {
            // Show error message
            errorMessage.textContent = data.error || 'Login failed. Please try again.';
            errorMessage.classList.add('show');
        }
    } catch (error) {
        console.error('Login error:', error);
        errorMessage.textContent = 'Unable to connect to server. Please try again later.';
        errorMessage.classList.add('show');
    } finally {
        // Reset button state
        submitBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

