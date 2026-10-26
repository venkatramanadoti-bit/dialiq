// DialIQ Frontend JavaScript

// ==================== UTILITY FUNCTIONS ====================

function showToast(message, type = 'info', duration = 5000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span>${message}</span>
        <button class="btn btn-ghost btn-sm" onclick="this.parentElement.remove()" style="margin-left: auto;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </button>
    `;
    container.appendChild(toast);

    setTimeout(() => toast.remove(), duration);
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0
    }).format(amount);
}

function formatNumber(num) {
    return new Intl.NumberFormat('en-IN').format(num);
}

function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// ==================== NAVBAR ====================

const navbar = document.getElementById('navbar');
const navbarToggle = document.getElementById('navbarToggle');
const navbarMenu = document.getElementById('navbarMenu');

window.addEventListener('scroll', () => {
    if (navbar) {
        navbar.classList.toggle('scrolled', window.scrollY > 50);
    }
});

if (navbarToggle && navbarMenu) {
    navbarToggle.addEventListener('click', () => {
        navbarMenu.classList.toggle('active');
    });
}

// ==================== ROI CALCULATOR ====================

function calculateROI() {
    const callsPerDay = parseFloat(document.getElementById('callsPerDay')?.value) || 500;
    const avgDuration = parseFloat(document.getElementById('avgDuration')?.value) || 3;
    const convRate = parseFloat(document.getElementById('convRate')?.value) || 15;
    const dealValue = parseFloat(document.getElementById('dealValue')?.value) || 50000;
    const workDays = parseFloat(document.getElementById('workDays')?.value) || 22;
    const costPerMin = parseFloat(document.getElementById('costPerMin')?.value) || 6;

    const monthlyCalls = callsPerDay * workDays;
    const monthlyMinutes = monthlyCalls * avgDuration;
    const monthlyCost = monthlyMinutes * costPerMin;
    const leads = monthlyCalls * (convRate / 100);
    const revenue = leads * dealValue;
    const traditionalCost = monthlyCalls * 15 * 50; // 15 min avg, ₹50/min human agent
    const savings = traditionalCost - monthlyCost;

    const el = (id, val) => { const e = document.getElementById(id); if (e) e.textContent = val; };

    el('roiMonthlyCalls', formatNumber(monthlyCalls));
    el('roiMonthlyCost', formatCurrency(monthlyCost));
    el('roiLeads', formatNumber(Math.round(leads)));
    el('roiRevenue', formatCurrency(revenue));
    el('traditionalCost', formatCurrency(traditionalCost));
    el('savings', formatCurrency(savings));
}

// ==================== PRICING TOGGLE ====================

function toggleBilling() {
    const toggle = document.getElementById('billingToggle');
    const label = document.getElementById('billingLabel');
    if (toggle && label) {
        label.textContent = toggle.checked ? 'Annual Billing (Save 20%)' : 'Monthly Billing';
        // Update prices if needed
    }
}

// ==================== SIMULATOR ====================

let simConversation = [];
let simActive = false;
let recognition = null;

function initSimulator() {
    const input = document.getElementById('simInput');
    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && simActive) {
                sendSimMessage();
            }
        });
    }

    // Check for Web Speech API support
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-IN';

        recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(r => r[0].transcript)
                .join('');
            document.getElementById('simInput').value = transcript;
            if (event.results[0].isFinal) {
                sendSimMessage();
            }
        };

        recognition.onerror = (event) => {
            console.log('Speech recognition error:', event.error);
            stopVoiceInput();
        };

        recognition.onend = () => {
            stopVoiceInput();
        };
    } else {
        const voiceBtn = document.getElementById('btnVoiceInput');
        if (voiceBtn) {
            voiceBtn.style.display = 'none';
        }
    }
}

async function startSimCall() {
    const btn = document.getElementById('btnStartCall');
    const input = document.getElementById('simInput');
    const sendBtn = document.getElementById('btnSendMsg');
    const voiceBtn = document.getElementById('btnVoiceInput');
    const statusDot = document.getElementById('simStatusDot');
    const statusText = document.getElementById('simStatusText');

    if (!simActive) {
        simActive = true;
        simConversation = [];

        btn.innerHTML = '<span class="spinner spinner-sm"></span> Connecting...';
        btn.disabled = true;

        // Simulate connection delay
        await new Promise(r => setTimeout(r, 1000));

        // Get AI greeting
        try {
            const response = await fetch('/api/agents/demo/greeting', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ language: 'en-IN' })
            });
            const data = await response.json();
            addSimMessage('ai', data.greeting || "Hello! This is DialIQ AI assistant. How can I help you today?");
        } catch {
            addSimMessage('ai', "Hello! This is DialIQ AI assistant. How can I help you today?");
        }

        btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg> End Call';
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-secondary');
        btn.disabled = false;
        input.disabled = false;
        sendBtn.disabled = false;
        if (voiceBtn) voiceBtn.disabled = false;
        statusDot.classList.add('live');
        statusText.textContent = 'Call Connected';
        input.focus();
    } else {
        endSimCall();
    }
}

function endSimCall() {
    const btn = document.getElementById('btnStartCall');
    const input = document.getElementById('simInput');
    const sendBtn = document.getElementById('btnSendMsg');
    const voiceBtn = document.getElementById('btnVoiceInput');
    const statusDot = document.getElementById('simStatusDot');
    const statusText = document.getElementById('simStatusText');

    simActive = false;
    stopVoiceInput();

    btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M6.6 10.8l6.4-4.1 6.4 4.1V20.8l-6.4 4.1-6.4-4.1V10.8z"/></svg> Start Call';
    btn.classList.remove('btn-secondary');
    btn.classList.add('btn-primary');
    input.disabled = true;
    sendBtn.disabled = true;
    if (voiceBtn) voiceBtn.disabled = true;
    statusDot.classList.remove('live');
    statusText.textContent = 'Call Ended';
    input.value = '';

    addSimMessage('ai', "Thank you for trying DialIQ! Ready to automate your calls?");
    showToast('Call simulation ended', 'info');
}

async function sendSimMessage() {
    const input = document.getElementById('simInput');
    const text = input.value.trim();
    if (!text || !simActive) return;

    addSimMessage('customer', text);
    input.value = '';

    // Show typing indicator
    const typingId = showTypingIndicator();

    try {
        const response = await fetch('/api/agents/demo/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                conversation: simConversation,
                language: 'en-IN'
            })
        });
        const data = await response.json();

        removeTypingIndicator(typingId);
        addSimMessage('ai', data.response || "I understand. Can you tell me more?");

        // Check for disposition
        if (data.disposition) {
            showToast(`Lead tagged as: ${data.disposition.replace('_', ' ')}`, 'success');
        }
        if (data.should_transfer) {
            showToast('Transferring to human agent...', 'warning');
            setTimeout(endSimCall, 2000);
        }
    } catch (error) {
        removeTypingIndicator(typingId);
        addSimMessage('ai', "I'm having trouble connecting. Please try again.");
        console.error('Sim chat error:', error);
    }
}

function addSimMessage(speaker, text) {
    const transcript = document.getElementById('simTranscript');
    if (!transcript) return;

    const entry = document.createElement('div');
    entry.className = 'transcript-entry';
    entry.innerHTML = `
        <span class="transcript-speaker ${speaker}">${speaker === 'ai' ? 'DialIQ AI' : 'Customer'}</span>
        <span class="transcript-text">${escapeHtml(text)}</span>
    `;
    transcript.appendChild(entry);
    transcript.scrollTop = transcript.scrollHeight;

    simConversation.push({ speaker, text, timestamp: Date.now() });
}

function showTypingIndicator() {
    const transcript = document.getElementById('simTranscript');
    const id = 'typing-' + Date.now();
    const entry = document.createElement('div');
    entry.id = id;
    entry.className = 'transcript-entry';
    entry.innerHTML = `
        <span class="transcript-speaker ai">DialIQ AI</span>
        <span class="transcript-text"><span class="spinner spinner-sm" style="margin-right: 0.5rem;"></span>Typing...</span>
    `;
    transcript.appendChild(entry);
    transcript.scrollTop = transcript.scrollHeight;
    return id;
}

function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function startVoiceInput() {
    if (!recognition) {
        showToast('Voice input not supported in this browser', 'error');
        return;
    }

    const btn = document.getElementById('btnVoiceInput');
    btn.classList.add('btn-primary');
    btn.classList.remove('btn-outline');
    btn.innerHTML = '<span class="spinner spinner-sm"></span>';

    try {
        recognition.start();
    } catch (e) {
        console.log('Recognition start error:', e);
        stopVoiceInput();
    }
}

function stopVoiceInput() {
    const btn = document.getElementById('btnVoiceInput');
    if (btn) {
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-outline');
        btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="22"></line></svg>';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== ADD CREDITS ====================

function addCredits(amount) {
    if (amount === 0) {
        const custom = prompt('Enter custom amount (₹):');
        if (custom && !isNaN(custom)) {
            amount = parseFloat(custom);
        } else {
            return;
        }
    }

    // Check if user is logged in
    const token = localStorage.getItem('dialiq_token');
    if (!token) {
        showToast('Please login to add credits', 'warning');
        setTimeout(() => window.location.href = '/login', 1500);
        return;
    }

    // Redirect to wallet page with amount
    window.location.href = `/wallet?add=${amount}`;
}

// ==================== API HELPERS ====================

async function apiRequest(endpoint, options = {}) {
    const token = localStorage.getItem('dialiq_token');
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(endpoint, {
        ...options,
        headers
    });

    if (response.status === 401) {
        localStorage.removeItem('dialiq_token');
        localStorage.removeItem('dialiq_user');
        window.location.href = '/login';
        return null;
    }

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.detail || 'Request failed');
    }
    return data;
}

// ==================== AUTH HELPERS ====================

function getAuthToken() {
    return localStorage.getItem('dialiq_token');
}

function getCurrentUser() {
    const userStr = localStorage.getItem('dialiq_user');
    return userStr ? JSON.parse(userStr) : null;
}

function setAuth(token, user) {
    localStorage.setItem('dialiq_token', token);
    localStorage.setItem('dialiq_user', JSON.stringify(user));
}

function clearAuth() {
    localStorage.removeItem('dialiq_token');
    localStorage.removeItem('dialiq_user');
}

function requireAuth() {
    if (!getAuthToken()) {
        window.location.href = '/login';
        return false;
    }
    return true;
}

// ==================== MODAL HELPERS ====================

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('active');
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    }
});

// ==================== FORM HANDLERS ====================

function handleFormSubmit(formId, submitFn) {
    const form = document.getElementById(formId);
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn?.innerHTML;

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner spinner-sm"></span> Processing...';
        }

        try {
            await submitFn(new FormData(form));
        } catch (error) {
            showToast(error.message, 'error');
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        }
    });
}

// ==================== TABLE SORTING ====================

function initTableSort(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;

    table.querySelectorAll('th[data-sort]').forEach(th => {
        th.style.cursor = 'pointer';
        th.addEventListener('click', () => {
            const column = th.dataset.sort;
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const isAsc = th.classList.contains('sort-asc');

            rows.sort((a, b) => {
                const aVal = a.querySelector(`td[data-${column}]`)?.dataset[column] || a.cells[0].textContent;
                const bVal = b.querySelector(`td[data-${column}]`)?.dataset[column] || b.cells[0].textContent;
                return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
            });

            table.querySelectorAll('th').forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
            th.classList.add(isAsc ? 'sort-desc' : 'sort-asc');

            rows.forEach(row => tbody.appendChild(row));
        });
    });
}

// ==================== CHART HELPERS ====================

function createChart(canvasId, type, data, options = {}) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return null;

    // Simple chart implementation without Chart.js dependency
    // This is a placeholder - in production, use Chart.js or similar
    return { ctx, data, options };
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize tooltips
    document.querySelectorAll('[data-tooltip]').forEach(el => {
        el.addEventListener('mouseenter', () => {
            // Tooltip handled by CSS
        });
    });

    // Initialize dropdowns
    document.querySelectorAll('.dropdown').forEach(dropdown => {
        dropdown.addEventListener('mouseleave', () => {
            dropdown.classList.remove('active');
        });
    });

    // Auto-hide toasts after animation
    setInterval(() => {
        document.querySelectorAll('.toast').forEach(toast => {
            if (!toast.dataset.hovered) {
                // Toast auto-removal handled by showToast
            }
        });
    }, 1000);
});

// Export for global access
window.DialIQ = {
    showToast,
    formatCurrency,
    formatNumber,
    formatDuration,
    apiRequest,
    getAuthToken,
    getCurrentUser,
    setAuth,
    clearAuth,
    requireAuth,
    openModal,
    closeModal,
    handleFormSubmit,
    initTableSort
};