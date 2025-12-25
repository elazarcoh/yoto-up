// Yoto Up Server - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    console.log('Yoto Up Server initialized');
    
    // Initialize drag-and-drop for upload page
    initDragAndDrop();
    
    // Initialize HTMX event handlers
    initHtmxHandlers();
    
    // Initialize icon edit buttons
    initIconEditButtons();
});

/**
 * Initialize icon edit button event listeners
 */
function initIconEditButtons() {
    document.addEventListener('click', function(e) {
        if (e.target.classList && e.target.classList.contains('icon-edit-btn')) {
            const chapterIndex = e.target.getAttribute('data-chapter-index');
            if (chapterIndex !== null) {
                openIconSidebar(parseInt(chapterIndex));
            }
        }
    });
}

/**
 * Initialize drag-and-drop functionality for file uploads
 */
function initDragAndDrop() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    
    if (!dropZone || !fileInput) return;
    
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    
    // Highlight drop zone when item is dragged over
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('border-indigo-500', 'bg-indigo-50', 'ring-2', 'ring-indigo-500');
            dropZone.classList.remove('border-gray-300', 'bg-gray-50');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('border-indigo-500', 'bg-indigo-50', 'ring-2', 'ring-indigo-500');
            dropZone.classList.add('border-gray-300', 'bg-gray-50');
        }, false);
    });
    
    // Handle dropped files
    dropZone.addEventListener('drop', function(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length > 0) {
            fileInput.files = files;
            // Trigger HTMX form submission
            const form = fileInput.closest('form');
            if (form && window.htmx) {
                htmx.trigger(form, 'submit');
            }
        }
    }, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

/**
 * Initialize HTMX event handlers
 */
function initHtmxHandlers() {
    // Auth complete handler - redirect to playlists
    document.body.addEventListener('auth-complete', function(e) {
        console.log('Authentication complete');
        // Optionally redirect
        // window.location.href = '/playlists/';
    });
    
    // Handle HTMX errors
    document.body.addEventListener('htmx:responseError', function(e) {
        console.error('HTMX request failed:', e.detail);
        showNotification('An error occurred. Please try again.', 'error');
    });
    
    // Handle HTMX before request - show loading
    document.body.addEventListener('htmx:beforeRequest', function(e) {
        // Add any global loading behavior here
    });
    
    // Handle HTMX after request - hide loading
    document.body.addEventListener('htmx:afterRequest', function(e) {
        // Add any global loading hide behavior here
    });
}

/**
 * Show a notification message
 */
function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container') || createNotificationContainer();
    
    const colors = {
        'info': 'bg-blue-50 text-blue-800 border-blue-200',
        'success': 'bg-green-50 text-green-800 border-green-200',
        'warning': 'bg-yellow-50 text-yellow-800 border-yellow-200',
        'error': 'bg-red-50 text-red-800 border-red-200'
    };
    
    const colorClass = colors[type] || colors['info'];
    
    const notification = document.createElement('div');
    notification.className = `rounded-md p-4 shadow-lg flex items-center justify-between min-w-[300px] border ${colorClass} mb-2 transition-all duration-300 transform translate-y-0 opacity-100`;
    notification.innerHTML = `
        <span class="font-medium">${message}</span>
        <button class="ml-4 text-current opacity-70 hover:opacity-100 focus:outline-none" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.classList.add('opacity-0', 'translate-y-[-10px]');
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notification-container';
    container.className = 'fixed top-20 right-5 z-50 flex flex-col items-end';
    document.body.appendChild(container);
    return container;
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!', 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showNotification('Failed to copy to clipboard', 'error');
    });
}

/**
 * Format duration in seconds to MM:SS
 */
function formatDuration(seconds) {
    if (!seconds) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Format file size in bytes to human readable
 */
function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let unitIndex = 0;
    let size = bytes;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

/**
 * Update chapter icon
 */
function updateChapterIcon(buttonElement, iconId) {
    const chapterIndex = document.querySelector('#icons-grid')?.dataset?.chapterIndex;
    const playlistId = window.location.pathname.split('/').pop();
    
    if (chapterIndex === undefined || chapterIndex === null) {
        alert('Chapter index not found');
        return;
    }
    
    const payload = {
        chapter_index: chapterIndex === 'batch' ? null : parseInt(chapterIndex),
        icon_id: iconId,
        playlist_id: playlistId
    };
    
    (async function() {
        try {
            const response = await fetch('/playlists/' + playlistId + '/update-chapter-icon', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            
            if (response.ok) {
                // Close sidebar and refresh
                const sidebar = document.getElementById('icon-sidebar');
                const overlay = document.getElementById('edit-overlay');
                if (sidebar) sidebar.remove();
                if (overlay) overlay.classList.add('hidden');
                window.location.reload();
            } else {
                const error = await response.json();
                alert('Error updating icon: ' + (error.detail || 'Unknown error'));
            }
        } catch (err) {
            console.error('Error:', err);
            alert('Failed to update icon: ' + err.message);
        }
    })();
}

/**
 * Open icon sidebar for selecting chapter icon
 */
function openIconSidebar(chapterIndex) {
    const playlistId = window.location.pathname.split('/').pop();
    
    // Create overlay if it doesn't exist
    let overlay = document.getElementById('edit-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'edit-overlay';
        overlay.className = 'fixed inset-0 bg-black bg-opacity-50 z-40';
        overlay.addEventListener('click', function(e) {
            if (e.target === this) {
                closeSidebar();
            }
        });
        document.body.appendChild(overlay);
    }
    overlay.classList.remove('hidden');
    
    // Load and show sidebar via HTMX
    htmx.ajax(
        'GET',
        `/playlists/${playlistId}/icon-sidebar?chapter_index=${chapterIndex}`,
        {
            target: 'body',
            swap: 'beforeend',
            settleInfo: { target: 'body' }
        }
    );
}

/**
 * Close icon sidebar
 */
function closeSidebar() {
    const sidebar = document.getElementById('icon-sidebar');
    const overlay = document.getElementById('edit-overlay');
    if (sidebar) sidebar.remove();
    if (overlay) overlay.classList.add('hidden');
}
