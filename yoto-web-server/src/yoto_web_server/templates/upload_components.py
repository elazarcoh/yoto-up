"""
Upload-related components for HTMX-driven file uploads.
"""

from pydom import Component
from pydom import html as d

from yoto_web_server.utils.alpine import xon


class UploadModalPartial(Component):
    """Server-rendered upload modal - JavaScript-based with File System API."""

    def __init__(self, *, playlist_id: str):
        super().__init__()
        self.playlist_id = playlist_id

    def render(self):
        return d.Div(
            id="upload-modal",
            classes="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4",
        )(
            d.Div(
                classes="bg-white rounded-lg shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto flex flex-col"
            )(
                # Header
                d.Div(
                    classes="sticky top-0 px-6 py-4 border-b border-gray-200 bg-white flex justify-between items-center"
                )(
                    d.H3(classes="text-2xl font-bold text-gray-900")("Upload Files"),
                    d.Button(
                        type="button",
                        classes="text-gray-500 hover:text-gray-700 text-2xl",
                        onclick="closeUploadModal()",
                    )("✕"),
                ),
                # Main content area - two states: selection and uploading
                d.Div(classes="flex-1 overflow-y-auto")(
                    # Selection state
                    d.Div(id="selection-state", classes="px-6 py-6 space-y-6")(
                        # Pending Files Section
                        d.Div(classes="space-y-3")(
                            d.Label(classes="block text-sm font-semibold text-gray-900")(
                                "📋 Pending Files"
                            ),
                            d.Div(
                                id="pending-files-list",
                                classes="max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-3 bg-gray-50",
                            )(
                                d.Div(classes="text-sm text-gray-500 text-center py-2")(
                                    "No files selected"
                                )
                            ),
                        ),
                        # File/Folder selection buttons
                        d.Div(classes="flex gap-3")(
                            d.Button(
                                type="button",
                                id="select-files-btn",
                                classes="flex-1 px-4 py-3 border-2 border-dashed border-indigo-300 rounded-lg hover:border-indigo-500 hover:bg-indigo-50 transition-colors text-center",
                            )(
                                d.Div(classes="text-3xl mb-1")("📄"),
                                d.Div(classes="text-sm font-medium text-gray-700")("Select Files"),
                            ),
                            d.Button(
                                type="button",
                                id="select-folder-btn",
                                classes="flex-1 px-4 py-3 border-2 border-dashed border-indigo-300 rounded-lg hover:border-indigo-500 hover:bg-indigo-50 transition-colors text-center",
                            )(
                                d.Div(classes="text-3xl mb-1")("📁"),
                                d.Div(classes="text-sm font-medium text-gray-700")("Select Folder"),
                            ),
                        ),
                        # Upload options
                        self._render_upload_options(),
                    ),
                    # Uploading state (hidden by default)
                    d.Div(id="uploading-state", classes="hidden px-6 py-6")(
                        d.Div(classes="text-center")(
                            d.Div(classes="animate-spin text-4xl mb-4")("⏳"),
                            d.P(id="upload-status-text", classes="text-lg font-medium")(
                                "Uploading..."
                            ),
                            d.Div(classes="w-full bg-gray-200 rounded-full h-3 mt-4")(
                                d.Div(
                                    id="upload-progress-bar",
                                    classes="bg-indigo-600 h-3 rounded-full transition-all",
                                    style="width: 0%",
                                )()
                            ),
                            d.P(
                                id="upload-progress-text",
                                classes="text-sm text-gray-600 mt-2",
                            )("0 of 0 files"),
                        ),
                        d.Div(
                            id="upload-results",
                            classes="mt-6 space-y-2 max-h-40 overflow-y-auto",
                        )(),
                    ),
                ),
                # Footer
                d.Div(
                    classes="sticky bottom-0 px-6 py-4 border-t border-gray-200 bg-white flex justify-end gap-3"
                )(
                    d.Button(
                        type="button",
                        classes="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium",
                        onclick="closeUploadModal()",
                    )("Cancel"),
                    d.Button(
                        type="button",
                        id="start-upload-btn",
                        classes="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed",
                        disabled=True,
                    )("⬆️ Start Upload"),
                ),
            ),
            # Upload JavaScript
            d.Script()(
                r"""//js
            const pendingFiles = [];
            let currentPlaylistId = '"""
                + self.playlist_id
                + r"""';
            
            function closeUploadModal() {
                const modal = document.getElementById('upload-modal');
                if (modal) modal.remove();
            }
            
            // File selection using File System Access API
            document.getElementById('select-files-btn')?.addEventListener('click', async () => {
                try {
                    // Use File System Access API if available
                    if ('showOpenFilePicker' in window) {
                        const fileHandles = await window.showOpenFilePicker({
                            multiple: true,
                            types: [{ description: 'Audio files', accept: { 'audio/*': ['.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac', '.m4b'] } }]
                        });
                        for (const handle of fileHandles) {
                            const file = await handle.getFile();
                            addFileToPending(file);
                        }
                    } else {
                        // Fallback to input element
                        const input = document.createElement('input');
                        input.type = 'file';
                        input.multiple = true;
                        input.accept = 'audio/*';
                        input.onchange = (e) => {
                            for (const file of e.target.files) {
                                addFileToPending(file);
                            }
                        };
                        input.click();
                    }
                } catch (err) {
                    if (err.name !== 'AbortError') console.error('File selection error:', err);
                }
            });
            
            // Folder selection
            document.getElementById('select-folder-btn')?.addEventListener('click', async () => {
                try {
                    if ('showDirectoryPicker' in window) {
                        const dirHandle = await window.showDirectoryPicker();
                        await processDirectory(dirHandle);
                    } else {
                        // Fallback
                        const input = document.createElement('input');
                        input.type = 'file';
                        input.webkitdirectory = true;
                        input.onchange = (e) => {
                            for (const file of e.target.files) {
                                if (file.type.startsWith('audio/') || /\.(mp3|m4a|wav|flac|ogg|aac|m4b)$/i.test(file.name)) {
                                    addFileToPending(file);
                                }
                            }
                        };
                        input.click();
                    }
                } catch (err) {
                    if (err.name !== 'AbortError') console.error('Folder selection error:', err);
                }
            });
            
            async function processDirectory(dirHandle, path = '') {
                for await (const entry of dirHandle.values()) {
                    if (entry.kind === 'file') {
                        const file = await entry.getFile();
                        if (file.type.startsWith('audio/') || /\.(mp3|m4a|wav|flac|ogg|aac|m4b)$/i.test(file.name)) {
                            addFileToPending(file, path);
                        }
                    } else if (entry.kind === 'directory') {
                        await processDirectory(entry, path ? `${path}/${entry.name}` : entry.name);
                    }
                }
            }
            
            function addFileToPending(file, path = '') {
                // Check for duplicates
                const exists = pendingFiles.some(f => f.name === file.name && f.size === file.size);
                if (!exists) {
                    pendingFiles.push({ file, path, name: file.name, size: file.size });
                    updatePendingFilesList();
                }
            }
            
            function removeFromPending(index) {
                pendingFiles.splice(index, 1);
                updatePendingFilesList();
            }
            
            function updatePendingFilesList() {
                const list = document.getElementById('pending-files-list');
                const uploadBtn = document.getElementById('start-upload-btn');
                
                if (pendingFiles.length === 0) {
                    list.innerHTML = '<div class="text-sm text-gray-500 text-center py-2">No files selected</div>';
                    uploadBtn.disabled = true;
                    return;
                }
                
                uploadBtn.disabled = false;
                list.innerHTML = pendingFiles.map((f, i) => `
                    <div class="flex items-center justify-between py-1 border-b border-gray-100 last:border-0">
                        <span class="text-sm text-gray-800">📄 ${f.path ? f.path + '/' : ''}${f.name}</span>
                        <button type="button" class="text-red-500 hover:text-red-700 text-sm" onclick="removeFromPending(${i})">✕</button>
                    </div>
                `).join('');
            }
            
            // Start upload
            document.getElementById('start-upload-btn')?.addEventListener('click', async () => {
                if (pendingFiles.length === 0) return;
                
                // Get options
                const uploadMode = document.querySelector('input[name="upload_mode"]:checked')?.value || 'chapters';
                const normalize = document.getElementById('normalize-checkbox')?.checked || false;
                const targetLufs = parseFloat(document.querySelector('input[name="target_lufs"]')?.value || '-23.0');
                const normalizeBatch = document.getElementById('normalize_batch-checkbox')?.checked || false;
                const analyzeIntroOutro = document.getElementById('analyze_intro_outro-checkbox')?.checked || false;
                const segmentSeconds = parseFloat(document.querySelector('input[name="segment_seconds"]')?.value || '10.0');
                const similarityThreshold = parseFloat(document.querySelector('input[name="similarity_threshold"]')?.value || '0.75');
                const showWaveform = document.getElementById('show_waveform-checkbox')?.checked || false;
                
                // Switch to uploading state
                document.getElementById('selection-state').classList.add('hidden');
                document.getElementById('uploading-state').classList.remove('hidden');
                
                // Create upload session
                const sessionResponse = await fetch(`/playlists/${currentPlaylistId}/upload-session`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        upload_mode: uploadMode,
                        normalize: normalize,
                        target_lufs: targetLufs,
                        normalize_batch: normalizeBatch,
                        analyze_intro_outro: analyzeIntroOutro,
                        segment_seconds: segmentSeconds,
                        similarity_threshold: similarityThreshold,
                        show_waveform: showWaveform,
                        files: pendingFiles.map(f => ({ filename: f.name, size: f.size, path: f.path }))
                    })
                });
                
                if (!sessionResponse.ok) {
                    alert('Failed to create upload session');
                    return;
                }
                
                const session = await sessionResponse.json();
                const sessionId = session.session_id;
                
                // Upload files sequentially
                const results = document.getElementById('upload-results');
                const totalFiles = pendingFiles.length;
                
                for (let i = 0; i < pendingFiles.length; i++) {
                    const { file, name } = pendingFiles[i];
                    
                    // Update progress
                    document.getElementById('upload-status-text').textContent = `Uploading ${name}...`;
                    document.getElementById('upload-progress-text').textContent = `${i + 1} of ${totalFiles} files`;
                    document.getElementById('upload-progress-bar').style.width = `${((i) / totalFiles) * 100}%`;
                    
                    try {
                        const formData = new FormData();
                        formData.append('file', file);
                        
                        const uploadResponse = await fetch(`/playlists/${currentPlaylistId}/upload-session/${sessionId}/files`, {
                            method: 'POST',
                            body: formData
                        });
                        
                        if (uploadResponse.ok) {
                            results.innerHTML += `<div class="text-sm text-green-600">✅ ${name}</div>`;
                        } else {
                            results.innerHTML += `<div class="text-sm text-red-600">❌ ${name} - Upload failed</div>`;
                        }
                    } catch (err) {
                        results.innerHTML += `<div class="text-sm text-red-600">❌ ${name} - ${err.message}</div>`;
                    }
                }
                
                // Complete
                document.getElementById('upload-progress-bar').style.width = '100%';
                document.getElementById('upload-status-text').textContent = 'Upload complete! Processing in background...';
                
                // Close modal after delay and refresh
                setTimeout(() => {
                    closeUploadModal();
                    htmx.ajax('GET', `/playlists/${currentPlaylistId}`, { target: '#main-content', swap: 'innerHTML' });
                }, 2000);
            });
            """
            ),
        )

    def _render_upload_options(self):
        """Render the upload options form."""
        return d.Div(classes="space-y-4")(
            # Upload mode
            d.Div(classes="space-y-3 p-4 bg-gray-50 rounded-lg border border-gray-200")(
                d.Label(classes="block text-sm font-semibold text-gray-900 mb-2")("Upload Mode"),
                d.Div(classes="flex gap-4")(
                    d.Label(classes="flex items-center gap-2 cursor-pointer")(
                        d.Input(
                            type="radio",
                            name="upload_mode",
                            value="chapters",
                            checked=True,
                            classes="w-4 h-4 accent-indigo-600",
                        ),
                        d.Span(classes="text-sm text-gray-700")(
                            "Chapters (one track, multiple chapters)"
                        ),
                    ),
                    d.Label(classes="flex items-center gap-2 cursor-pointer")(
                        d.Input(
                            type="radio",
                            name="upload_mode",
                            value="tracks",
                            classes="w-4 h-4 accent-indigo-600",
                        ),
                        d.Span(classes="text-sm text-gray-700")("Tracks (multiple tracks)"),
                    ),
                ),
            ),
            # Normalization
            d.Div(classes="space-y-3 p-4 bg-gray-50 rounded-lg border border-gray-200")(
                d.Label(classes="flex items-center cursor-pointer gap-2")(
                    d.Input(
                        type="checkbox",
                        id="normalize-checkbox",
                        name="normalize",
                        value="true",
                        classes="w-4 h-4 accent-indigo-600",
                        onchange="document.getElementById('normalize-options').classList.toggle('hidden')",
                    ),
                    d.Span(classes="text-sm font-semibold text-gray-900")("Normalize Audio"),
                ),
                d.Div(id="normalize-options", classes="hidden space-y-3 pl-6")(
                    d.Div(classes="space-y-2")(
                        d.Label(classes="block text-sm text-gray-700")("Target LUFS"),
                        d.Input(
                            type="number",
                            name="target_lufs",
                            value="-23.0",
                            step="0.1",
                            classes="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500",
                        ),
                    ),
                    d.Label(classes="flex items-center cursor-pointer gap-2")(
                        d.Input(
                            type="checkbox",
                            id="normalize_batch-checkbox",
                            name="normalize_batch",
                            value="true",
                            classes="w-4 h-4 accent-indigo-600",
                        ),
                        d.Span(classes="text-sm text-gray-700")("Batch mode (Album normalization)"),
                    ),
                ),
            ),
            # Analysis
            d.Div(classes="space-y-3 p-4 bg-gray-50 rounded-lg border border-gray-200")(
                d.Label(classes="flex items-center cursor-pointer gap-2")(
                    d.Input(
                        type="checkbox",
                        id="analyze_intro_outro-checkbox",
                        name="analyze_intro_outro",
                        value="true",
                        classes="w-4 h-4 accent-indigo-600",
                        onchange="document.getElementById('analysis-options').classList.toggle('hidden')",
                    ),
                    d.Span(classes="text-sm font-semibold text-gray-900")("Analyze Intro/Outro"),
                ),
                d.Div(id="analysis-options", classes="hidden space-y-3 pl-6")(
                    d.Div(classes="space-y-2")(
                        d.Label(classes="block text-sm text-gray-700")("Segment Seconds"),
                        d.Input(
                            type="number",
                            name="segment_seconds",
                            value="10.0",
                            step="0.5",
                            classes="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500",
                        ),
                    ),
                    d.Div(classes="space-y-2")(
                        d.Label(classes="block text-sm text-gray-700")("Similarity Threshold"),
                        d.Input(
                            type="number",
                            name="similarity_threshold",
                            value="0.75",
                            step="0.05",
                            min="0",
                            max="1",
                            classes="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500",
                        ),
                    ),
                ),
            ),
            # Waveform
            d.Label(
                classes="flex items-center cursor-pointer gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200"
            )(
                d.Input(
                    type="checkbox",
                    id="show_waveform-checkbox",
                    name="show_waveform",
                    value="true",
                    classes="w-4 h-4 accent-indigo-600",
                ),
                d.Span(classes="text-sm font-semibold text-gray-900")(
                    "Show waveform visualization"
                ),
            ),
        )


class UploadProgressPartial(Component):
    """Server-rendered upload progress display - polls session status."""

    def __init__(self, *, session_id: str, playlist_id: str):
        super().__init__()
        self.session_id = session_id
        self.playlist_id = playlist_id

    def render(self):
        return d.Div(
            id=f"upload-session-{self.session_id}",
            classes="border-l-4 border-blue-500 bg-blue-50 p-4 rounded-lg",
            hx_get=f"/playlists/{self.playlist_id}/upload-session/{self.session_id}/status",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
        )(
            d.Div(classes="flex justify-between items-start gap-4")(
                d.Div(classes="flex-1")(
                    d.P(classes="font-medium text-gray-900")("Uploading..."),
                ),
            ),
        )


class ActiveUploadsSection(Component):
    """Component for displaying active uploads on the playlist page."""

    def __init__(self, *, playlist_id: str):
        super().__init__()
        self.playlist_id = playlist_id

    def render(self):
        return d.Div(
            id="active-uploads-container",
            classes="border-t border-gray-200 px-6 py-6 bg-gray-50",
        )(
            d.H3(classes="text-lg font-semibold text-gray-900 mb-4")("⬆️ Active Uploads"),
            d.Div(id="uploads-list", classes="space-y-4"),
            # Script to manage active uploads
            d.Script()(
                r"""//js
            // Poll for active upload sessions
            const handledSessions = new Set();

            async function pollActiveUploads() {
                try {
                    const response = await fetch(`/playlists/"""
                + self.playlist_id
                + r"""/upload-sessions`);
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
                    const response = await fetch(`/playlists/"""
                + self.playlist_id
                + r"""/upload-session/${sessionId}`, {
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
                    const response = await fetch(`/playlists/"""
                + self.playlist_id
                + r"""/upload-session/${sessionId}/stop`, {
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
                    // Create new session display
                    sessionEl = document.createElement('div');
                    sessionEl.id = `upload-${session.session_id}`;
                    sessionEl.className = 'border border-blue-200 rounded-lg p-4 bg-white';
                    document.getElementById('uploads-list').appendChild(sessionEl);
                }

                const isDone = session.overall_status === 'done';
                
                if (isDone && !handledSessions.has(session.session_id)) {
                    handledSessions.add(session.session_id);
                    
                    // Check for new chapters
                    if (session.new_chapter_ids && session.new_chapter_ids.length > 0) {
                        const newChapters = session.new_chapter_ids.join(',');
                        // Reload playlist detail with new chapters highlighted
                        htmx.ajax('GET', `/playlists/${session.playlist_id}?new_chapters=${newChapters}`, {
                            target: '#playlist-detail',
                            swap: 'outerHTML'
                        });
                    }
                }
                
                // Build file list with states
                const filesHtml = (session.files || []).map(file => {
                    let stateIcon = '⏳';
                    let stateColor = 'text-gray-600';
                    let stateLabel = file.status || 'pending';
                    
                    // Map status enum to icons and colors
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
                        stateColor = 'text-gray-600';
                    } else if (file.status === 'uploading') {
                        stateIcon = '⬆️';
                        stateColor = 'text-blue-600';
                    } else if (file.status === 'pending') {
                        stateIcon = '⏳';
                        stateColor = 'text-gray-500';
                    }
                    
                    return `<div class="flex items-center justify-between py-2">
                        <span class="text-sm text-gray-800">📄 ${file.filename}</span>
                        <span class="${stateColor} text-sm font-medium">${stateIcon} ${stateLabel.replace('_', ' ')}</span>
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
                            <span class="font-medium text-gray-900">Session ${session.session_id.substring(0, 8)}</span>
                            <span class="text-sm text-gray-600">${doneFiles}/${totalFiles}</span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-2">
                            <div class="bg-blue-600 h-2 rounded-full transition-all" style="width: ${progress}%"></div>
                        </div>
                    </div>
                    <div class="space-y-1 text-sm mb-3">
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
            """
            ),
        )


class NewPlaylistModalPartial(Component):
    """Modal dialog for creating a new playlist."""

    def render(self):
        return d.Div(
            id="new-playlist-modal",
            classes="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4",
            # **{"hx-on:keydown.escape": "closeNewPlaylistModal()"},
            **xon().keydown.escape("closeNewPlaylistModal()"),
        )(
            d.Div(classes="bg-white rounded-lg shadow-2xl max-w-md w-full")(
                # Header
                d.Div(
                    classes="px-6 py-4 border-b border-gray-200 flex justify-between items-center"
                )(
                    d.H3(classes="text-2xl font-bold text-gray-900")("Create New Playlist"),
                    d.Button(
                        classes="text-gray-500 hover:text-gray-700 text-2xl bg-none border-none cursor-pointer",
                        type="button",
                        **xon().click("closeNewPlaylistModal()"),
                    )("✕"),
                ),
                # Form
                d.Form(
                    id="new-playlist-form",
                    hx_post="/playlists/create-with-cover",
                    hx_target="#playlist-list",
                    hx_swap="innerHTML",
                    hx_on_htmx_after_request="if(event.detail.successful) { closeNewPlaylistModal(); }",
                    classes="space-y-4",
                )(
                    # Content
                    d.Div(classes="px-6 py-6 space-y-5")(
                        # Title field
                        d.Div(classes="flex flex-col")(
                            d.Label(
                                html_for="playlist-title",
                                classes="block text-sm font-semibold text-gray-900 mb-2",
                            )("Playlist Title"),
                            d.Input(
                                type="text",
                                id="playlist-title",
                                name="title",
                                placeholder="e.g., My Stories",
                                required=True,
                                classes="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition",
                            ),
                        ),
                        # Cover image section
                        d.Div(classes="flex flex-col")(
                            d.Label(classes="block text-sm font-semibold text-gray-900 mb-2")(
                                "Cover Image (Optional)"
                            ),
                            # Cover preview
                            d.Div(
                                id="cover-preview",
                                classes="w-full h-40 bg-gray-100 rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center mb-3 text-gray-400",
                            )(
                                d.Div(classes="text-center")(
                                    d.Div(classes="text-2xl mb-2")("🖼️"),
                                    d.Div(classes="text-sm")("No image selected"),
                                )
                            ),
                            # Upload options
                            d.Div(classes="flex gap-2")(
                                d.Button(
                                    type="button",
                                    classes="flex-1 px-4 py-2 border border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium text-sm",
                                    onclick="document.getElementById('cover-file-input').click()",
                                )("📁 Upload File"),
                                d.Button(
                                    type="button",
                                    classes="flex-1 px-4 py-2 border border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium text-sm",
                                    onclick="showCoverUrlInput()",
                                )("🔗 Use URL"),
                            ),
                            # File input (hidden)
                            d.Input(
                                type="file",
                                id="cover-file-input",
                                name="cover_file",
                                accept="image/*",
                                classes="hidden",
                                **{"hx-on:change": "handleCoverFileSelected(event)"},
                            ),
                            # URL input (hidden by default)
                            d.Div(id="cover-url-input-container", classes="hidden mt-3")(
                                d.Input(
                                    type="url",
                                    id="cover-url-input",
                                    name="cover_url",
                                    placeholder="https://example.com/image.jpg",
                                    classes="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition",
                                ),
                            ),
                        ),
                    ),
                    # Footer
                    d.Div(classes="px-6 py-4 border-t border-gray-200 flex justify-end gap-3")(
                        d.Button(
                            type="button",
                            classes="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium",
                            **xon().click("closeNewPlaylistModal()"),
                        )("Cancel"),
                        d.Button(
                            type="submit",
                            classes="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium",
                        )("✨ Create Playlist"),
                    ),
                ),
            ),
            # Helper scripts
            d.Script()("""//js
                function closeNewPlaylistModal() {
                    const modal = document.getElementById('new-playlist-modal');
                    if (modal) modal.remove();
                }
                
                function showCoverUrlInput() {
                    const container = document.getElementById('cover-url-input-container');
                    container.classList.toggle('hidden');
                    if (!container.classList.contains('hidden')) {
                        document.getElementById('cover-url-input').focus();
                    }
                }
                
                function handleCoverFileSelected(event) {
                    const file = event.target.files?.[0];
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = (e) => {
                            const preview = document.getElementById('cover-preview');
                            preview.innerHTML = `<img src="${e.target.result}" alt="Cover preview" class="w-full h-full object-cover rounded-lg" />`;
                        };
                        reader.readAsDataURL(file);
                    }
                }
            """),
        )


class JsonDisplayModalPartial(Component):
    """Server-rendered JSON display modal."""

    def __init__(self, *, json_data: str):
        super().__init__()
        self.json_data = json_data

    def render(self):
        return d.Div(
            id="json-modal",
            classes="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4",
        )(
            d.Div(
                classes="bg-white rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto"
            )(
                # Header
                d.Div(
                    classes="sticky top-0 px-6 py-4 border-b border-gray-200 bg-white flex justify-between items-center"
                )(
                    d.H3(classes="text-2xl font-bold text-gray-900")("Playlist JSON"),
                    d.Div(classes="flex gap-2")(
                        d.Button(
                            classes="px-3 py-1 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium",
                            onclick="copyToClipboard_json_content()",
                        )("📋 Copy"),
                        d.Button(
                            classes="text-gray-500 hover:text-gray-700 text-2xl",
                            **xon().click.prevent("document.getElementById('json-modal').remove()"),
                        )("✕"),
                    ),
                ),
                # Content
                d.Div(classes="px-6 py-6")(
                    d.Pre(
                        id="json_content",
                        classes="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm font-mono max-h-[70vh] overflow-y-auto",
                    )(d.Code()(self.json_data)),
                ),
            )
        )
