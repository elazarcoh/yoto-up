"""
Upload-related components for HTMX-driven file uploads.
"""


from pydom import Component
from pydom import html as d


class UploadModalPartial(Component):
    """Server-rendered upload modal - uses new session-based upload."""
    
    def __init__(self, playlist_id: str):
        super().__init__()
        self.playlist_id = playlist_id
    
    def render(self):
        return d.Div(
            id="upload-modal",
            classes="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
        )(
            d.Div(classes="bg-white rounded-lg shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto")(
                # Header
                d.Div(classes="sticky top-0 px-6 py-4 border-b border-gray-200 bg-white flex justify-between items-center")(
                    d.H3(classes="text-2xl font-bold text-gray-900")("Upload Files"),
                    d.Button(
                        classes="text-gray-500 hover:text-gray-700 text-2xl",
                        **{"hx-on:click": "closeUploadModal()"}
                    )("✕"),
                ),
                
                # Upload form
                d.Form(
                    id="upload-form",
                    classes="space-y-4",
                    **{"hx-on:submit": "handleUploadSubmit(event)"}
                )(
                    d.Div(classes="px-6 py-6 space-y-6")(
                        # File selection
                        d.Div(classes="space-y-3")(
                            d.Label(classes="block text-sm font-semibold text-gray-900")("Select Files"),
                            d.Div(classes="flex gap-3")(
                                d.Button(
                                    type="button",
                                    classes="flex-1 px-4 py-3 border-2 border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium",
                                    onclick="triggerFilePicker('file-input')"
                                )("📁 Select Files"),
                                d.Button(
                                    type="button",
                                    classes="flex-1 px-4 py-3 border-2 border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium",
                                    onclick="triggerFolderPicker('file-input')"
                                )("📂 Select Folder"),
                            ),
                            d.Input(
                                type="file",
                                id="file-input",
                                name="files",
                                multiple=True,
                                classes="hidden",
                                accept="audio/*",
                                **{"hx-on:change": "updateFilePreview()"}
                            ),
                        ),
                        
                        # File preview
                        d.Div(
                            id="file-preview",
                            classes="max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-3 bg-gray-50"
                        )(
                            d.Div(classes="text-sm text-gray-500 text-center py-2")("No files selected")
                        ),
                        
                        # Upload options
                        self._render_upload_options(),
                    ),
                    
                    # Footer
                    d.Div(classes="sticky bottom-0 px-6 py-4 border-t border-gray-200 bg-white flex justify-end gap-3")(
                        d.Button(
                            type="button",
                            classes="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium",
                            **{"hx-on:click": "closeUploadModal()"}
                        )("Cancel"),
                        d.Button(
                            type="button",
                            id="start-upload-btn",
                            classes="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed",
                            **{"hx-on:click": "handleUploadSubmit(event)"}
                        )("⬆️ Start Upload"),
                    ),
                ),
                
                # Helper scripts
                d.Script()("""//js
                    window.uploadSessionId = null;
                    window.playlistId = '""" + self.playlist_id + """';
                    
                    function closeUploadModal() {
                        const modal = document.getElementById('upload-modal');
                        if (modal) modal.remove();
                    }
                    
                    function updateFilePreview() {
                        const input = document.getElementById('file-input');
                        const preview = document.getElementById('file-preview');
                        const btn = document.getElementById('start-upload-btn');
                        
                        if (!input.files || input.files.length === 0) {
                            preview.innerHTML = '<div class="text-sm text-gray-500 text-center py-2">No files selected</div>';
                            btn.disabled = true;
                            return;
                        }
                        
                        btn.disabled = false;
                        const html = Array.from(input.files).map(file => {
                            const sizeMB = (file.size / 1024 / 1024).toFixed(2);
                            return `<div class="text-sm text-gray-700 py-1">📄 ${file.name} (${sizeMB} MB)</div>`;
                        }).join('');
                        preview.innerHTML = html;
                    }
                    
                    async function handleUploadSubmit(event) {
                        event.preventDefault();
                        
                        const input = document.getElementById('file-input');
                        if (!input.files || input.files.length === 0) {
                            alert('Please select files first');
                            return;
                        }
                        
                        // Collect form data
                        const formData = new FormData(document.getElementById('upload-form'));
                        const uploadConfig = {
                            upload_mode: formData.get('upload_mode'),
                            normalize: formData.get('normalize') === 'true',
                            target_lufs: parseFloat(formData.get('target_lufs') || '-23.0'),
                            normalize_batch: formData.get('normalize_batch') === 'true',
                            analyze_intro_outro: formData.get('analyze_intro_outro') === 'true',
                            segment_seconds: parseFloat(formData.get('segment_seconds') || '10.0'),
                            similarity_threshold: parseFloat(formData.get('similarity_threshold') || '0.75'),
                            show_waveform: formData.get('show_waveform') === 'true'
                        };
                        
                        try {
                            // Step 1: Create upload session
                            const sessionResponse = await fetch(`/playlists/${window.playlistId}/upload-session`, {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify(uploadConfig)
                            });
                            
                            if (!sessionResponse.ok) throw new Error('Failed to create upload session');
                            
                            const sessionData = await sessionResponse.json();
                            window.uploadSessionId = sessionData.session_id;
                            
                            // Step 2: Upload files
                            await uploadFilesToSession(input.files);
                            
                            // Step 3: Show progress modal
                            closeUploadModal();
                            showUploadProgress();
                            
                        } catch (error) {
                            console.error('Upload error:', error);
                            alert('Upload failed: ' + error.message);
                        }
                    }
                    
                    async function uploadFilesToSession(files) {
                        for (let file of files) {
                            const fileFormData = new FormData();
                            fileFormData.append('file', file);
                            
                            const response = await fetch(
                                `/playlists/${window.playlistId}/upload-session/${window.uploadSessionId}/files`,
                                {
                                    method: 'POST',
                                    body: fileFormData
                                }
                            );
                            
                            if (!response.ok) {
                                throw new Error(`Failed to upload ${file.name}`);
                            }
                        }
                    }
                    
                    function showUploadProgress() {
                        const progressHtml = `
                            <div id="upload-session-${window.uploadSessionId}" 
                                 class="border-l-4 border-blue-500 bg-blue-50 p-4 rounded-lg"
                                 hx-get="/playlists/${window.playlistId}/upload-session/${window.uploadSessionId}/status"
                                 hx-trigger="every 2s"
                                 hx-swap="outerHTML">
                                <div class="flex justify-between items-start gap-4">
                                    <div class="flex-1">
                                        <p class="font-medium text-gray-900">Uploading...</p>
                                        <span class="inline-block mt-2 px-2 py-1 rounded text-xs font-medium bg-blue-200 text-blue-800">Processing</span>
                                    </div>
                                </div>
                                <div class="mt-3 bg-gray-200 rounded-full h-2 overflow-hidden">
                                    <div class="bg-blue-600 h-full transition-all duration-300 w-full"></div>
                                </div>
                            </div>
                        `;
                        
                        const uploading = document.getElementById('uploading-section');
                        if (uploading) {
                            uploading.classList.remove('hidden');
                            uploading.innerHTML = progressHtml;
                            htmx.process(uploading);
                        }
                    }
                """),
            )
        )
    
    def _render_upload_options(self):
        """Render upload configuration options."""
        return d.Div(classes="space-y-4")(
            # Upload mode
            d.Div(classes="space-y-2")(
                d.Label(classes="block text-sm font-semibold text-gray-900")("Upload As"),
                d.Div(classes="flex gap-4")(
                    d.Label(classes="flex items-center cursor-pointer")(
                        d.Input(
                            type="radio",
                            name="upload_mode",
                            value="chapters",
                            checked=True,
                            classes="w-4 h-4 accent-indigo-600"
                        ),
                        d.Span(classes="ml-2 text-sm text-gray-700")("Chapters"),
                    ),
                    d.Label(classes="flex items-center cursor-pointer")(
                        d.Input(
                            type="radio",
                            name="upload_mode",
                            value="tracks",
                            classes="w-4 h-4 accent-indigo-600"
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
                        name="normalize",
                        value="true",
                        classes="w-4 h-4 accent-indigo-600",
                        **{"hx-on:change": "toggleClass('normalize-options', 'hidden')"}
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
                            classes="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                        ),
                    ),
                    d.Label(classes="flex items-center cursor-pointer gap-2")(
                        d.Input(
                            type="checkbox",
                            name="normalize_batch",
                            value="true",
                            classes="w-4 h-4 accent-indigo-600"
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
                        name="analyze_intro_outro",
                        value="true",
                        classes="w-4 h-4 accent-indigo-600",
                        **{"hx-on:change": "toggleClass('analysis-options', 'hidden')"}
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
                            classes="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
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
                            classes="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                        ),
                    ),
                ),
            ),
            
            # Waveform
            d.Label(classes="flex items-center cursor-pointer gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200")(
                d.Input(
                    type="checkbox",
                    name="show_waveform",
                    value="true",
                    classes="w-4 h-4 accent-indigo-600"
                ),
                d.Span(classes="text-sm font-semibold text-gray-900")("Show waveform visualization"),
            ),
        )


class UploadProgressPartial(Component):
    """Server-rendered upload progress display - polls session status."""
    
    def __init__(self, session_id: str, playlist_id: str):
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
                    d.Span(classes="inline-block mt-2 px-2 py-1 rounded text-xs font-medium bg-blue-200 text-blue-800")(
                        "In Progress"
                    ),
                ),
                d.Button(
                    classes="text-gray-500 hover:text-gray-700 text-xl",
                    hx_delete=f"/playlists/{self.playlist_id}/upload-session/{self.session_id}",
                    hx_target=f"#upload-session-{self.session_id}",
                    hx_swap="outerHTML",
                )("✕"),
            ),
            d.Div(classes="mt-3 bg-gray-200 rounded-full h-2 overflow-hidden")(
                d.Div(
                    classes="bg-blue-600 h-full transition-all duration-300 w-1/3"
                )()
            ),
        )


class NewPlaylistModalPartial(Component):
    """Modal dialog for creating a new playlist."""
    
    def render(self):
        return d.Div(
            id="new-playlist-modal",
            classes="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4",
            **{"hx-on:keydown.escape": "closeNewPlaylistModal()"}
        )(
            d.Div(classes="bg-white rounded-lg shadow-2xl max-w-md w-full")(
                # Header
                d.Div(classes="px-6 py-4 border-b border-gray-200 flex justify-between items-center")(
                    d.H3(classes="text-2xl font-bold text-gray-900")("Create New Playlist"),
                    d.Button(
                        classes="text-gray-500 hover:text-gray-700 text-2xl bg-none border-none cursor-pointer",
                        type="button",
                        **{"hx-on:click": "closeNewPlaylistModal()"}
                    )("✕"),
                ),
                
                # Form
                d.Form(
                    id="new-playlist-form",
                    hx_post="/playlists/create-with-cover",
                    hx_target="#playlist-list",
                    hx_swap="innerHTML",
                    **{"hx-on::after-request": "if(event.detail.successful) { closeNewPlaylistModal(); }"},
                    classes="space-y-4"
                )(
                    # Content
                    d.Div(classes="px-6 py-6 space-y-5")(
                        # Title field
                        d.Div(classes="flex flex-col")(
                            d.Label(
                                html_for="playlist-title",
                                classes="block text-sm font-semibold text-gray-900 mb-2"
                            )("Playlist Title"),
                            d.Input(
                                type="text",
                                id="playlist-title",
                                name="title",
                                placeholder="e.g., My Stories",
                                required=True,
                                classes="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition"
                            ),
                        ),
                        
                        # Cover image section
                        d.Div(classes="flex flex-col")(
                            d.Label(classes="block text-sm font-semibold text-gray-900 mb-2")("Cover Image (Optional)"),
                            
                            # Cover preview
                            d.Div(
                                id="cover-preview",
                                classes="w-full h-40 bg-gray-100 rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center mb-3 text-gray-400"
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
                                    onclick="document.getElementById('cover-file-input').click()"
                                )("📁 Upload File"),
                                d.Button(
                                    type="button",
                                    classes="flex-1 px-4 py-2 border border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium text-sm",
                                    onclick="showCoverUrlInput()"
                                )("🔗 Use URL"),
                            ),
                            
                            # File input (hidden)
                            d.Input(
                                type="file",
                                id="cover-file-input",
                                name="cover_file",
                                accept="image/*",
                                classes="hidden",
                                **{"hx-on:change": "handleCoverFileSelected(event)"}
                            ),
                            
                            # URL input (hidden by default)
                            d.Div(
                                id="cover-url-input-container",
                                classes="hidden mt-3"
                            )(
                                d.Input(
                                    type="url",
                                    id="cover-url-input",
                                    name="cover_url",
                                    placeholder="https://example.com/image.jpg",
                                    classes="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition"
                                ),
                            ),
                        ),
                    ),
                    
                    # Footer
                    d.Div(classes="px-6 py-4 border-t border-gray-200 flex justify-end gap-3")(
                        d.Button(
                            type="button",
                            classes="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium",
                            **{"hx-on:click": "closeNewPlaylistModal()"}
                        )("Cancel"),
                        d.Button(
                            type="submit",
                            classes="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
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
    
    def __init__(self, json_data: str):
        super().__init__()
        self.json_data = json_data
    
    def render(self):
        return d.Div(
            id="json-modal",
            classes="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
        )(
            d.Div(classes="bg-white rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto")(
                # Header
                d.Div(classes="sticky top-0 px-6 py-4 border-b border-gray-200 bg-white flex justify-between items-center")(
                    d.H3(classes="text-2xl font-bold text-gray-900")("Playlist JSON"),
                    d.Div(classes="flex gap-2")(
                        d.Button(
                            classes="px-3 py-1 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium",
                            onclick="copyToClipboard_json_content()"
                        )("📋 Copy"),
                        d.Button(
                            classes="text-gray-500 hover:text-gray-700 text-2xl",
                            **{"hx-on:click": "document.getElementById('json-modal').classList.add('hidden')"}
                        )("✕"),
                    ),
                ),
                
                # Content
                d.Div(classes="px-6 py-6")(
                    d.Pre(
                        id="json_content",
                        classes="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm font-mono max-h-[70vh] overflow-y-auto"
                    )(
                        d.Code()(self.json_data)
                    ),
                ),
            )
        )
