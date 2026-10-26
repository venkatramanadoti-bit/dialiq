// Leads JavaScript

let currentPage = 1;
let totalPages = 1;
let allLeads = [];

document.addEventListener('DOMContentLoaded', async () => {
    if (!DialIQ.requireAuth()) return;

    await loadCampaignsForSelect();
    await loadLeads();
    setupFormHandlers();
    setupImportForm();
});

async function loadCampaignsForSelect() {
    try {
        const campaigns = await DialIQ.apiRequest('/api/campaigns');
        const selects = ['leadCampaign', 'importCampaign', 'campaignFilter'];
        selects.forEach(id => {
            const select = document.getElementById(id);
            if (select && campaigns) {
                const options = campaigns.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
                if (id === 'campaignFilter') {
                    select.innerHTML = '<option value="">All Campaigns</option>' + options;
                } else {
                    select.innerHTML = '<option value="">No Campaign</option>' + options;
                }
            }
        });
    } catch (error) {
        console.error('Failed to load campaigns:', error);
    }
}

async function loadLeads(page = 1) {
    try {
        currentPage = page;
        const params = new URLSearchParams({
            skip: (page - 1) * 50,
            limit: 50
        });

        const disposition = document.getElementById('dispositionFilter').value;
        const campaign = document.getElementById('campaignFilter').value;
        const search = document.getElementById('leadSearch').value;

        if (disposition) params.append('disposition', disposition);
        if (campaign) params.append('campaign_id', campaign);

        const leads = await DialIQ.apiRequest(`/api/leads?${params.toString()}`);
        const tbody = document.getElementById('leadsBody');

        if (leads && leads.length > 0) {
            tbody.innerHTML = leads.map(lead => `
                <tr>
                    <td>${escapeHtml(lead.name || 'Unknown')}</td>
                    <td>${escapeHtml(lead.phone)}</td>
                    <td>${escapeHtml(lead.email || '-')}</td>
                    <td>${lead.campaign_id ? `<span class="badge badge-gold">Campaign #${lead.campaign_id}</span>` : '-'}</td>
                    <td>${lead.disposition ? `<span class="badge ${getDispositionBadge(lead.disposition)}">${formatDisposition(lead.disposition)}</span>` : '<span style="color: var(--text-muted);">None</span>'}</td>
                    <td><div class="progress" style="width: 60px;"><div class="progress-bar" style="width: ${lead.score}%"></div></div> ${lead.score}</td>
                    <td>${lead.call_count}</td>
                    <td style="font-size: 0.85rem; color: var(--text-muted);">${lead.last_called_at ? new Date(lead.last_called_at).toLocaleDateString('en-IN', {day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'}) : 'Never'}</td>
                    <td>
                        <div class="table-actions">
                            <button class="btn btn-ghost btn-sm" onclick="viewLead(${lead.id})" title="View"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg></button>
                            <button class="btn btn-ghost btn-sm" onclick="editLead(${lead.id})" title="Edit"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg></button>
                            <button class="btn btn-ghost btn-sm" onclick="deleteLead(${lead.id})" title="Delete" style="color: var(--error);"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button>
                        </div>
                    </td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center" style="padding: 2rem; color: var(--text-muted);">No leads found</td></tr>';
        }

        document.getElementById('leadsCount').textContent = `${leads?.length || 0} leads`;
        updatePagination();
    } catch (error) {
        console.error('Failed to load leads:', error);
        DialIQ.showToast('Failed to load leads', 'error');
    }
}

function filterLeads() {
    loadLeads(1);
}

function changePage(delta) {
    const newPage = currentPage + delta;
    if (newPage >= 1 && newPage <= totalPages) {
        loadLeads(newPage);
    }
}

function updatePagination() {
    document.getElementById('prevPage').disabled = currentPage <= 1;
    document.getElementById('nextPage').disabled = currentPage >= totalPages;
}

function setupFormHandlers() {
    const form = document.getElementById('leadForm');
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
                phone: formData.get('phone'),
                email: formData.get('email'),
                campaign_id: formData.get('campaign_id') ? parseInt(formData.get('campaign_id')) : null,
                disposition: formData.get('disposition') || null,
                score: parseInt(formData.get('score')),
                notes: formData.get('notes')
            };

            const leadId = formData.get('id');
            if (leadId) {
                await DialIQ.apiRequest(`/api/leads/${leadId}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                DialIQ.showToast('Lead updated', 'success');
            } else {
                await DialIQ.apiRequest('/api/leads', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                DialIQ.showToast('Lead created', 'success');
            }

            closeModal('leadModal');
            await loadLeads(currentPage);
        } catch (error) {
            DialIQ.showToast(error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    });
}

function setupImportForm() {
    const form = document.getElementById('importForm');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = form.querySelector('button[type="submit"]');
        const originalHtml = btn.innerHTML;
        const fileInput = form.querySelector('input[type="file"]');
        const file = fileInput.files[0];

        if (!file) {
            DialIQ.showToast('Please select a CSV file', 'error');
            return;
        }

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner spinner-sm"></span> Importing...';

        try {
            const formData = new FormData();
            formData.append('file', file);
            const campaignId = document.getElementById('importCampaign').value;
            if (campaignId) formData.append('campaign_id', campaignId);

            const token = DialIQ.getAuthToken();
            const response = await fetch('/api/leads/upload-csv', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });

            const result = await response.json();

            if (!response.ok) throw new Error(result.detail || 'Import failed');

            DialIQ.showToast(`Successfully imported ${result.leads?.length || 0} leads`, 'success');
            closeModal('importModal');
            await loadLeads(1);
        } catch (error) {
            DialIQ.showToast(error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    });
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        if (modalId === 'leadModal') {
            const form = document.getElementById('leadForm');
            form.reset();
            document.getElementById('leadId').value = '';
            document.getElementById('leadModalTitle').textContent = 'Add Lead';
        }
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
}

async function editLead(id) {
    try {
        const lead = await DialIQ.apiRequest(`/api/leads/${id}`);
        if (!lead) return;

        openModal('leadModal');
        document.getElementById('leadModalTitle').textContent = 'Edit Lead';
        document.getElementById('leadId').value = lead.id;

        const form = document.getElementById('leadForm');
        Object.keys(lead).forEach(key => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input) input.value = lead[key] || '';
        });
    } catch (error) {
        DialIQ.showToast('Failed to load lead', 'error');
    }
}

function viewLead(id) {
    window.location.href = `/calls?lead=${id}`;
}

async function deleteLead(id) {
    if (!confirm('Delete this lead?')) return;
    try {
        await DialIQ.apiRequest(`/api/leads/${id}`, { method: 'DELETE' });
        DialIQ.showToast('Lead deleted', 'success');
        await loadLeads(currentPage);
    } catch (error) {
        DialIQ.showToast(error.message, 'error');
    }
}

function getDispositionBadge(disposition) {
    const badges = {
        'hot_lead': 'badge-gold',
        'callback_requested': 'badge-blue',
        'not_interested': 'badge-red',
        'voicemail': 'badge-purple',
        'follow_up': 'badge-blue'
    };
    return badges[disposition] || 'badge-gold';
}

function formatDisposition(disposition) {
    return disposition.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}