"""
Refactored playlist detail component using HTMX patterns.
This replaces the JS-heavy version with server-side rendering.
"""

from pydom import Component
from pydom import html as d

from yoto_up.models import Card
from yoto_up_server.templates.components import ChapterItem
from yoto_up_server.templates.htmx_helpers import (
    ClipboardCopyScript,
    FilePickerScript,
    SortableInitScript,
    ToastNotificationSystem,
    ToggleClassScript,
)
from yoto_up_server.templates.icon_components import IconSidebarPartial


class PlaylistDetailRefactored(Component):
    """Refactored playlist detail page using HTMX principles."""
    
    def __init__(self, card: Card):
        super().__init__()
        self.card = card
    
    def render(self):
        title = self.card.title or "Untitled"
        description = ""
        cover_url = None
        
        # Get cover from metadata
        if self.card.metadata:
            description = getattr(self.card.metadata, 'description', "")
            cover = getattr(self.card.metadata, 'cover', None)
            if cover:
                cover_url = getattr(cover, 'imageL', None)
        
        # Get chapters from card content if available
        chapters = []
        if hasattr(self.card, 'content') and self.card.content:
            content = self.card.content
            if hasattr(content, 'chapters') and content.chapters:
                chapters = content.chapters
        
        return d.Div(classes="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8", id="playlist-detail", **{"data-playlist-id": self.card.cardId})(
            # Include necessary JavaScript libraries and helpers
            d.Script(src="https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js"),
            SortableInitScript(
                list_id="chapters-list",
                save_endpoint=f"/playlists/{self.card.cardId}/reorder-chapters",
                handle_class="drag-handle",
            ),
            FilePickerScript(),
            ToggleClassScript(),
            ClipboardCopyScript(source_id="json_content", success_message="JSON copied to clipboard!"),
            ToastNotificationSystem(),
            
            # Event listener for HTMX edit mode toggle
            d.Script()("""//js
            // Listen for HTMX after-settle events on the edit controls container
            document.addEventListener('htmx:afterSettle', function(event) {
                if(event.detail.target.id === 'edit-controls-container') {
                    // Check if edit controls were loaded (have buttons)
                    const hasButtons = document.querySelector('#edit-controls-container button');
                    const checkboxes = document.querySelectorAll('#chapters-list input[type=checkbox]');
                    if(hasButtons) {
                        checkboxes.forEach(cb => cb.classList.remove('hidden'));
                    } else {
                        checkboxes.forEach(cb => cb.classList.add('hidden'));
                    }
                }
            });
            """),
            
            # Header
            d.Div(classes="mb-6")(
                d.A(href="/playlists/", classes="inline-flex items-center px-4 py-2 text-indigo-600 hover:text-indigo-900 hover:bg-indigo-50 rounded-md transition-colors")(
                    d.Span(classes="mr-2")("←"), "Back to Playlists"
                )
            ),
            
            # Main content
            d.Div(classes="bg-white shadow-lg rounded-lg overflow-hidden")(
                # Header section
                self._render_header(title, description, cover_url),
                
                # Active uploads section (displays upload progress for each file)
                d.Div(id="active-uploads-container", classes="border-t border-gray-200 px-6 py-6 bg-gray-50")(
                    d.H3(classes="text-lg font-semibold text-gray-900 mb-4")("⬆️ Active Uploads"),
                    d.Div(id="uploads-list", classes="space-y-4"),
                    
                    # Script to manage active uploads
                    d.Script()(r"""//js
                    // Poll for active upload sessions
                    async function pollActiveUploads() {
                        try {
                            const response = await fetch(`/playlists/""" + self.card.cardId + r"""/upload-sessions`);
                            if (!response.ok) return;
                            
                            const data = await response.json();
                            const uploadsList = document.getElementById('uploads-list');
                            const container = document.getElementById('active-uploads-container');
                            
                            if (!data.sessions || data.sessions.length === 0) {
                                container.classList.add('hidden');
                                return;
                            }
                            
                            container.classList.remove('hidden');
                            
                            // Update each session
                            for (const session of data.sessions) {
                                updateSessionDisplay(session);
                            }
                        } catch (error) {
                            console.error('Error polling uploads:', error);
                        }
                    }
                    
                    async function dismissSession(sessionId) {
                        try {
                            const response = await fetch(`/playlists/""" + self.card.cardId + r"""/upload-session/${sessionId}`, {
                                method: 'DELETE'
                            });
                            if (response.ok) {
                                document.getElementById(`upload-${sessionId}`).remove();
                                pollActiveUploads();
                            }
                        } catch (error) {
                            console.error('Error dismissing session:', error);
                            alert('Failed to dismiss session');
                        }
                    }
                    
                    async function stopSession(sessionId) {
                        if (!confirm('Stop this upload session? This will revert to the last saved state.')) {
                            return;
                        }
                        
                        try {
                            const response = await fetch(`/playlists/""" + self.card.cardId + r"""/upload-session/${sessionId}/stop`, {
                                method: 'POST'
                            });
                            if (response.ok) {
                                // Remove the session from UI
                                document.getElementById(`upload-${sessionId}`).remove();
                                pollActiveUploads();
                            } else {
                                alert('Failed to stop session');
                            }
                        } catch (error) {
                            console.error('Error stopping session:', error);
                            alert('Failed to stop session');
                        }
                    }
                    
                    function updateSessionDisplay(session) {
                        let sessionEl = document.getElementById(`upload-${session.session_id}`);
                        
                        if (!sessionEl) {
                            sessionEl = document.createElement('div');
                            sessionEl.id = `upload-${session.session_id}`;
                            document.getElementById('uploads-list').appendChild(sessionEl);
                        }
                        
                        const isDone = session.overall_status === 'done';
                        const isError = session.overall_status === 'error';
                        const borderColor = isDone ? 'border-green-200 bg-green-50' : isError ? 'border-red-200 bg-red-50' : 'border-blue-200 bg-white';
                        sessionEl.className = `border rounded-lg p-4 ${borderColor}`;
                        
                        // Build file list with states
                        const filesHtml = (session.files || []).map(file => {
                            let stateIcon = '⏳';
                            let stateColor = 'text-gray-600';
                            let stateLabel = file.status || 'pending';
                            
                            if (file.status === 'completed') {
                                stateIcon = '✅';
                                stateColor = 'text-green-600';
                            } else if (file.status === 'yoto_uploading') {
                                stateIcon = '⬆️';
                                stateColor = 'text-blue-600';
                            } else if (file.status === 'converting') {
                                stateIcon = '🔄';
                                stateColor = 'text-yellow-600';
                            } else if (file.status === 'normalizing') {
                                stateIcon = '🔊';
                                stateColor = 'text-purple-600';
                            } else if (file.status === 'queued') {
                                stateIcon = '📋';
                                stateColor = 'text-indigo-600';
                            } else if (file.status === 'uploading') {
                                stateIcon = '⬆️';
                                stateColor = 'text-blue-600';
                            } else if (file.status === 'pending') {
                                stateIcon = '⏳';
                                stateColor = 'text-gray-500';
                            } else if (file.status === 'error') {
                                stateIcon = '❌';
                                stateColor = 'text-red-600';
                            }
                            
                            return `<div class="flex items-center justify-between py-2 px-2 bg-gray-50 rounded hover:bg-gray-100 transition-colors">
                                <span class="text-sm text-gray-800 flex-1">📄 ${file.filename}</span>
                                <span class="${stateColor} text-sm font-medium whitespace-nowrap ml-2">${stateIcon} ${stateLabel.replace(/_/g, ' ')}</span>
                            </div>`;
                        }).join('');
                        
                        const totalFiles = session.files ? session.files.length : 0;
                        const doneFiles = session.files ? session.files.filter(f => f.status === 'completed').length : 0;
                        const progress = totalFiles > 0 ? Math.round((doneFiles / totalFiles) * 100) : 0;
                        
                        let actionButtons = '';
                        if (isDone) {
                            actionButtons = `
                                <button onclick="dismissSession('${session.session_id}')" 
                                        class="px-3 py-1 text-sm bg-green-600 hover:bg-green-700 text-white rounded transition-colors">
                                    Dismiss
                                </button>
                            `;
                        } else {
                            actionButtons = `
                                <button onclick="stopSession('${session.session_id}')" 
                                        class="px-3 py-1 text-sm bg-red-600 hover:bg-red-700 text-white rounded transition-colors">
                                    Stop Upload
                                </button>
                            `;
                        }
                        
                        sessionEl.innerHTML = `
                            <div class="mb-3">
                                <div class="flex justify-between items-center mb-2">
                                    <div>
                                        <span class="font-medium text-gray-900">Upload Session ${session.session_id.substring(0, 8)}</span>
                                        <span class="text-xs text-gray-500 ml-2">${isDone ? '✓ Complete' : isError ? '✗ Error' : 'Processing'}</span>
                                    </div>
                                    <span class="text-sm text-gray-600 font-semibold">${doneFiles}/${totalFiles} files</span>
                                </div>
                                <div class="w-full bg-gray-200 rounded-full h-2.5 mb-3">
                                    <div class="bg-blue-600 h-2.5 rounded-full transition-all" style="width: ${progress}%"></div>
                                </div>
                                <div class="text-xs text-gray-600">${progress}% complete</div>
                            </div>
                            <div class="space-y-1 mb-3">
                                ${filesHtml}
                            </div>
                            <div class="flex justify-end">
                                ${actionButtons}
                            </div>
                        `;
                    }
                    
                    // Start polling every 2 seconds
                    pollActiveUploads();
                    setInterval(pollActiveUploads, 2000);
                    """),
                ),
                
                # Chapters/Items section
                self._render_chapters_section(chapters),
            ),
            
            # Modals and overlays (hidden by default, shown via HTMX)
            d.Div(id="edit-overlay", classes="hidden fixed inset-0 bg-black bg-opacity-50 z-40"),
            
            # Icon sidebar placeholder (loaded via HTMX when needed)
            d.Div(id="icon-sidebar-container")(),
            
            # Upload modal placeholder (loaded via HTMX when needed)
            d.Div(id="upload-modal-container")(),
            
            # JSON modal placeholder (loaded via HTMX when needed)
            d.Div(id="json-modal-container")(),
        )
    
    def _render_header(self, title: str, description: str, cover_url: str):
        """Render playlist header with cover and actions."""
        return d.Div(classes="px-6 py-8 sm:px-8 bg-gradient-to-r from-indigo-50 to-blue-50")(
            d.Div(classes="flex flex-col sm:flex-row gap-8")(
                # Cover Image
                d.Div(classes="flex-shrink-0")(
                    d.Img(src=cover_url, alt=title, classes="h-56 w-56 object-cover rounded-lg shadow-md border-2 border-gray-100")
                    if cover_url
                    else d.Div(classes="h-56 w-56 bg-gradient-to-br from-indigo-100 to-indigo-50 rounded-lg flex items-center justify-center text-6xl shadow-md border-2 border-gray-100")("🎵")
                ),
                # Title and Actions
                d.Div(classes="flex-1 flex flex-col justify-between")(
                    d.Div()(
                        d.H2(classes="text-3xl font-bold text-gray-900 mb-2")(title),
                        d.P(classes="text-base text-gray-600 leading-relaxed max-w-2xl")(description) if description else "",
                    ),
                    self._render_action_buttons(),
                ),
            ),
        )
    
    def _render_action_buttons(self):
        """Render action buttons for playlist operations."""
        return d.Div(classes="mt-6 flex flex-col sm:flex-row gap-3")(
            # Edit mode toggle - uses HTMX to load edit controls
            d.Button(
                id="edit-toggle-btn",
                classes="inline-flex items-center justify-center px-6 py-2 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 transition-colors",
                hx_get=f"/playlists/{self.card.cardId}/toggle-edit-mode?enable=true",
                hx_target="#edit-controls-container",
                hx_swap="innerHTML",
            )("✏️ Edit"),
            
            # Upload button - loads upload modal via HTMX
            d.Button(
                classes="inline-flex items-center justify-center px-6 py-2 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors",
                hx_get=f"/playlists/{self.card.cardId}/upload-modal",
                hx_target="#upload-modal-container",
                hx_swap="innerHTML",
                **{"hx-on::after-request": "removeClass('upload-modal-container', 'hidden')"}
            )("⬆️ Upload Items"),
            
            # Change cover - would load cover selection modal
            d.Button(
                classes="inline-flex items-center justify-center px-6 py-2 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors",
                hx_get=f"/playlists/{self.card.cardId}/cover-modal",
                hx_target="#body",
                hx_swap="beforeend",
            )("🖼️ Change Cover"),
            
            # Display JSON - loads JSON modal via HTMX
            d.Button(
                classes="inline-flex items-center justify-center px-6 py-2 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors",
                hx_get=f"/playlists/{self.card.cardId}/json-modal",
                hx_target="#json-modal-container",
                hx_swap="innerHTML",
            )("📋 Display JSON"),
        )
    
    def _render_chapters_section(self, chapters):
        """Render the chapters/items section."""
        return d.Div(classes="border-t border-gray-200")(
            d.Div(classes="px-6 py-6 sm:px-8")(
                d.Div(classes="flex justify-between items-center mb-3 flex-wrap gap-2")(
                    d.H3(classes="text-xl leading-6 font-bold text-gray-900")("Items"),
                    
                    # Tree controls - always visible
                    d.Div(classes="flex gap-2")(
                        d.Button(
                            classes="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors",
                            onclick="collapseAll()",
                            title="Collapse all chapters"
                        )("⊖ Collapse All"),
                        d.Button(
                            classes="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors",
                            onclick="expandAll()",
                            title="Expand all chapters"
                        )("⊕ Expand All"),
                    ),
                    
                    # Edit controls - loaded dynamically via HTMX when edit mode is enabled
                    d.Div(
                        id="edit-controls-container"
                    )(),
                ),
            ),
            
            # Chapters list - draggable via Sortable.js
            d.Ul(
                id="chapters-list",
                classes="divide-y divide-gray-100",
            )(
                *[ChapterItem(chapter=chapter, index=i, card_id=self.card.cardId) for i, chapter in enumerate(chapters)]
            ) if chapters else d.Div(classes="px-6 py-8 sm:px-8 text-center text-gray-500")("No items found."),
        )


class EditControlsPartial(Component):
    """Edit mode controls - shown when edit mode is active."""
    
    def __init__(self, playlist_id: str, edit_mode_active: bool = True):
        super().__init__()
        self.playlist_id = playlist_id
        self.edit_mode_active = edit_mode_active
    
    def render(self):
        if not self.edit_mode_active:
            # Return empty container when exiting edit mode
            return d.Div()()
        
        # Return controls + wrapper div that triggers script on render
        return d.Fragment()(
            d.Div(id="edit-controls-inner", classes="flex gap-2 flex-wrap")(
                # Select all - uses HTMX to update checkboxes client-side
                d.Button(
                    classes="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors",
                    type="button",
                    **{"hx-on:click": "document.querySelectorAll('#chapters-list input[type=checkbox]').forEach(cb => cb.checked = true)"},
                    title="Select all items"
                )("✓ Select All"),
                
                # Invert selection
                d.Button(
                    classes="px-3 py-1 text-sm bg-blue-400 text-white rounded hover:bg-blue-500 transition-colors",
                    type="button",
                    **{"hx-on:click": "document.querySelectorAll('#chapters-list input[type=checkbox]').forEach(cb => cb.checked = !cb.checked)"},
                    title="Invert selection"
                )("⟲ Invert"),
                
                # Delete selected
                d.Button(
                    classes="px-3 py-1 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition-colors",
                    hx_post=f"/playlists/{self.playlist_id}/delete-selected",
                    hx_confirm="Delete selected items?",
                    hx_include="[data-chapter-id]:checked",
                    hx_target="#chapters-list",
                    hx_swap="innerHTML",
                    title="Delete selected items"
                )("🗑️ Delete Selected"),
                
                # Batch edit icons - loads icon sidebar
                d.Button(
                    classes="px-3 py-1 text-sm bg-purple-500 text-white rounded hover:bg-purple-600 transition-colors",
                    hx_get=f"/playlists/{self.playlist_id}/icon-sidebar?batch=true",
                    hx_target="#icon-sidebar-container",
                    hx_swap="innerHTML",
                    **{"hx-on::after-request": "classList.remove(document.getElementById('edit-overlay'), 'hidden')"},
                    title="Edit icons for selected items"
                )("🎨 Edit Icons"),
                
                # Cancel button - exits edit mode
                d.Button(
                    classes="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors",
                    hx_get=f"/playlists/{self.playlist_id}/toggle-edit-mode?enable=false",
                    hx_target="#edit-controls-container",
                    hx_swap="innerHTML",
                    title="Cancel edit mode"
                )("❌ Cancel"),
            ),
            # Auto-show checkboxes with deferred script
            d.Script()(
                """
                // Show checkboxes after content is rendered
                document.querySelectorAll('#chapters-list input[type=checkbox]').forEach(cb => cb.classList.remove('hidden'));
                // Set up mutation observer to show new checkboxes if more content is added
                const list = document.getElementById('chapters-list');
                if (list) {
                    const observer = new MutationObserver(() => {
                        document.querySelectorAll('#chapters-list input[type=checkbox]').forEach(cb => cb.classList.remove('hidden'));
                    });
                    observer.observe(list, {childList: true, subtree: true});
                }
                """
            )
        )
