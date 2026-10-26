// Agents JavaScript

let currentAgentId = null;

document.addEventListener('DOMContentLoaded', async () => {
    if (!DialIQ.requireAuth()) return;

    await loadAgents();
    setupFormHandlers();
    setupTransferToggle();
});

async function loadAgents() {
    try {
        const agents = await DialIQ.apiRequest('/api/agents');
        const grid = document.getElementById('agentsGrid');

        if (agents && agents.length > 0) {
            grid.innerHTML = agents.map(agent => `
                <div class="card" style="display: flex; flex-direction: column;">
                    <div class="flex-between" style="margin-bottom: 1rem;">
                        <h3 style="font-size: 1.1rem;">${escapeHtml(agent.name)}</h3>
                        <span class="badge ${agent.is_active ? 'badge-green' : 'badge-red'}">${agent.is_active ? 'Active' : 'Inactive'}</span>
                    </div>
                    <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1rem; flex: 1;">${escapeHtml(agent.description || 'No description')}</p>
                    <div class="flex gap-2 flex-wrap" style="margin-bottom: 1rem;">
                        <span class="badge badge-gold">${agent.language}</span>
                        ${agent.transfer_enabled ? '<span class="badge badge-blue">Human Handoff</span>' : ''}
                        ${agent.knowledge_base && agent.knowledge_base.length > 0 ? `<span class="badge badge-purple">${agent.knowledge_base.length} KB Items</span>` : ''}
                    </div>
                    <div class="flex gap-2">
                        <button class="btn btn-primary flex-1" onclick="editAgent(${agent.id})">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                            Edit
                        </button>
                        <button class="btn btn-secondary" onclick="testAgent(${agent.id})">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                            Test
                        </button>
                        <button class="btn btn-ghost" onclick="deleteAgent(${agent.id})">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </div>
                </div>
            `).join('');
        } else {
            grid.innerHTML = `
                <div class="card" style="text-align: center; padding: 3rem; grid-column: 1 / -1;">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--accent-gold)" stroke-width="1.5" style="margin-bottom: 1rem; opacity: 0.5;"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                    <h3>No AI Agents Yet</h3>
                    <p style="color: var(--text-muted); margin: 1rem 0 2rem;">Create your first AI telecalling agent to start automating calls</p>
                    <button class="btn btn-primary" onclick="openModal('agentModal')">Create Agent</button>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load agents:', error);
        DialIQ.showToast('Failed to load agents', 'error');
    }
}

function setupFormHandlers() {
    const form = document.getElementById('agentForm');
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
                system_prompt: formData.get('system_prompt'),
                greeting_message: formData.get('greeting_message'),
                language: formData.get('language'),
                speech_rate: parseFloat(formData.get('speech_rate')),
                pitch: parseFloat(formData.get('pitch')),
                volume: parseFloat(formData.get('volume')),
                background_ambiance: formData.get('background_ambiance') === 'on',
                transfer_enabled: formData.get('transfer_enabled') === 'on',
                transfer_number: formData.get('transfer_number'),
                objection_handling: [],
                knowledge_base: []
            };

            // Collect objection handling
            const triggers = formData.getAll('objection_trigger[]');
            const responses = formData.getAll('objection_response[]');
            const actions = formData.getAll('objection_action[]');
            for (let i = 0; i < triggers.length; i++) {
                if (triggers[i] && responses[i]) {
                    data.objection_handling.push({
                        trigger: triggers[i],
                        response: responses[i],
                        action: actions[i] || null
                    });
                }
            }

            // Collect knowledge base
            const kbQuestions = formData.getAll('kb_question[]');
            const kbAnswers = formData.getAll('kb_answer[]');
            const kbCategories = formData.getAll('kb_category[]');
            for (let i = 0; i < kbQuestions.length; i++) {
                if (kbQuestions[i] && kbAnswers[i]) {
                    data.knowledge_base.push({
                        question: kbQuestions[i],
                        answer: kbAnswers[i],
                        category: kbCategories[i] || null
                    });
                }
            }

            const agentId = formData.get('id');
            let result;

            if (agentId) {
                result = await DialIQ.apiRequest(`/api/agents/${agentId}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                DialIQ.showToast('Agent updated successfully', 'success');
            } else {
                result = await DialIQ.apiRequest('/api/agents', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                DialIQ.showToast('Agent created successfully', 'success');
            }

            closeModal('agentModal');
            await loadAgents();
        } catch (error) {
            DialIQ.showToast(error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    });
}

function setupTransferToggle() {
    const toggle = document.getElementById('transferEnabled');
    const group = document.getElementById('transferNumberGroup');
    toggle.addEventListener('change', () => {
        group.style.display = toggle.checked ? 'block' : 'none';
    });
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        // Reset form
        const form = document.getElementById('agentForm');
        form.reset();
        document.getElementById('agentId').value = '';
        document.getElementById('agentModalTitle').textContent = 'Create New Agent';
        document.getElementById('transferNumberGroup').style.display = 'none';
        document.getElementById('transferEnabled').checked = false;

        // Reset objection rows
        const objectionsContainer = document.getElementById('objectionsContainer');
        objectionsContainer.innerHTML = createObjectionRow();

        // Reset knowledge rows
        const knowledgeContainer = document.getElementById('knowledgeContainer');
        knowledgeContainer.innerHTML = createKnowledgeRow();

        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
}

function createObjectionRow() {
    return `
        <div class="objection-row card" style="padding: 1rem; margin-bottom: 0.75rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <input type="text" class="form-input" placeholder="Trigger phrase (e.g., 'too expensive')" style="flex: 1; min-width: 200px;" name="objection_trigger[]">
            <textarea class="form-input" placeholder="AI response" style="flex: 1; min-width: 200px; min-height: 60px;" name="objection_response[]"></textarea>
            <select class="form-select" name="objection_action[]" style="min-width: 150px;">
                <option value="">Continue</option>
                <option value="transfer">Transfer to Human</option>
                <option value="end_call">End Call</option>
            </select>
            <button type="button" class="btn btn-ghost btn-icon" onclick="removeObjectionRow(this)"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
        </div>
    `;
}

function createKnowledgeRow() {
    return `
        <div class="knowledge-row card" style="padding: 1rem; margin-bottom: 0.75rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <input type="text" class="form-input" placeholder="Question/Topic" style="flex: 1; min-width: 200px;" name="kb_question[]">
            <textarea class="form-input" placeholder="Answer" style="flex: 1; min-width: 200px; min-height: 60px;" name="kb_answer[]"></textarea>
            <input type="text" class="form-input" placeholder="Category (optional)" style="min-width: 150px;" name="kb_category[]">
            <button type="button" class="btn btn-ghost btn-icon" onclick="removeKnowledgeRow(this)"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
        </div>
    `;
}

function addObjectionRow() {
    const container = document.getElementById('objectionsContainer');
    container.insertAdjacentHTML('beforeend', createObjectionRow());
}

function removeObjectionRow(btn) {
    btn.closest('.objection-row').remove();
}

function addKnowledgeRow() {
    const container = document.getElementById('knowledgeContainer');
    container.insertAdjacentHTML('beforeend', createKnowledgeRow());
}

function removeKnowledgeRow(btn) {
    btn.closest('.knowledge-row').remove();
}

async function editAgent(id) {
    try {
        const agent = await DialIQ.apiRequest(`/api/agents/${id}`);
        if (!agent) return;

        openModal('agentModal');
        document.getElementById('agentModalTitle').textContent = 'Edit Agent';
        document.getElementById('agentId').value = agent.id;

        // Fill form
        const form = document.getElementById('agentForm');
        Object.keys(agent).forEach(key => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input) {
                if (input.type === 'checkbox') {
                    input.checked = agent[key];
                } else if (input.type === 'range') {
                    input.value = agent[key];
                } else {
                    input.value = agent[key] || '';
                }
            }
        });

        // Fill objection handling
        if (agent.objection_handling && agent.objection_handling.length > 0) {
            const container = document.getElementById('objectionsContainer');
            container.innerHTML = agent.objection_handling.map(obj => `
                <div class="objection-row card" style="padding: 1rem; margin-bottom: 0.75rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    <input type="text" class="form-input" placeholder="Trigger phrase" style="flex: 1; min-width: 200px;" name="objection_trigger[]" value="${escapeHtml(obj.trigger || '')}">
                    <textarea class="form-input" placeholder="AI response" style="flex: 1; min-width: 200px; min-height: 60px;" name="objection_response[]">${escapeHtml(obj.response || '')}</textarea>
                    <select class="form-select" name="objection_action[]" style="min-width: 150px;">
                        <option value="">Continue</option>
                        <option value="transfer" ${obj.action === 'transfer' ? 'selected' : ''}>Transfer to Human</option>
                        <option value="end_call" ${obj.action === 'end_call' ? 'selected' : ''}>End Call</option>
                    </select>
                    <button type="button" class="btn btn-ghost btn-icon" onclick="removeObjectionRow(this)"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
                </div>
            `).join('');
        }

        // Fill knowledge base
        if (agent.knowledge_base && agent.knowledge_base.length > 0) {
            const container = document.getElementById('knowledgeContainer');
            container.innerHTML = agent.knowledge_base.map(kb => `
                <div class="knowledge-row card" style="padding: 1rem; margin-bottom: 0.75rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    <input type="text" class="form-input" placeholder="Question/Topic" style="flex: 1; min-width: 200px;" name="kb_question[]" value="${escapeHtml(kb.question || '')}">
                    <textarea class="form-input" placeholder="Answer" style="flex: 1; min-width: 200px; min-height: 60px;" name="kb_answer[]">${escapeHtml(kb.answer || '')}</textarea>
                    <input type="text" class="form-input" placeholder="Category (optional)" style="min-width: 150px;" name="kb_category[]" value="${escapeHtml(kb.category || '')}">
                    <button type="button" class="btn btn-ghost btn-icon" onclick="removeKnowledgeRow(this)"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
                </div>
            `).join('');
        }

        // Handle transfer toggle
        document.getElementById('transferNumberGroup').style.display = agent.transfer_enabled ? 'block' : 'none';
        document.getElementById('transferEnabled').checked = agent.transfer_enabled;
    } catch (error) {
        DialIQ.showToast('Failed to load agent', 'error');
    }
}

function testAgent(id) {
    window.location.href = `/simulator?agent=${id}`;
}

async function deleteAgent(id) {
    if (!confirm('Are you sure you want to delete this agent?')) return;

    try {
        await DialIQ.apiRequest(`/api/agents/${id}`, { method: 'DELETE' });
        DialIQ.showToast('Agent deleted', 'success');
        await loadAgents();
    } catch (error) {
        DialIQ.showToast(error.message, 'error');
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}