"""
HTMX helper components for minimal inline JavaScript.

These components provide the bare minimum JavaScript needed for features
that cannot be implemented purely with HTMX, such as:
- Browser APIs (clipboard, file picker)
- Third-party library initialization (Sortable.js)
- Event handlers that must run client-side
"""

from pydom import Component
from pydom import html as d


class ClipboardCopyScript(Component):
    """Minimal script for copying text to clipboard."""
    
    def __init__(self, *, source_id: str, success_message: str = "Copied!"):
        super().__init__()
        self.source_id = source_id
        self.success_message = success_message
    
    def render(self):
        return d.Script()(f"""
            function copyToClipboard_{self.source_id}() {{
                const text = document.getElementById('{self.source_id}').textContent;
                navigator.clipboard.writeText(text).then(() => {{
                    htmx.trigger(document.body, 'show-toast', {{detail: {{message: '{self.success_message}', type: 'success'}}}});
                }}).catch(err => {{
                    htmx.trigger(document.body, 'show-toast', {{detail: {{message: 'Failed to copy', type: 'error'}}}});
                }});
            }}
        """)


class FilePickerScript(Component):
    """Minimal script for triggering file/folder picker."""
    
    def render(self):
        return d.Script()("""
            function triggerFilePicker(inputId) {
                document.getElementById(inputId).click();
            }
            
            async function triggerFolderPicker(inputId) {
                const input = document.getElementById(inputId);
                if ('showDirectoryPicker' in window) {
                    try {
                        const dirHandle = await showDirectoryPicker();
                        const files = [];
                        await collectAudioFiles(dirHandle, files);
                        
                        // Create a DataTransfer to set files on the input
                        const dataTransfer = new DataTransfer();
                        files.forEach(file => dataTransfer.items.add(file));
                        input.files = dataTransfer.files;
                        
                        // Trigger change event
                        input.dispatchEvent(new Event('change', {bubbles: true}));
                    } catch (err) {
                        if (err.name !== 'AbortError') {
                            console.error('Folder picker error:', err);
                        }
                    }
                } else {
                    // Fallback: use webkitdirectory
                    input.setAttribute('webkitdirectory', '');
                    input.click();
                    input.removeAttribute('webkitdirectory');
                }
            }
            
            async function collectAudioFiles(dirHandle, files) {
                const audioExtensions = ['.mp3', '.m4a', '.wav', '.flac', '.aac', '.ogg'];
                for await (const entry of dirHandle.values()) {
                    if (entry.kind === 'file') {
                        if (audioExtensions.some(ext => entry.name.toLowerCase().endsWith(ext))) {
                            const file = await entry.getFile();
                            files.push(file);
                        }
                    } else if (entry.kind === 'directory') {
                        await collectAudioFiles(entry, files);
                    }
                }
            }
        """)


class SortableInitScript(Component):
    """Initialize Sortable.js for drag-and-drop reordering."""
    
    def __init__(self, *, list_id: str, save_endpoint: str, handle_class: str = "drag-handle"):
        super().__init__()
        self.list_id = list_id
        self.save_endpoint = save_endpoint
        self.handle_class = handle_class
    
    def render(self):
        return d.Script()(f"""
            document.addEventListener('DOMContentLoaded', function() {{
                const list = document.getElementById('{self.list_id}');
                if (list && typeof Sortable !== 'undefined') {{
                    Sortable.create(list, {{
                        handle: '.{self.handle_class}',
                        animation: 150,
                        ghostClass: 'opacity-50 bg-indigo-100',
                        onEnd: function(evt) {{
                            const items = Array.from(list.querySelectorAll('[data-chapter-index]'));
                            const newOrder = items.map(item => parseInt(item.getAttribute('data-chapter-index')));
                            
                            htmx.ajax('POST', '{self.save_endpoint}', {{
                                values: {{new_order: newOrder}},
                                swap: 'none'
                            }}).then(() => {{
                                htmx.trigger(document.body, 'show-toast', {{detail: {{message: 'Order saved!', type: 'success'}}}});
                            }}).catch(() => {{
                                htmx.trigger(document.body, 'show-toast', {{detail: {{message: 'Failed to save order', type: 'error'}}}});
                            }});
                        }}
                    }});
                }}
            }});
        """)


class ToastNotificationSystem(Component):
    """Simple toast notification system using HTMX events."""
    
    def render(self):
        return d.Fragment()(
            # Toast container
            d.Div(
                id="toast-container",
                classes="fixed top-4 right-4 z-[100] flex flex-col gap-2",
                **{"hx-on:show-toast": "showToast(event)"}
            )(),
            # Toast logic
            d.Script()("""
                function showToast(event) {
                    const {message, type} = event.detail;
                    const toast = document.createElement('div');
                    toast.className = `px-6 py-3 rounded-lg shadow-lg text-white transform transition-all ${
                        type === 'success' ? 'bg-green-600' : 'bg-red-600'
                    }`;
                    toast.textContent = message;
                    
                    const container = document.getElementById('toast-container');
                    container.appendChild(toast);
                    
                    setTimeout(() => {
                        toast.style.opacity = '0';
                        toast.style.transform = 'translateX(100%)';
                        setTimeout(() => toast.remove(), 300);
                    }, 4000);
                }
            """)
        )


class ToggleClassScript(Component):
    """Simple script for toggling CSS classes - used where HTMX swap is overkill."""
    
    def render(self):
        return d.Script()("""//js
            function toggleClass(elementId, className) {
                document.getElementById(elementId).classList.toggle(className);
            }
            
            function addClass(elementId, className) {
                document.getElementById(elementId).classList.add(className);
            }
            
            function removeClass(elementId, className) {
                document.getElementById(elementId).classList.remove(className);
            }
            
            function toggleChapter(chapterIndex) {
                const tracksContainer = document.getElementById(`tracks-container-${chapterIndex}`);
                const toggleBtn = document.getElementById(`toggle-btn-${chapterIndex}`);
                
                if (!tracksContainer || !toggleBtn) return;
                
                const isHidden = tracksContainer.classList.contains('hidden');
                if (isHidden) {
                    tracksContainer.classList.remove('hidden');
                    toggleBtn.textContent = '▼';
                } else {
                    tracksContainer.classList.add('hidden');
                    toggleBtn.textContent = '▶';
                }
            }
            
            function expandAll() {
                const chaptersListItems = document.querySelectorAll('#chapters-list > li');
                chaptersListItems.forEach((item, index) => {
                    const tracksContainer = item.querySelector('[id^="tracks-container-"]');
                    if (tracksContainer) {
                        tracksContainer.classList.remove('hidden');
                        const toggleBtn = item.querySelector('[id^="toggle-btn-"]');
                        if (toggleBtn) {
                            toggleBtn.textContent = '▼';
                        }
                    }
                });
            }
            
            function collapseAll() {
                const chaptersListItems = document.querySelectorAll('#chapters-list > li');
                chaptersListItems.forEach((item, index) => {
                    const tracksContainer = item.querySelector('[id^="tracks-container-"]');
                    if (tracksContainer) {
                        tracksContainer.classList.add('hidden');
                        const toggleBtn = item.querySelector('[id^="toggle-btn-"]');
                        if (toggleBtn) {
                            toggleBtn.textContent = '▶';
                        }
                    }
                });
            }
            
            function showEditCheckboxes() {
                const checkboxes = document.querySelectorAll('#chapters-list input[type="checkbox"]');
                checkboxes.forEach(cb => cb.classList.remove('hidden'));
            }
            
            function hideEditCheckboxes() {
                const checkboxes = document.querySelectorAll('#chapters-list input[type="checkbox"]');
                checkboxes.forEach(cb => cb.classList.add('hidden'));
            }
            
            // Handle HTMX events for edit mode
            document.addEventListener('htmx:afterSwap', function(evt) {
                if (evt.detail.target && evt.detail.target.id === 'edit-controls-container') {
                    const editContainer = document.getElementById('edit-controls-container');
                    if (editContainer) {
                        // Check if edit controls are present (they exist when in edit mode)
                        const hasEditControls = editContainer.querySelector('button') !== null;
                        if (hasEditControls) {
                            showEditCheckboxes();
                        } else {
                            hideEditCheckboxes();
                        }
                    }
                }
            });
            
            function toggleEditMode() {
                const editToggleBtn = document.getElementById('edit-toggle-btn');
                const editControls = document.getElementById('edit-controls-container');
                
                if (!editControls) return;
                
                const isEditMode = editControls.querySelector('button') !== null;
                
                if (isEditMode) {
                    // Exit edit mode
                    editToggleBtn.textContent = '✏️ Edit';
                    editControls.innerHTML = '';
                    hideEditCheckboxes();
                } else {
                    // Enter edit mode
                    editToggleBtn.textContent = '❌ Cancel';
                    showEditCheckboxes();
                }
            }
        """)
