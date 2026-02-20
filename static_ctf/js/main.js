// Countdown functionality
function startCountdown(targetTime, elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;

    function updateCountdown() {
        const now = new Date().getTime();
        const diff = targetTime - now;

        if (diff <= 0) {
            element.innerHTML = `
                <div class="text-center"><div class="w-16 h-16 md:w-20 md:h-20 bg-card border border-primary/30 rounded-lg flex items-center justify-center mb-2"><span class="font-display text-2xl md:text-3xl text-primary">00</span></div><span class="font-tech text-xs uppercase tracking-wider text-muted-foreground">Days</span></div>
                <div class="text-center"><div class="w-16 h-16 md:w-20 md:h-20 bg-card border border-primary/30 rounded-lg flex items-center justify-center mb-2"><span class="font-display text-2xl md:text-3xl text-primary">00</span></div><span class="font-tech text-xs uppercase tracking-wider text-muted-foreground">Hours</span></div>
                <div class="text-center"><div class="w-16 h-16 md:w-20 md:h-20 bg-card border border-primary/30 rounded-lg flex items-center justify-center mb-2"><span class="font-display text-2xl md:text-3xl text-primary">00</span></div><span class="font-tech text-xs uppercase tracking-wider text-muted-foreground">Minutes</span></div>
                <div class="text-center"><div class="w-16 h-16 md:w-20 md:h-20 bg-card border border-primary/30 rounded-lg flex items-center justify-center mb-2"><span class="font-display text-2xl md:text-3xl text-primary">00</span></div><span class="font-tech text-xs uppercase tracking-wider text-muted-foreground">Seconds</span></div>
            `;
            return;
        }

        const days = String(Math.floor(diff / (1000 * 60 * 60 * 24))).padStart(2, "0");
        const hours = String(Math.floor((diff / (1000 * 60 * 60)) % 24)).padStart(2, "0");
        const minutes = String(Math.floor((diff / (1000 * 60)) % 60)).padStart(2, "0");
        const seconds = String(Math.floor((diff / 1000) % 60)).padStart(2, "0");

        element.innerHTML = `
            <div class="text-center">
                <div class="w-16 h-16 md:w-20 md:h-20 bg-card border border-primary/30 rounded-lg flex items-center justify-center mb-2 animate-pulse-glow">
                    <span class="font-display text-2xl md:text-3xl text-primary">${days}</span>
                </div>
                <span class="font-tech text-xs uppercase tracking-wider text-muted-foreground">Days</span>
            </div>
            <div class="text-center">
                <div class="w-16 h-16 md:w-20 md:h-20 bg-card border border-primary/30 rounded-lg flex items-center justify-center mb-2 animate-pulse-glow">
                    <span class="font-display text-2xl md:text-3xl text-primary">${hours}</span>
                </div>
                <span class="font-tech text-xs uppercase tracking-wider text-muted-foreground">Hours</span>
            </div>
            <div class="text-center">
                <div class="w-16 h-16 md:w-20 md:h-20 bg-card border border-primary/30 rounded-lg flex items-center justify-center mb-2 animate-pulse-glow">
                    <span class="font-display text-2xl md:text-3xl text-primary">${minutes}</span>
                </div>
                <span class="font-tech text-xs uppercase tracking-wider text-muted-foreground">Minutes</span>
            </div>
            <div class="text-center">
                <div class="w-16 h-16 md:w-20 md:h-20 bg-card border border-primary/30 rounded-lg flex items-center justify-center mb-2 animate-pulse-glow">
                    <span class="font-display text-2xl md:text-3xl text-primary">${seconds}</span>
                </div>
                <span class="font-tech text-xs uppercase tracking-wider text-muted-foreground">Seconds</span>
            </div>
        `;
    }

    updateCountdown();
    setInterval(updateCountdown, 1000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Lucide icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
});

// Form submission handler
function handleFormSubmit(formId, actionUrl, method = 'POST') {
    const form = document.getElementById(formId);
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const submitButton = form.querySelector('button[type="submit"]');
        const originalText = submitButton ? submitButton.innerHTML : '';
        
        // Disable submit button
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = 'Loading...';
        }

        try {
            const response = await fetch(actionUrl, {
                method: method,
                body: formData,
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                },
            });

            const data = await response.json();

            if (response.ok) {
                // Success
                if (data.redirect) {
                    window.location.href = data.redirect;
                } else {
                    window.location.reload();
                }
            } else {
                // Error
                showError(data.error || data.message || 'An error occurred');
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.innerHTML = originalText;
                }
            }
        } catch (error) {
            console.error('Error:', error);
            showError('Network error. Please try again.');
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.innerHTML = originalText;
            }
        }
    });
}

// Get CSRF token from cookies
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Show error message
function showError(message) {
    // Create error alert
    const alert = document.createElement('div');
    alert.className = 'fixed top-20 right-4 bg-red-600 text-white px-6 py-4 rounded-lg shadow-lg z-50';
    alert.textContent = message;
    document.body.appendChild(alert);
    
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

// Show success message
function showSuccess(message) {
    const alert = document.createElement('div');
    alert.className = 'fixed top-20 right-4 bg-green-600 text-white px-6 py-4 rounded-lg shadow-lg z-50';
    alert.textContent = message;
    document.body.appendChild(alert);
    
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

