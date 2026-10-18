// Check if already logged in
if (sessionStorage.getItem('adminLoggedIn') === 'true') {
    window.location.href = 'admin.html';
}

// Handle login form submission
function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const remember = document.getElementById('remember').checked;
    
    // Demo credentials (in production, this should be server-side)
    const validCredentials = {
        'admin': 'admin123',
        'superadmin': 'super123'
    };
    
    // Validate credentials
    if (validCredentials[username] && validCredentials[username] === password) {
        // Store login state
        sessionStorage.setItem('adminLoggedIn', 'true');
        sessionStorage.setItem('adminUsername', username);
        
        if (remember) {
            localStorage.setItem('adminRemember', 'true');
            localStorage.setItem('adminUsername', username);
        }
        
        // Show success message
        showMessage('Login successful! Redirecting...', 'success');
        
        // Redirect to admin dashboard
        setTimeout(() => {
            window.location.href = 'admin.html';
        }, 1000);
    } else {
        // Show error message
        showMessage('Invalid username or password!', 'error');
    }
}

// Show message function
function showMessage(message, type) {
    // Remove existing message if any
    const existingMsg = document.querySelector('.message');
    if (existingMsg) {
        existingMsg.remove();
    }
    
    // Create message element
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${type}`;
    msgDiv.textContent = message;
    msgDiv.style.cssText = `
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-size: 14px;
        text-align: center;
        ${type === 'error' ? 'background: #fee2e2; color: #991b1b;' : 'background: #d1fae5; color: #065f46;'}
    `;
    
    // Insert before form
    const form = document.getElementById('loginForm');
    form.parentNode.insertBefore(msgDiv, form);
    
    // Remove after 3 seconds
    setTimeout(() => {
        msgDiv.remove();
    }, 3000);
}

// Check remember me on page load
window.addEventListener('DOMContentLoaded', function() {
    if (localStorage.getItem('adminRemember') === 'true') {
        const username = localStorage.getItem('adminUsername');
        if (username) {
            document.getElementById('username').value = username;
            document.getElementById('remember').checked = true;
        }
    }
});
