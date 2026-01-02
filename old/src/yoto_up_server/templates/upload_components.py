"""
Upload-related components for HTMX-driven file uploads.
"""

from pydom import Component
from pydom import html as d
from yoto_up_server.utils.alpine import xon


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
                            d.Label(
                                classes="block text-sm font-semibold text-gray-900"
                            )("📋 Pending Files"),
                            d.Div(
                                id="pending-files-list",
                                classes="max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-3 bg-gray-50",
                            )(
                                d.Div(classes="text-sm text-gray-500 text-center py-2")(
                                    "No files selected"
                                )
                            ),
                            d.Div(classes="flex gap-3")(
                                d.Button(
                                    type="button",
                                    classes="flex-1 px-4 py-3 border-2 border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium",
                                    onclick="selectFiles()",
                                )("📁 Select Files"),
                                d.Button(
                                    type="button",
                                    classes="flex-1 px-4 py-3 border-2 border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium",
                                    onclick="selectFolder()",
                                )("📂 Select Folder"),
                            ),
                            d.Input(
                                type="file",
                                id="file-input",
                                multiple=True,
                                classes="hidden",
                                accept="audio/*",
                                onchange="handleFileSelection()",
                            ),
                            d.Input(
                                type="file",
                                id="folder-input",
                                classes="hidden",
                                webkitdirectory="true",
                                mozdirectory="true",
                                onchange="handleFolderSelection()",
                            ),
                        ),
                        # Upload options
                        self._render_upload_options(),
                    ),
                    # Uploading state (hidden initially)
                    d.Div(id="uploading-state", classes="hidden px-6 py-6 space-y-6")(
                        d.H4(classes="text-lg font-semibold text-gray-900")(
                            "⬆️ Uploading..."
                        ),
                        d.Div(id="upload-progress-list", classes="space-y-3"),
                        d.Div(
                            id="upload-status",
                            classes="text-sm text-gray-600 text-center py-2",
                        )("Preparing upload..."),
                    ),
                ),
                # Footer
                d.Div(
                    classes="sticky bottom-0 px-6 py-4 border-t border-gray-200 bg-white flex justify-end gap-3"
                )(
                    d.Button(
                        type="button",
                        id="cancel-btn",
                        classes="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium",
                        onclick="closeUploadModal()",
                    )("Cancel"),
                    d.Button(
                        type="button",
                        id="start-upload-btn",
                        classes="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed",
                        onclick="startUpload()",
                        disabled=True,
                    )("⬆️ Start Upload"),
                ),
                # Upload management script
                d.Script()(
                    """//js
                // Upload state management
                window.uploadState = {
                    pendingFiles: [],
                    playlistId: '"""
                    + self.playlist_id
                    + """',
                    uploadSessionId: null,
                    uploadConfig: null
                };
                
                function closeUploadModal() {
                    const modal = document.getElementById('upload-modal');
                    if (modal) modal.remove();
                }
                
                function selectFiles() {
                    document.getElementById('file-input').click();
                }
                
                function selectFolder() {
                    document.getElementById('folder-input').click();
                }
                
                function handleFileSelection() {
                    const input = document.getElementById('file-input');
                    if (input.files && input.files.length > 0) {
                        const audioFiles = Array.from(input.files).filter(f => 
                            f.type.startsWith('audio/') || /\\.(mp3|m4a|wav|flac|ogg)$/i.test(f.name)
                        );
                        updatePendingFiles(audioFiles);
                    }
                    // Reset input so same file can be selected again
                    input.value = '';
                }
                
                function handleFolderSelection() {
                    const input = document.getElementById('folder-input');
                    if (input.files && input.files.length > 0) {
                        const audioFiles = Array.from(input.files).filter(f => 
                            f.type.startsWith('audio/') || /\\.(mp3|m4a|wav|flac|ogg)$/i.test(f.name)
                        );
                        updatePendingFiles(audioFiles);
                    }
                    input.value = '';
                }
                
                function updatePendingFiles(files) {
                    window.uploadState.pendingFiles = files;
                    
                    const list = document.getElementById('pending-files-list');
                    const btn = document.getElementById('start-upload-btn');
                    
                    if (files.length === 0) {
                        list.innerHTML = '<div class="text-sm text-gray-500 text-center py-2">No files selected</div>';
                        btn.disabled = true;
                        return;
                    }
                    
                    btn.disabled = false;
                    const html = files.map(file => {
                        const sizeMB = (file.size / 1024 / 1024).toFixed(2);
                        return `<div class="text-sm text-gray-700 py-1">📄 ${file.name} (${sizeMB} MB)</div>`;
                    }).join('');
                    list.innerHTML = html;
                }
                
                function getUploadConfig() {
                    const form = document.getElementById('upload-form');
                    const formData = new FormData(form);
                    
                    return {
                        upload_mode: formData.get('upload_mode') || 'chapters',
                        normalize: document.getElementById('normalize-checkbox')?.checked || false,
                        target_lufs: parseFloat(formData.get('target_lufs') || '-23.0'),
                        normalize_batch: document.getElementById('normalize_batch-checkbox')?.checked || false,
                        analyze_intro_outro: document.getElementById('analyze_intro_outro-checkbox')?.checked || false,
                        segment_seconds: parseFloat(formData.get('segment_seconds') || '10.0'),
                        similarity_threshold: parseFloat(formData.get('similarity_threshold') || '0.75'),
                        show_waveform: document.getElementById('show_waveform-checkbox')?.checked || false
                    };
                }
                
                async function startUpload() {
                    if (window.uploadState.pendingFiles.length === 0) {
                        alert('Please select files first');
                        return;
                    }
                    
                    try {
                        // Disable buttons
                        document.getElementById('start-upload-btn').disabled = true;
                        document.getElementById('cancel-btn').disabled = true;
                        
                        // Collect upload configuration
                        window.uploadState.uploadConfig = getUploadConfig();
                        
                        // Create upload session with config
                        console.log('Creating upload session with config:', window.uploadState.uploadConfig);
                        const sessionResponse = await fetch(
                            `/playlists/${window.uploadState.playlistId}/upload-session`,
                            {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify(window.uploadState.uploadConfig)
                            }
                        );
                        
                        if (!sessionResponse.ok) {
                            throw new Error('Failed to create upload session');
                        }
                        
                        const sessionData = await sessionResponse.json();
                        window.uploadState.uploadSessionId = sessionData.session_id;
                        console.log('Upload session created:', window.uploadState.uploadSessionId);
                        
                        // Close modal immediately
                        closeUploadModal();
                        
                        // Upload files in background (don't await)
                        uploadFilesInBackground(window.uploadState.pendingFiles, window.uploadState.uploadSessionId);
                        
                    } catch (error) {
                        console.error('Upload error:', error);
                        alert('Upload failed: ' + error.message);
                        // Re-enable buttons
                        document.getElementById('start-upload-btn').disabled = false;
                        document.getElementById('cancel-btn').disabled = false;
                    }
                }
                
                async function uploadFilesInBackground(files, sessionId) {
                    // Upload files sequentially in the background
                    for (let i = 0; i < files.length; i++) {
                        const file = files[i];
                        
                        try {
                            await uploadSingleFile(file, sessionId);
                            console.log(`Uploaded ${file.name} to session ${sessionId}`);
                        } catch (error) {
                            console.error(`Failed to upload ${file.name}:`, error);
                        }
                    }
                }
                
                async function uploadSingleFile(file, sessionId) {
                    const fileFormData = new FormData();
                    fileFormData.append('file', file);
                    
                    const response = await fetch(
                        `/playlists/${window.uploadState.playlistId}/upload-session/${sessionId}/files`,
                        {
                            method: 'POST',
                            body: fileFormData
                        }
                    );
                    
                    if (!response.ok) {
                        const error = await response.text();
                        throw new Error(`HTTP ${response.status}: ${error}`);
                    }
                }
                
                async function uploadFilesSequentially() {
                    const files = window.uploadState.pendingFiles;
                    const progressList = document.getElementById('upload-progress-list');
                    progressList.innerHTML = '';
                    
                    for (let i = 0; i < files.length; i++) {
                        const file = files[i];
                        
                        // Create progress item
                        const progressId = `progress-${i}`;
                        const progressHtml = `
                            <div class="border border-gray-200 rounded p-3 bg-gray-50">
                                <div class="flex justify-between items-start mb-2">
                                    <span class="text-sm font-medium text-gray-900">📄 ${file.name}</span>
                                    <span class="text-xs text-gray-500">${(file.size / 1024 / 1024).toFixed(2)} MB</span>
                                </div>
                                <div id="${progressId}" class="w-full bg-gray-200 rounded-full h-2">
                                    <div class="bg-indigo-600 h-2 rounded-full" style="width: 0%"></div>
                                </div>
                            </div>
                        `;
                        progressList.insertAdjacentHTML('beforeend', progressHtml);
                        
                        // Upload file
                        try {
                            await uploadSingleFile(file, i);
                            // Update progress bar to 100%
                            const progressBar = document.querySelector(`#${progressId} div`);
                            if (progressBar) progressBar.style.width = '100%';
                        } catch (error) {
                            console.error(`Failed to upload ${file.name}:`, error);
                            // Show error in progress item
                            const progressItem = document.getElementById(progressId).parentElement;
                            progressItem.innerHTML += `<div class="text-xs text-red-600 mt-1">❌ Upload failed: ${error.message}</div>`;
                        }
                        
                        // Update status
                        document.getElementById('upload-status').textContent = 
                            `Uploaded ${i + 1} of ${files.length} files...`;
                    }
                }
                
                async function pollForCompletion() {
                    const maxAttempts = 120; // 2 minutes with 1-second intervals
                    let attempts = 0;
                    
                    while (attempts < maxAttempts) {
                        try {
                            const statusResponse = await fetch(
                                `/playlists/${window.uploadState.playlistId}/upload-session/${window.uploadState.uploadSessionId}/status`
                            );
                            
                            if (!statusResponse.ok) break;
                            
                            const status = await statusResponse.json();
                            const statusEl = document.getElementById('upload-status');
                            
                            if (status.is_complete) {
                                statusEl.innerHTML = '✅ Upload complete! Refreshing playlist...';
                                
                                // Wait a moment then close modal and refresh
                                setTimeout(() => {
                                    closeUploadModal();
                                    // Refresh the playlist page
                                    location.reload();
                                }, 1000);
                                return;
                            } else {
                                statusEl.textContent = `Processing... ${status.processed_count} of ${status.total_count} files`;
                            }
                        } catch (error) {
                            console.warn('Poll error:', error);
                        }
                        
                        // Wait 1 second before next poll
                        await new Promise(resolve => setTimeout(resolve, 1000));
                        attempts++;
                    }
                    
                    // Timeout or error - still reload
                    document.getElementById('upload-status').innerHTML = '⏱️ Processing may continue in background. Refreshing playlist...';
                    setTimeout(() => {
                        closeUploadModal();
                        location.reload();
                    }, 2000);
                }
                """
                ),
            ),
        )

    def _render_upload_options(self):
        """Render upload configuration options."""
        return d.Form(id="upload-form", classes="space-y-4")(
            # Upload mode
            d.Div(classes="space-y-2")(
                d.Label(classes="block text-sm font-semibold text-gray-900")(
                    "Upload As"
                ),
                d.Div(classes="flex gap-4")(
                    d.Label(classes="flex items-center cursor-pointer")(
                        d.Input(
                            type="radio",
                            name="upload_mode",
                            value="chapters",
                            checked=True,
                            classes="w-4 h-4 accent-indigo-600",
                        ),
                        d.Span(classes="ml-2 text-sm text-gray-700")("Chapters"),
                    ),
                    d.Label(classes="flex items-center cursor-pointer")(
                        d.Input(
                            type="radio",
                            name="upload_mode",
                            value="tracks",
                            classes="w-4 h-4 accent-indigo-600",
                        ),
                        d.Span(classes="ml-2 text-sm text-gray-700")("Tracks"),
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
                    d.Span(classes="text-sm font-semibold text-gray-900")(
                        "Normalize Audio"
                    ),
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
                        d.Span(classes="text-sm text-gray-700")(
                            "Batch mode (Album normalization)"
                        ),
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
                    d.Span(classes="text-sm font-semibold text-gray-900")(
                        "Analyze Intro/Outro"
                    ),
                ),
                d.Div(id="analysis-options", classes="hidden space-y-3 pl-6")(
                    d.Div(classes="space-y-2")(
                        d.Label(classes="block text-sm text-gray-700")(
                            "Segment Seconds"
                        ),
                        d.Input(
                            type="number",
                            name="segment_seconds",
                            value="10.0",
                            step="0.5",
                            classes="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500",
                        ),
                    ),
                    d.Div(classes="space-y-2")(
                        d.Label(classes="block text-sm text-gray-700")(
                            "Similarity Threshold"
                        ),
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
            d.H3(classes="text-lg font-semibold text-gray-900 mb-4")(
                "⬆️ Active Uploads"
            ),
            d.Div(id="uploads-list", classes="space-y-4"),
            # Script to manage active uploads
            d.Script()(
                r"""//js
            // Poll for active upload sessions
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
            
            function updateSessionDisplay(session) {
                let sessionEl = document.getElementById(`upload-${session.session_id}`);
                
                if (!sessionEl) {
                    // Create new session display
                    sessionEl = document.createElement('div');
                    sessionEl.id = `upload-${session.session_id}`;
                    sessionEl.className = 'border border-blue-200 rounded-lg p-4 bg-white';
                    document.getElementById('uploads-list').appendChild(sessionEl);
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
                    <div class="space-y-1 text-sm">
                        ${filesHtml}
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
                    d.H3(classes="text-2xl font-bold text-gray-900")(
                        "Create New Playlist"
                    ),
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
                            d.Label(
                                classes="block text-sm font-semibold text-gray-900 mb-2"
                            )("Cover Image (Optional)"),
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
                            d.Div(
                                id="cover-url-input-container", classes="hidden mt-3"
                            )(
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
                    d.Div(
                        classes="px-6 py-4 border-t border-gray-200 flex justify-end gap-3"
                    )(
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
                            **xon().click.prevent(
                                "document.getElementById('json-modal').remove()"
                            ),
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
