// Dashboard JavaScript

let dashboardCharts = {};

document.addEventListener('DOMContentLoaded', async () => {
    if (!DialIQ.requireAuth()) return;

    await loadUserInfo();
    await loadDashboardStats();
    await loadRecentCalls();
    await loadHotLeads();
    initCharts();
    initTabs();
});

async function loadUserInfo() {
    try {
        const user = DialIQ.getCurrentUser();
        if (user) {
            document.getElementById('userName').textContent = user.full_name || user.email;
            document.getElementById('ddUserName').textContent = user.full_name || user.email;
            document.getElementById('ddUserEmail').textContent = user.email;
            document.getElementById('userAvatar').textContent = (user.full_name || user.email).substring(0, 2).toUpperCase();
        }
    } catch (error) {
        console.error('Failed to load user info:', error);
    }
}

async function loadDashboardStats() {
    try {
        const [stats, wallet] = await Promise.all([
            DialIQ.apiRequest('/api/analytics/overview?days=30'),
            DialIQ.apiRequest('/api/wallet/balance')
        ]);

        if (stats) {
            document.getElementById('statTotalCalls').textContent = DialIQ.formatNumber(stats.total_calls);
            document.getElementById('statPickupRate').textContent = stats.pickup_rate.toFixed(1) + '%';
            document.getElementById('statAvgDuration').textContent = DialIQ.formatDuration(Math.round(stats.avg_duration));
            document.getElementById('statTotalCost').textContent = DialIQ.formatCurrency(stats.total_cost);

            // Update sidebar counts
            document.getElementById('walletBalance').textContent = DialIQ.formatCurrency(wallet?.balance || 0);
        }
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function loadRecentCalls() {
    try {
        const calls = await DialIQ.apiRequest('/api/calls?limit=10');
        const tbody = document.getElementById('recentCallsBody');

        if (calls && calls.length > 0) {
            tbody.innerHTML = calls.map(call => `
                <tr>
                    <td>
                        <div style="font-weight: 500;">${escapeHtml(call.phone_number)}</div>
                        <div style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(call.lead?.name || 'Unknown')}</div>
                    </td>
                    <td>${DialIQ.formatDuration(call.duration)}</td>
                    <td><span class="badge ${getStatusBadge(call.status)}">${formatStatus(call.status)}</span></td>
                    <td>${call.disposition ? `<span class="badge ${getDispositionBadge(call.disposition)}">${formatDisposition(call.disposition)}</span>` : '-'}</td>
                    <td>${DialIQ.formatCurrency(call.cost)}</td>
                    <td style="font-size: 0.85rem; color: var(--text-muted);">${formatDateTime(call.created_at)}</td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center" style="padding: 2rem; color: var(--text-muted);">No calls yet</td></tr>';
        }
    } catch (error) {
        console.error('Failed to load recent calls:', error);
        document.getElementById('recentCallsBody').innerHTML = '<tr><td colspan="6" class="text-center" style="padding: 2rem; color: var(--error);">Failed to load</td></tr>';
    }
}

async function loadHotLeads() {
    try {
        const leads = await DialIQ.apiRequest('/api/leads?disposition=hot_lead&limit=5');
        const container = document.getElementById('hotLeadsList');

        if (leads && leads.length > 0) {
            container.innerHTML = leads.map(lead => `
                <div style="padding: 1rem; border: 1px solid var(--border-gold); border-radius: var(--radius-md); margin-bottom: 0.75rem; background: var(--bg-secondary);">
                    <div class="flex-between">
                        <div>
                            <div style="font-weight: 600;">${escapeHtml(lead.name || 'Unknown')}</div>
                            <div style="font-size: 0.85rem; color: var(--accent-gold);">${escapeHtml(lead.phone)}</div>
                        </div>
                        <span class="badge badge-gold">Hot Lead</span>
                    </div>
                    ${lead.custom_fields?.company ? `<div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem;">${escapeHtml(lead.custom_fields.company)}</div>` : ''}
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--text-muted);">No hot leads yet. Start a campaign!</div>';
        }
    } catch (error) {
        console.error('Failed to load hot leads:', error);
        document.getElementById('hotLeadsList').innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--error);">Failed to load</div>';
    }
}

function initCharts() {
    // Volume Chart
    const volumeCtx = document.getElementById('volumeChart');
    if (volumeCtx) {
        drawVolumeChart(volumeCtx.getContext('2d'));
    }

    // Outcome Chart
    const outcomeCtx = document.getElementById('outcomeChart');
    if (outcomeCtx) {
        drawOutcomeChart(outcomeCtx.getContext('2d'));
    }
}

function drawVolumeChart(ctx) {
    const canvas = ctx.canvas;
    const width = canvas.width = canvas.offsetWidth;
    const height = canvas.height = canvas.offsetHeight;
    const padding = 40;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    // Sample data for demo
    const data = [
        { day: 'Mon', calls: 45, answered: 28 },
        { day: 'Tue', calls: 52, answered: 35 },
        { day: 'Wed', calls: 38, answered: 22 },
        { day: 'Thu', calls: 61, answered: 41 },
        { day: 'Fri', calls: 55, answered: 38 },
        { day: 'Sat', calls: 20, answered: 12 },
        { day: 'Sun', calls: 15, answered: 8 }
    ];

    const maxVal = Math.max(...data.map(d => d.calls)) * 1.2;

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Grid lines
    ctx.strokeStyle = 'rgba(212, 175, 55, 0.1)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = padding + (chartHeight / 4) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(width - padding, y);
        ctx.stroke();

        // Y-axis labels
        ctx.fillStyle = 'rgba(247, 244, 235, 0.5)';
        ctx.font = '11px Inter';
        ctx.textAlign = 'right';
        ctx.fillText(Math.round(maxVal * (1 - i / 4)), padding - 10, y + 4);
    }

    // Bars
    const barWidth = chartWidth / data.length * 0.6;
    const barGap = chartWidth / data.length * 0.4;

    data.forEach((d, i) => {
        const x = padding + i * (barWidth + barGap) + barGap / 2;
        const callHeight = (d.calls / maxVal) * chartHeight;
        const answeredHeight = (d.answered / maxVal) * chartHeight;

        // Call bars (background)
        ctx.fillStyle = 'rgba(212, 175, 55, 0.2)';
        ctx.fillRect(x, padding + chartHeight - callHeight, barWidth, callHeight);

        // Answered bars (foreground)
        const gradient = ctx.createLinearGradient(0, padding + chartHeight - answeredHeight, 0, padding + chartHeight);
        gradient.addColorStop(0, '#D4AF37');
        gradient.addColorStop(1, '#CC5500');
        ctx.fillStyle = gradient;
        ctx.fillRect(x, padding + chartHeight - answeredHeight, barWidth, answeredHeight);

        // Labels
        ctx.fillStyle = 'rgba(247, 244, 235, 0.7)';
        ctx.font = '11px Inter';
        ctx.textAlign = 'center';
        ctx.fillText(d.day, x + barWidth / 2, height - padding + 20);
    });

    // Legend
    ctx.fillStyle = '#D4AF37';
    ctx.fillRect(width - 160, 20, 12, 12);
    ctx.fillStyle = 'var(--text-cream)';
    ctx.font = '12px Inter';
    ctx.textAlign = 'left';
    ctx.fillText('Answered', width - 145, 30);

    ctx.fillStyle = 'rgba(212, 175, 55, 0.3)';
    ctx.fillRect(width - 80, 20, 12, 12);
    ctx.fillText('Total', width - 65, 30);
}

function drawOutcomeChart(ctx) {
    const canvas = ctx.canvas;
    const width = canvas.width = canvas.offsetWidth;
    const height = canvas.height = canvas.offsetHeight;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) / 2 - 50;

    // Sample data
    const data = [
        { label: 'Completed', value: 45, color: '#2E7D32' },
        { label: 'No Answer', value: 25, color: '#F57F17' },
        { label: 'Busy', value: 15, color: '#CC5500' },
        { label: 'Voicemail', value: 10, color: '#6A1B9A' },
        { label: 'Failed', value: 5, color: '#C62828' }
    ];

    const total = data.reduce((sum, d) => sum + d.value, 0);
    let startAngle = -Math.PI / 2;

    ctx.clearRect(0, 0, width, height);

    data.forEach(d => {
        const sliceAngle = (d.value / total) * 2 * Math.PI;

        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
        ctx.closePath();
        ctx.fillStyle = d.color;
        ctx.fill();

        // Label
        const midAngle = startAngle + sliceAngle / 2;
        const labelX = centerX + Math.cos(midAngle) * (radius * 0.7);
        const labelY = centerY + Math.sin(midAngle) * (radius * 0.7);

        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 12px Inter';
        ctx.textAlign = 'center';
        ctx.fillText(`${d.value}%`, labelX, labelY);

        startAngle += sliceAngle;
    });

    // Center text
    ctx.fillStyle = '#D4AF37';
    ctx.font = 'bold 24px Inter';
    ctx.textAlign = 'center';
    ctx.fillText(total > 0 ? '100%' : 'No Data', centerX, centerY + 8);

    ctx.fillStyle = 'var(--text-muted)';
    ctx.font = '11px Inter';
    ctx.fillText('Call Outcomes', centerX, centerY + 28);

    // Legend
    let legendY = height - 100;
    data.forEach((d, i) => {
        const col = i % 3;
        const row = Math.floor(i / 3);
        const x = centerX - 150 + col * 100;
        const y = legendY + row * 25;

        ctx.fillStyle = d.color;
        ctx.fillRect(x, y, 12, 12);

        ctx.fillStyle = 'var(--text-cream)';
        ctx.font = '11px Inter';
        ctx.textAlign = 'left';
        ctx.fillText(d.label, x + 18, y + 9);
    });
}

function initTabs() {
    document.querySelectorAll('.tabs').forEach(tabContainer => {
        tabContainer.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                tabContainer.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                // Chart re-rendering would go here
            });
        });
    });
}

function getStatusBadge(status) {
    const badges = {
        'completed': 'badge-green',
        'answered': 'badge-green',
        'busy': 'badge-amber',
        'no_answer': 'badge-blue',
        'voicemail': 'badge-purple',
        'failed': 'badge-red',
        'initiated': 'badge-gold',
        'ringing': 'badge-gold'
    };
    return badges[status] || 'badge-gold';
}

function formatStatus(status) {
    return status.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function getDispositionBadge(disposition) {
    const badges = {
        'hot_lead': 'badge-gold',
        'callback_requested': 'badge-blue',
        'not_interested': 'badge-red',
        'voicemail': 'badge-purple',
        'wrong_number': 'badge-amber',
        'do_not_call': 'badge-red',
        'follow_up': 'badge-blue'
    };
    return badges[disposition] || 'badge-gold';
}

function formatDisposition(disposition) {
    return disposition.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatDateTime(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function logout() {
    DialIQ.clearAuth();
    window.location.href = '/login';
}