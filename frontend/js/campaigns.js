// Campaigns JavaScript

document.addEventListener('DOMContentLoaded', async () => {
    if (!DialIQ.requireAuth()) return;

    await loadAgentsForSelect();
    await loadCampaigns();
    setupFormHandlers();
    setupTabs();
});

async function loadAgentsForSelect() {
    try {
        const agents = await DialIQ.apiRequest('/api/agents');
        const select = document.getElementById('campaignAgent');
        if (agents && agents.length > 0) {
            select.innerHTML = agents.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('');
        } else {
            select.innerHTML = '<option value="">No agents available. Create one first.</option>';
        }
    } catch (error) {
        console.error('Failed to load agents:', error);
    }
}

async function loadCampaigns(status = 'all') {
    try {
        const campaigns = await DialIQ.apiRequest('/api/campaigns');
        const grid = document.getElementById('campaignsGrid');

        let filtered = campaigns;
        if (status !== 'all') {
            filtered = campaigns.filter(c => c.status === status);
        }

        if (filtered && filtered.length > 0) {
            grid.innerHTML = filtered.map(campaign => `
                <div class="card">
                    <div class="flex-between" style="margin-bottom: 1rem;">
                        <h3 style="font-size: 1.1rem;">${escapeHtml(campaign.name)}</h3>
                        <span class="badge ${getStatusBadge(campaign.status)}">${formatStatus(campaign.status)}</span>
                    </div>
                    <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1rem;">${escapeHtml(campaign.description || 'No description')}</p>
                    <div class="grid grid-3" style="margin-bottom: 1rem; font-size: 0.85rem;">
                        <div><span style="color: var(--text-muted);">Agent:</span> <span id="campaignAgent-${campaign.id}">Loading...</span></div>
                        <div><span style="color: var(--text-muted);">Leads:</span> ${campaign.total_leads}</div>
                        <div><span style="color: var(--text-muted);">Calls Made:</span> ${campaign.calls_made}</div>
                    </div>
                    <div class="grid grid-3" style="margin-bottom: 1rem; font-size: 0.85rem;">
                        <div><span style="color: var(--text-muted);">Answered:</span> ${campaign.calls_answered}</div>
                        <div><span style="color: var(--text-muted);">Completed:</span> ${campaign.calls_completed}</div>
                        <div><span style="color: var(--text-muted);">Cost:</span> ${DialIQ.formatCurrency(campaign.total_cost)}</div>
                    </div>
                    <div class="flex gap-2">
                        ${getCampaignActions(campaign)}
                    </div>
                </div>
            `).join('');

            // Load agent names
            for (const campaign of filtered) {
                const agentEl = document.getElementById(`campaignAgent-${campaign.id}`);
                if (agentEl && campaign.agent_id) {
                    try {
                        const agent = await DialIQ.apiRequest(`/api/agents/${campaign.agent_id}`);
                        if (agent) agentEl.textContent = agent.name;
                    } catch {}
                }
            }
        } else {
            grid.innerHTML = `
                <div class="card" style="text-align: center; padding: 3rem; grid-column: 1 / -1;">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--accent-gold)" stroke-width="1.5" style="margin-bottom: 1rem; opacity: 0.5;"><path d="M21 13.67A5 5 0 0 0 18 9a5 5 0 0 0-8.87-2.17 3 3 0 0 0 0 5.66A5 5 0 0 1 18 15a5 5 0 0 1 3 7.34"></path><path d="M22 12h-4"></path></svg>
                    <h3>No Campaigns Yet</h3>
                    <p style="color: var(--text-muted); margin: 1rem 0 2rem;">Create your first campaign to start automated calling</p>
                    <button class="btn btn-primary" onclick="openModal('campaignModal')">Create Campaign</button>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load campaigns:', error);
        DialIQ.showToast('Failed to load campaigns', 'error');
    }
}

function getStatusBadge(status) {
    const badges = {
        'draft': 'badge-gold',
        'scheduled': 'badge-blue',
        'running': 'badge-green',
        'paused': 'badge-amber',
        'completed': 'badge-blue',
        'cancelled': 'badge-red'
    };
    return badges[status] || 'badge-gold';
}

function formatStatus(status) {
    return status.charAt(0).toUpperCase() + status.slice(1);
}

function getCampaignActions(campaign) {
    switch (campaign.status) {
        case 'draft':
            return `
                <button class="btn btn-primary flex-1" onclick="startCampaign(${campaign.id})"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Start</button>
                <button class="btn btn-secondary" onclick="editCampaign(${campaign.id})"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg></button>
                <button class="btn btn-ghost" onclick="deleteCampaign(${campaign.id})"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button>
            `;
        case 'running':
            return `
                <button class="btn btn-secondary flex-1" onclick="pauseCampaign(${campaign.id})"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg> Pause</button>
                <button class="btn btn-outline" onclick="stopCampaign(${campaign.id})"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="12" height="16"></rect></svg> Stop</button>
            `;
        case 'paused':
            return `
                <button class="btn btn-primary flex-1" onclick="startCampaign(${campaign.id})"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Resume</button>
                <button class="btn btn-outline" onclick="stopCampaign(${campaign.id})"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="12" height="16"></rect></svg> Stop</button>
            `;
        case 'completed':
        case 'cancelled':
            return `
                <button class="btn btn-secondary" onclick="viewCampaign(${campaign.id})"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> View</button>
            `;
        default:
            return '';
    }
}

function setupFormHandlers() {
    const form = document.getElementById('campaignForm');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = form.querySelector('button[type="submit"]');
        const originalHtml = btn.innerHTML;

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner spinner-sm"></span> Saving...';

        try {
            const formData = new FormData(form);
            const data = {
                name: formData.get('name'),
                description: formData.get('description'),
                agent_id: parseInt(formData.get('agent_id')),
                timezone: formData.get('timezone'),
                start_time: formData.get('start_time') || null,
                end_time: formData.get('end_time') || null,
                concurrent_calls: parseInt(formData.get('concurrent_calls')),
                retry_attempts: parseInt(formData.get('retry_attempts')),
                retry_interval: parseInt(formData.get('retry_interval')),
                retry_on: formData.getAll('retry_on')
            };

            const campaignId = formData.get('id');
            if (campaignId) {
                await DialIQ.apiRequest(`/api/campaigns/${campaignId}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                DialIQ.showToast('Campaign updated', 'success');
            } else {
                await DialIQ.apiRequest('/api/campaigns', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                DialIQ.showToast('Campaign created', 'success');
            }

            closeModal('campaignModal');
            await loadCampaigns(getCurrentTab());
        } catch (error) {
            DialIQ.showToast(error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    });
}

function setupTabs() {
    document.querySelectorAll('#campaignTabs .tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#campaignTabs .tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadCampaigns(btn.dataset.status);
        });
    });
}

function getCurrentTab() {
    const active = document.querySelector('#campaignTabs .tab-btn.active');
    return active ? active.dataset.status : 'all';
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        const form = document.getElementById('campaignForm');
        form.reset();
        document.getElementById('campaignId').value = '';
        document.getElementById('campaignModalTitle').textContent = 'Create Campaign';
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
}

async function editCampaign(id) {
    try {
        const campaign = await DialIQ.apiRequest(`/api/campaigns/${id}`);
        if (!campaign) return;

        openModal('campaignModal');
        document.getElementById('campaignModalTitle').textContent = 'Edit Campaign';
        document.getElementById('campaignId').value = campaign.id;

        const form = document.getElementById('campaignForm');
        Object.keys(campaign).forEach(key => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input) {
                if (input.type === 'checkbox') {
                    input.checked = campaign[key]?.includes(input.value);
                } else if (key === 'start_time' || key === 'end_time') {
                    if (campaign[key]) {
                        input.value = campaign[key].replace(' ', 'T').substring(0, 16);
                    }
                } else {
                    input.value = campaign[key] || '';
                }
            }
        });

        // Handle retry_on checkboxes
        if (campaign.retry_on) {
            campaign.retry_on.forEach(val => {
                const cb = form.querySelector(`[name="retry_on"][value="${val}"]`);
                if (cb) cb.checked = true;
            });
        }
    } catch (error) {
        DialIQ.showToast('Failed to load campaign', 'error');
    }
}

async function startCampaign(id) {
    try {
        await DialIQ.apiRequest(`/api/campaigns/${id}/start`, { method: 'POST' });
        DialIQ.showToast('Campaign started', 'success');
        await loadCampaigns(getCurrentTab());
    } catch (error) {
        DialIQ.showToast(error.message, 'error');
    }
}

async function pauseCampaign(id) {
    try {
        await DialIQ.apiRequest(`/api/campaigns/${id}/pause`, { method: 'POST' });
        DialIQ.showToast('Campaign paused', 'success');
        await loadCampaigns(getCurrentTab());
    } catch (error) {
        DialIQ.showToast(error.message, 'error');
    }
}

async function stopCampaign(id) {
    if (!confirm('Stop this campaign?')) return;
    try {
        await DialIQ.apiRequest(`/api/campaigns/${id}/stop`, { method: 'POST' });
        DialIQ.showToast('Campaign stopped', 'success');
        await loadCampaigns(getCurrentTab());
    } catch (error) {
        DialIQ.showToast(error.message, 'error');
    }
}

async function deleteCampaign(id) {
    if (!confirm('Delete this campaign?')) return;
    try {
        await DialIQ.apiRequest(`/api/campaigns/${id}`, { method: 'DELETE' });
        DialIQ.showToast('Campaign deleted', 'success');
        await loadCampaigns(getCurrentTab());
    } catch (error) {
        DialIQ.showToast(error.message, 'error');
    }
}

function viewCampaign(id) {
    window.location.href = `/calls?campaign=${id}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}