const API_BASE = 'http://localhost:8000/api';
let currentConversation = [];
let systemInfo = {};
let conversations = [];
let currentConversationId = null;
let currentLLMMode = 'cloud';

// ====================================================================
// LLM Mode Toggle Functions (defined early for onclick handlers)
// ====================================================================

async function initializeLLMMode() {
    try {
        const response = await fetch(`${API_BASE}/llm/mode`);
        if (response.ok) {
            const data = await response.json();
            currentLLMMode = data.current_mode;
            updateLLMModeUI(currentLLMMode);
            console.log(`[LLM Mode] Initialized: ${data.current_mode}`);
        }
    } catch (error) {
        console.error('[LLM Mode] Init error:', error);
        currentLLMMode = 'cloud';
        updateLLMModeUI('cloud');
    }
}

function toggleLLMMode() {
    // Toggle between local and cloud
    const newMode = currentLLMMode === 'local' ? 'cloud' : 'local';
    console.log(`[LLM Mode] Toggle activated: ${currentLLMMode} -> ${newMode}`);
    switchLLMMode(newMode);
}

async function switchLLMMode(mode) {
    console.log(`[LLM Mode] Attempting to switch to: ${mode}`);

    try {
        const response = await fetch(`${API_BASE}/llm/mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode })
        });

        if (!response.ok) {
            const error = await response.json();
            console.error('[LLM Mode] Switch error:', error);
            showNotification(`Failed to switch: ${error.detail || 'Unknown error'}`, 'error');
            return;
        }

        const data = await response.json();
        currentLLMMode = data.current_mode;
        updateLLMModeUI(currentLLMMode);

        console.log(`[LLM Mode] Switched successfully to: ${mode}`);
        showNotification(`Switched to ${mode.toUpperCase()} LLM mode`, 'success');
    } catch (error) {
        console.error('[LLM Mode] Error:', error);
        showNotification('Failed to switch LLM mode', 'error');
    }
}

function updateLLMModeUI(mode) {
    const toggle = document.getElementById('llmModeToggle');

    if (toggle) {
        toggle.classList.remove('local', 'cloud');
        toggle.classList.add(mode);
        console.log(`[LLM Mode] Toggle UI updated to: ${mode}`);
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 20px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 500;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 2000;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;

    const style = document.createElement('style');
    if (!document.getElementById('notificationStyle')) {
        style.id = 'notificationStyle';
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(400px);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadSystemInfo();
    loadConversations();
    loadTheme();
    initializeLLMMode();
});

// Load conversations from localStorage
function loadConversations() {
    const saved = localStorage.getItem('erpConversations');
    if (saved) {
        conversations = JSON.parse(saved);
        renderConversationsList();
    }
}

// Save conversations to localStorage
function saveConversations() {
    localStorage.setItem('erpConversations', JSON.stringify(conversations));
}

// Render conversations list
function renderConversationsList(searchQuery = '') {
    const listEl = document.getElementById('conversationsList');

    // Filter conversations based on search query
    let filteredConversations = conversations;
    if (searchQuery) {
        filteredConversations = conversations.filter(conv =>
            conv.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            conv.messages.some(msg =>
                msg.content.toLowerCase().includes(searchQuery.toLowerCase())
            )
        );
    }

    if (filteredConversations.length === 0) {
        listEl.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text-secondary); font-size: 14px;">${searchQuery ? 'No matching chats' : 'No conversations yet'}</div>`;
        return;
    }

    listEl.innerHTML = filteredConversations.map(conv => `
        <div class="conversation-item ${conv.id === currentConversationId ? 'active' : ''}" onclick="loadConversation('${conv.id}')">
            <div class="conversation-title">${escapeHtml(conv.title)}</div>
            <button class="conversation-delete" onclick="event.stopPropagation(); deleteConversation('${conv.id}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
            </button>
        </div>
    `).join('');
}

// Filter conversations based on search
function filterConversations(query) {
    renderConversationsList(query);
}

// Load a conversation
function loadConversation(id) {
    const conv = conversations.find(c => c.id === id);
    if (!conv) return;

    currentConversationId = id;
    currentConversation = conv.messages || [];

    const chatContainer = document.getElementById('chatContainer');
    chatContainer.innerHTML = '';

    if (currentConversation.length === 0) {
        document.getElementById('emptyState').style.display = 'flex';
    } else {
        currentConversation.forEach(msg => {
            if (msg.role === 'user') {
                appendMessage(msg.content, 'user');
            } else {
                appendMessage(msg.content, 'assistant', msg.sources);
            }
        });
    }

    renderConversationsList();

    // Close sidebar on mobile
    if (window.innerWidth <= 768) {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebarOverlay');
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('active');
    }
}

// Delete a conversation
let conversationToDelete = null;

function deleteConversation(id) {
    conversationToDelete = id;
    document.getElementById('deleteModal').classList.add('active');
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('active');
    conversationToDelete = null;
}

function confirmDelete() {
    if (!conversationToDelete) return;

    conversations = conversations.filter(c => c.id !== conversationToDelete);
    saveConversations();

    if (currentConversationId === conversationToDelete) {
        startNewChat();
    } else {
        renderConversationsList();
    }

    closeDeleteModal();
}

// Toggle profile menu
function toggleProfileMenu() {
    const menu = document.getElementById('profileMenu');
    menu.classList.toggle('active');
}

// Close profile menu when clicking outside
document.addEventListener('click', (e) => {
    const profileSection = document.querySelector('.profile-section');
    const profileMenu = document.getElementById('profileMenu');
    if (profileSection && !profileSection.contains(e.target)) {
        profileMenu?.classList.remove('active');
    }

    // Close delete modal when clicking backdrop
    const deleteModal = document.getElementById('deleteModal');
    if (e.target === deleteModal) {
        closeDeleteModal();
    }
});

// Open settings modal
function openSettings() {
    toggleProfileMenu();
    // Create settings modal content
    const modal = document.getElementById('infoModal');
    const content = document.getElementById('systemInfoContent');

    content.innerHTML = `
        <div class="info-panel">
            <h3>Settings</h3>
            <div class="info-item">
                <span>Theme</span>
                <button class="action-btn" onclick="toggleTheme(); openSettings();" style="border: 1px solid var(--border); padding: 6px 12px;">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                    </svg>
                    Toggle
                </button>
            </div>
            <div class="info-item">
                <span>Profile Name</span>
                <span class="info-value">User</span>
            </div>
            <div class="info-item">
                <span>Plan</span>
                <span class="info-value">Free</span>
            </div>
        </div>
        <div class="info-panel" style="margin-top: 16px;">
            <h3>System Status</h3>
            <div class="info-item">
                <span>Documents Indexed</span>
                <span class="info-value" id="docCount">${systemInfo.total_chunks || 'Loading...'}</span>
            </div>
            <div class="info-item">
                <span>Embedding Model</span>
                <span class="info-value">all-MiniLM-L6-v2</span>
            </div>
            <div class="info-item">
                <span>LLM Model</span>
                <span class="info-value">Mistral 7B (Ollama)</span>
            </div>
            <div class="info-item">
                <span>Vector Store</span>
                <span class="info-value">FAISS</span>
            </div>
        </div>
    `;

    document.querySelector('.modal-title').textContent = 'Settings';
    modal.classList.add('active');
}

// Toggle sidebar
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    if (window.innerWidth <= 768) {
        // Mobile: use mobile-open class and overlay
        sidebar.classList.toggle('mobile-open');
        overlay.classList.toggle('active');
    } else {
        // Desktop: use collapsed class
        sidebar.classList.toggle('collapsed');
    }
}

// Load theme
function loadTheme() {
    const theme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', theme);
}

// Load system info
async function loadSystemInfo() {
    try {
        const response = await fetch(`${API_BASE}/../info`);
        if (response.ok) {
            systemInfo = await response.json();
            document.getElementById('docCount').textContent = systemInfo.total_chunks || 'N/A';
        }
    } catch (error) {
        console.error('Failed to load system info:', error);
    }
}

// Auto-resize textarea
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

// Handle Enter key
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        submitQuery();
    }
}

// Theme toggle
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
}

// Load saved theme
const savedTheme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);

// ====================================================================
// LLM Mode Switching (Local Ollama vs Cloud Groq)
// ====================================================================

// Close LLM mode menu when clicking outside
document.addEventListener('click', (e) => {
    const toggle = document.getElementById('llmModeToggle');
    if (toggle && !toggle.contains(e.target)) {
        const menu = document.getElementById('llmModeMenu');
        if (menu) menu.classList.remove('active');
    }
});

// Start new chat
function startNewChat() {
    currentConversation = [];
    currentConversationId = null;
    renderConversationsList();
    document.getElementById('chatContainer').innerHTML = `
        <div class="empty-state" id="emptyState">
            <h1>How can I help you today?</h1>
            <p>Ask me anything about ERP systems, processes, and implementation</p>
            <div class="suggestions">
                <div class="suggestion-card" onclick="askSuggestion('What is ERP and what are its benefits?')">
                    <h3>What is ERP and its benefits?</h3>
                </div>
                <div class="suggestion-card" onclick="askSuggestion('Explain the accounts payable process')">
                    <h3>Explain accounts payable process</h3>
                </div>
                <div class="suggestion-card" onclick="askSuggestion('How do I implement manufacturing in ERP?')">
                    <h3>Manufacturing implementation guide</h3>
                </div>
                <div class="suggestion-card" onclick="askSuggestion('What are common ERP challenges?')">
                    <h3>Common ERP challenges</h3>
                </div>
            </div>
        </div>
    `;
}

// Ask suggestion
function askSuggestion(question) {
    document.getElementById('queryInput').value = question;
    submitQuery();
}

// Show/close modal
function showSystemInfo() {
    document.getElementById('infoModal').classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// Export chat
function exportChat() {
    const data = JSON.stringify(currentConversation, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `erp-chat-${new Date().toISOString().slice(0,10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

// ====================================================================
// Document Upload & Processing Pipeline
// ====================================================================

let uploadInProgress = false;

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showUploadStatus('Only PDF files are supported', 'error');
        return;
    }

    // Validate file size (max 50MB)
    if (file.size > 50 * 1024 * 1024) {
        showUploadStatus('File too large (max 50MB)', 'error');
        return;
    }

    if (uploadInProgress) {
        showUploadStatus('Upload already in progress', 'error');
        return;
    }

    uploadDocument(file);
}

async function uploadDocument(file) {
    uploadInProgress = true;
    const progressBar = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const statusDiv = document.getElementById('uploadStatus');

    // Show progress bar
    progressBar.classList.add('active');
    statusDiv.classList.remove('active');

    try {
        // Step 1: Upload file (0-30%)
        progressFill.style.width = '10%';
        progressText.textContent = 'Uploading file...';

        const formData = new FormData();
        formData.append('file', file);

        const uploadResponse = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!uploadResponse.ok) {
            throw new Error('Upload failed');
        }

        const uploadResult = await uploadResponse.json();
        progressFill.style.width = '30%';

        // Step 2: Process document (30-60%)
        progressText.textContent = 'Processing document...';
        await new Promise(resolve => setTimeout(resolve, 500));

        const ingestResponse = await fetch(`${API_BASE}/process-document`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: uploadResult.filename })
        });

        if (!ingestResponse.ok) {
            throw new Error('Document processing failed');
        }

        progressFill.style.width = '60%';

        // Step 3: Generate embeddings (60-90%)
        progressText.textContent = 'Generating embeddings...';
        await new Promise(resolve => setTimeout(resolve, 500));

        const embedResponse = await fetch(`${API_BASE}/generate-embeddings`, {
            method: 'POST'
        });

        if (!embedResponse.ok) {
            throw new Error('Embedding generation failed');
        }

        const embedResult = await embedResponse.json();
        progressFill.style.width = '90%';

        // Step 4: Reload RAG system (90-100%)
        progressText.textContent = 'Reloading system...';
        await new Promise(resolve => setTimeout(resolve, 500));

        const reloadResponse = await fetch(`${API_BASE}/reload`, {
            method: 'POST'
        });

        if (!reloadResponse.ok) {
            throw new Error('System reload failed');
        }

        progressFill.style.width = '100%';
        progressText.textContent = 'Complete!';

        // Show success message
        await new Promise(resolve => setTimeout(resolve, 500));
        progressBar.classList.remove('active');
        showUploadStatus(
            `✓ ${file.name} processed successfully! (${embedResult.total_chunks} chunks)`,
            'success'
        );

        // Reset file input
        document.getElementById('fileInput').value = '';

    } catch (error) {
        console.error('Upload error:', error);
        progressBar.classList.remove('active');
        showUploadStatus(`✗ Error: ${error.message}`, 'error');
    } finally {
        uploadInProgress = false;
    }
}

function showUploadStatus(message, type) {
    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.textContent = message;
    statusDiv.className = `upload-status ${type} active`;

    // Auto-hide after 5 seconds
    setTimeout(() => {
        statusDiv.classList.remove('active');
    }, 5000);
}

// Hide empty state
function hideEmptyState() {
    const emptyState = document.getElementById('emptyState');
    if (emptyState) emptyState.remove();
}

// Add message
function addMessage(role, content, sources = []) {
    hideEmptyState();

    const container = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = role === 'user' ? 'Y' : 'A';
    const formattedContent = role === 'assistant' ? formatMarkdown(content) : escapeHtml(content).replace(/\n/g, '<br>');

    // Get the last user query for feedback submission
    const lastUserQuery = currentConversation?.messages?.filter(m => m.role === 'user').slice(-1)[0]?.content || '';
    const messageId = Date.now();

    let html = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-text">${formattedContent}</div>
    `;

    if (sources && sources.length > 0) {
        html += `
            <div class="sources">
                <div class="sources-title">Sources</div>
                ${sources.map(source => `
                    <div class="source-item">
                        <div class="source-name">📄 ${escapeHtml(source.document_name)}</div>
                        <div class="source-excerpt">${escapeHtml(source.excerpt)}</div>
                        <div class="source-chunks">Chunks: ${source.chunk_ids.join(', ')}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // Add feedback buttons for assistant messages
    if (role === 'assistant') {
        html += `
            <div class="feedback-buttons" id="feedback-${messageId}" data-message-id="${messageId}">
                <button class="feedback-btn positive" data-rating="positive">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                    </svg>
                    Helpful
                </button>
                <button class="feedback-btn negative" data-rating="negative">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
                    </svg>
                    Not Helpful
                </button>
            </div>
        `;

        // Store message data for later use by event listeners
        feedbackData = feedbackData || {};
        feedbackData[messageId] = {
            messageId: messageId,
            query: lastUserQuery,
            answer: content,
            sources: sources || []
        };
    }

    html += '</div></div>';
    messageDiv.innerHTML = html;
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;

    // Add event listeners for feedback buttons
    if (role === 'assistant') {
        const feedbackContainer = document.getElementById(`feedback-${messageId}`);
        if (feedbackContainer && feedbackData && feedbackData[messageId]) {
            const data = feedbackData[messageId];
            feedbackContainer.querySelectorAll('.feedback-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    const rating = btn.dataset.rating;
                    console.log(`[Feedback Button] Clicked: ${rating} for message ${messageId}`);
                    await submitFeedback(messageId, rating, data.query, data.answer, data.sources);
                });
            });
        }
    }
}

// Global feedback data storage
let feedbackData = {};

// Submit feedback
async function submitFeedback(messageId, rating, query, answer, sources) {
    console.log(`[Feedback] Submitting: rating=${rating}, messageId=${messageId}`);
    console.log(`[Feedback] Query: "${query}"`);
    console.log(`[Feedback] Sources count: ${sources ? sources.length : 0}`);

    const feedbackContainer = document.getElementById(`feedback-${messageId}`);
    if (!feedbackContainer) {
        console.error(`[Feedback] Container not found: feedback-${messageId}`);
        return;
    }

    const buttons = feedbackContainer.querySelectorAll('.feedback-btn');

    // Disable buttons during submission
    buttons.forEach(btn => btn.disabled = true);

    try {
        const payload = {
            query: query,
            answer: answer,
            sources: sources || [],
            rating: rating,
            user_id: 'ui_user'
        };

        console.log(`[Feedback] Sending payload to ${API_BASE}/feedback`);

        const response = await fetch(`${API_BASE}/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        console.log(`[Feedback] Response status: ${response.status}`);

        if (response.ok) {
            const data = await response.json();
            console.log(`[Feedback] Success:`, data);

            // Mark the clicked button as active
            buttons.forEach(btn => {
                btn.classList.remove('active');
                if (btn.dataset.rating === rating) {
                    btn.classList.add('active');
                }
            });

            // Show success message
            const successMsg = document.createElement('span');
            successMsg.style.color = 'var(--accent)';
            successMsg.style.fontSize = '12px';
            successMsg.style.marginLeft = '12px';
            successMsg.textContent = '✓ Thank you for your feedback!';
            feedbackContainer.appendChild(successMsg);

            setTimeout(() => successMsg.remove(), 3000);
        } else {
            const errorData = await response.text();
            console.error(`[Feedback] Error response (${response.status}):`, errorData);
            throw new Error(`HTTP ${response.status}: ${errorData}`);
        }
    } catch (error) {
        console.error('[Feedback] Submission error:', error);
        alert('Failed to submit feedback: ' + error.message);
        buttons.forEach(btn => btn.disabled = false);
    }
}

// Show loading
function showLoading() {
    hideEmptyState();
    const container = document.getElementById('chatContainer');
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'loadingIndicator';
    loadingDiv.className = 'message assistant';
    loadingDiv.innerHTML = `
        <div class="message-avatar">A</div>
        <div class="message-content">
            <div class="loading">
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
            </div>
        </div>
    `;
    container.appendChild(loadingDiv);
    container.scrollTop = container.scrollHeight;
}

// Hide loading
function hideLoading() {
    const loading = document.getElementById('loadingIndicator');
    if (loading) loading.remove();
}

// Submit query
async function submitQuery() {
    const input = document.getElementById('queryInput');
    const query = input.value.trim();

    if (!query) return;

    // Create new conversation if none exists
    if (!currentConversationId) {
        const newConv = {
            id: Date.now().toString(),
            title: query.substring(0, 50) + (query.length > 50 ? '...' : ''),
            messages: [],
            createdAt: new Date().toISOString()
        };
        conversations.unshift(newConv);
        currentConversationId = newConv.id;
        saveConversations();
        renderConversationsList();
    }

    input.value = '';
    input.style.height = 'auto';

    // Add user message
    addMessage('user', query);
    currentConversation.push({ role: 'user', content: query });

    // Update conversation in storage
    updateCurrentConversation();

    // Show loading
    showLoading();
    document.getElementById('sendBtn').disabled = true;

    try {
        const response = await fetch(`${API_BASE}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });

        if (!response.ok) throw new Error('Request failed');

        const data = await response.json();
        hideLoading();

        addMessage('assistant', data.answer, data.sources);
        currentConversation.push({
            role: 'assistant',
            content: data.answer,
            sources: data.sources
        });

        // Update conversation in storage
        updateCurrentConversation();

    } catch (error) {
        hideLoading();
        addMessage('assistant', 'Sorry, I encountered an error. Please try again or check if the server is running.');
        console.error('Error:', error);
    } finally {
        document.getElementById('sendBtn').disabled = false;
    }
}

// Update current conversation in storage
function updateCurrentConversation() {
    const conv = conversations.find(c => c.id === currentConversationId);
    if (conv) {
        conv.messages = currentConversation;
        conv.updatedAt = new Date().toISOString();
        saveConversations();
    }
}

// Append message (used when loading conversation)
function appendMessage(content, role, sources = []) {
    addMessage(role, content, sources);
}

// Format markdown
function formatMarkdown(text) {
    let html = escapeHtml(text);

    html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^(\d+)\. (.+)$/gm, '<li style="margin-left: 20px;">$2</li>');
    html = html.replace(/^- (.+)$/gm, '<li style="list-style-type: disc; margin-left: 20px;">$1</li>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    html = '<p>' + html + '</p>';
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p><br>/g, '<p>');
    html = html.replace(/<br><\/p>/g, '</p>');

    return html;
}

// Escape HTML
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
