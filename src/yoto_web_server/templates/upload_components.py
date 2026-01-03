"""
Upload-related components for HTMX-driven file uploads.
"""

from pydom import Component
from pydom import html as d

from yoto_web_server.models import (
    FileUploadStatus,
    SessionUploadStatus,
    UploadFileStatus,
    UploadSession,
)
from yoto_web_server.utils.alpine import xbind, xdata, xif, xmodel, xon, xshow
from yoto_web_server.utils.style import classnames


class UploadModalPartial(Component):
    """Server-rendered upload modal with file and YouTube URL support."""

    def __init__(self, *, playlist_id: str, youtube_available: bool = False):
        super().__init__()
        self.playlist_id = playlist_id
        self.youtube_available = youtube_available

    def render(self):
        return d.Div(
            id="upload-modal",
            classes="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4",
            **xon().keydown.escape("document.getElementById('upload-modal')?.remove()"),
        )(
            d.Div(
                classes="bg-white rounded-lg shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto flex flex-col",
            )(
                # Header
                d.Div(
                    classes="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center"
                )(
                    d.H3(classes="text-2xl font-bold text-gray-900")("Upload to Playlist"),
                    d.Button(
                        type="button",
                        classes="text-gray-500 hover:text-gray-700 text-2xl",
                        **xon().click("document.getElementById('upload-modal')?.remove()"),
                    )("✕"),
                ),
                # Main content area
                d.Div(classes="flex-1 overflow-y-auto px-6 py-6 space-y-6")(
                    # Pending Files Section
                    d.Div(classes="space-y-3")(
                        d.Label(classes="block text-sm font-semibold text-gray-900")(
                            "📋 Pending Files"
                        ),
                        d.Div(
                            id="pending-files-list",
                            classes="max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-3 bg-gray-50 min-h-12",
                        )(
                            d.Div(classes="text-sm text-gray-500 text-center py-2")(
                                "No files selected"
                            )
                        ),
                    ),
                    # Pending URLs Section (if YouTube available)
                    *(
                        [
                            d.Div(classes="space-y-3")(
                                d.Label(classes="block text-sm font-semibold text-gray-900")(
                                    "▶️ Pending URLs"
                                ),
                                d.Div(
                                    id="pending-urls-list",
                                    classes="group max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-3 bg-gray-50 min-h-12",
                                )(
                                    d.Div(
                                        classes="text-sm text-gray-500 text-center py-2 hidden group-empty:block"
                                    )("No URLs added")
                                ),
                            )
                        ]
                        if self.youtube_available
                        else []
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
                        d.Button(
                            type="button",
                            id="add-youtube-url-btn",
                            classes="flex-1 px-4 py-3 border-2 border-dashed border-red-300 rounded-lg hover:border-red-500 hover:bg-red-50 transition-colors text-center",
                            hx_get="/youtube/upload-modal/",
                            hx_target="#youtube-upload-modal",
                            hx_swap="outerHTML",
                        )("▶️ From YouTube")
                        if self.youtube_available
                        else None,
                    ),
                    # YouTube Modal Container
                    d.Div(
                        id="youtube-upload-modal",
                        classes="hidden",
                    ),
                    # Upload options
                    self._render_upload_options(),
                ),
                # Footer
                d.Div(
                    classes="sticky bottom-0 px-6 py-4 border-t border-gray-200 bg-white flex justify-end gap-3"
                )(
                    d.Button(
                        type="button",
                        classes="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium",
                        **xon().click("document.getElementById('upload-modal')?.remove()"),
                    )("Cancel"),
                    d.Button(
                        type="button",
                        id="start-upload-btn",
                        classes="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed",
                        disabled=True,
                    )("⬆️ Start Upload"),
                ),
            ),
            # Script for file selection and upload logic
            d.Script()(
                rf"""//js
            {{

            const pendingFiles = [];
            const pendingUrls = [];
            let currentPlaylistId = '{self.playlist_id}';

            // Listen for YouTube URLs being added to the pending URLs list
            const pendingUrlsList = document.getElementById('pending-urls-list');
            if (pendingUrlsList) {{
                const observer = new MutationObserver(() => {{
                    updateStartUploadButton();
                }});
                observer.observe(pendingUrlsList, {{ childList: true }});
            }}

            function getPendingYouTubeUrls() {{
                const urlsList = document.getElementById('pending-urls-list');
                const urls = [];
                if (urlsList) {{
                    urlsList.querySelectorAll('[id^="youtube-pending-"]').forEach(entry => {{
                        const url = entry.getAttribute('data-youtube-url');
                        if (url) urls.push(url);
                    }});
                }}
                return urls;
            }}

            function updateStartUploadButton() {{
                const files = pendingFiles.length;
                const urls = getPendingYouTubeUrls().length;
                const uploadBtn = document.getElementById('start-upload-btn');
                uploadBtn.disabled = files + urls === 0;
            }}

            // File selection handlers
            document.getElementById('select-files-btn')?.addEventListener('click', async () => {{
                try {{
                    if ('showOpenFilePicker' in window) {{
                        const fileHandles = await window.showOpenFilePicker({{
                            multiple: true,
                            types: [{{ description: 'Audio files', accept: {{ 'audio/*': ['.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac', '.m4b'] }} }}]
                        }});
                        for (const handle of fileHandles) {{
                            const file = await handle.getFile();
                            addFileToPending(file);
                        }}
                    }} else {{
                        const input = document.createElement('input');
                        input.type = 'file';
                        input.multiple = true;
                        input.accept = 'audio/*';
                        input.onchange = (e) => {{
                            for (const file of e.target.files) addFileToPending(file);
                        }};
                        input.click();
                    }}
                }} catch (err) {{
                    if (err.name !== 'AbortError') console.error('File selection error:', err);
                }}
            }});

            // Folder selection handler
            document.getElementById('select-folder-btn')?.addEventListener('click', async () => {{
                try {{
                    if ('showDirectoryPicker' in window) {{
                        const dirHandle = await window.showDirectoryPicker();
                        await processDirectory(dirHandle);
                    }} else {{
                        const input = document.createElement('input');
                        input.type = 'file';
                        input.webkitdirectory = true;
                        input.onchange = (e) => {{
                            for (const file of e.target.files) {{
                                if (file.type.startsWith('audio/') || /\\.(mp3|m4a|wav|flac|ogg|aac|m4b)$/i.test(file.name)) {{
                                    addFileToPending(file);
                                }}
                            }}
                        }};
                        input.click();
                    }}
                }} catch (err) {{
                    if (err.name !== 'AbortError') console.error('Folder selection error:', err);
                }}
            }});

            async function processDirectory(dirHandle) {{
                for await (const entry of dirHandle.values()) {{
                    if (entry.kind === 'file') {{
                        const file = await entry.getFile();
                        if (file.type.startsWith('audio/') || /\\.(mp3|m4a|wav|flac|ogg|aac|m4b)$/i.test(file.name)) {{
                            addFileToPending(file);
                        }}
                    }} else if (entry.kind === 'directory') {{
                        await processDirectory(entry);
                    }}
                }}
            }}

            function addFileToPending(file) {{
                const exists = pendingFiles.some(f => f.name === file.name && f.size === file.size);
                if (!exists) {{
                    pendingFiles.push({{ file, name: file.name, size: file.size }});
                    updatePendingFilesList();
                }}
            }}

            function removeFromPending(index) {{
                pendingFiles.splice(index, 1);
                updatePendingFilesList();
            }}

            function updatePendingFilesList() {{
                const list = document.getElementById('pending-files-list');
                const uploadBtn = document.getElementById('start-upload-btn');

                if (pendingFiles.length === 0) {{
                    list.innerHTML = '<div class="text-sm text-gray-500 text-center py-2">No files selected</div>';
                    uploadBtn.disabled = true;
                    return;
                }}

                uploadBtn.disabled = false;
                list.innerHTML = pendingFiles.map((f, i) => `
                    <div class="flex items-center justify-between py-1 border-b border-gray-100 last:border-0">
                        <span class="text-sm text-gray-800">📄 ${{f.name}}</span>
                        <button type="button" class="text-red-500 hover:text-red-700 text-sm" onclick="removeFromPending(${{i}})">✕</button>
                    </div>
                `).join('');
            }}

            // Upload handler
            document.getElementById('start-upload-btn')?.addEventListener('click', async () => {{
                const files = pendingFiles;
                const urls = getPendingYouTubeUrls();
                if (files.length === 0 && urls.length === 0) return;

                // Disable the button to prevent multiple clicks
                const uploadBtn = document.getElementById('start-upload-btn');
                uploadBtn.disabled = true;

                // Get form options
                const uploadMode = document.querySelector('input[name="upload_mode"]:checked')?.value || 'chapters';
                const normalize = document.getElementById('normalize-checkbox')?.checked || false;
                const targetLufs = parseFloat(document.querySelector('input[name="target_lufs"]')?.value || '-23.0');
                const normalizeBatch = document.getElementById('normalize_batch-checkbox')?.checked || false;
                const analyzeIntroOutro = document.getElementById('analyze_intro_outro-checkbox')?.checked || false;
                const segmentSeconds = parseFloat(document.querySelector('input[name="segment_seconds"]')?.value || '10.0');
                const similarityThreshold = parseFloat(document.querySelector('input[name="similarity_threshold"]')?.value || '0.75');
                const showWaveform = document.getElementById('show_waveform-checkbox')?.checked || false;

                try {{
                    // Step 1: Create upload session
                    const sessionRes = await fetch(`/playlists/${{currentPlaylistId}}/upload-session`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            upload_mode: uploadMode,
                            normalize: normalize,
                            target_lufs: targetLufs,
                            normalize_batch: normalizeBatch,
                            analyze_intro_outro: analyzeIntroOutro,
                            segment_seconds: segmentSeconds,
                            similarity_threshold: similarityThreshold,
                            show_waveform: showWaveform
                        }})
                    }});

                    if (!sessionRes.ok) {{
                        throw new Error(`Failed to create upload session: ${{sessionRes.statusText}}`);
                    }}

                    const sessionData = await sessionRes.json();
                    const sessionId = sessionData.session_id;

                    // Step 2: Register YouTube URLs if any
                    if (urls.length > 0) {{
                        const urlsRes = await fetch(`/playlists/${{currentPlaylistId}}/upload-session/${{sessionId}}/youtube-urls`, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                            body: new URLSearchParams({{ youtube_urls: JSON.stringify(urls) }}).toString()
                        }});

                        if (!urlsRes.ok) {{
                            console.error(`Failed to register YouTube URLs: ${{urlsRes.statusText}}`);
                        }}
                    }}

                    const totalItems = files.length + urls.length;

                    // Step 3: Pre-register file count if any
                    if (files.length > 0) {{
                        const registerRes = await fetch(`/playlists/${{currentPlaylistId}}/upload-session/${{sessionId}}/register-files`, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                            body: new URLSearchParams({{ file_count: files.length }}).toString()
                        }});

                        if (!registerRes.ok) {{
                            throw new Error(`Failed to register files: ${{registerRes.statusText}}`);
                        }}
                    }}

                    // Step 4: Upload each file to the session
                    let uploadedCount = 0;
                    for (const {{ file }} of files) {{
                        const formData = new FormData();
                        formData.append('file', file);

                        const uploadRes = await fetch(`/playlists/${{currentPlaylistId}}/upload-session/${{sessionId}}/files`, {{
                            method: 'POST',
                            body: formData
                        }});

                        if (!uploadRes.ok) {{
                            console.error(`Failed to upload ${{file.name}}: ${{uploadRes.statusText}}`);
                        }} else {{
                            uploadedCount++;
                            const progress = totalItems > 0 ? (uploadedCount / totalItems) * 100 : 100;
                            // Show progress to user
                            console.log(`Upload progress: ${{progress.toFixed(0)}}%`);
                        }}
                    }}

                    // Step 5: Finalize the session - all files/URLs registered, ready to process
                    const finalizeRes = await fetch(`/playlists/${{currentPlaylistId}}/upload-session/${{sessionId}}/finalize`, {{
                        method: 'POST'
                    }});

                    if (!finalizeRes.ok) {{
                        throw new Error(`Failed to finalize upload: ${{finalizeRes.statusText}}`);
                    }}

                    // Success - close modal and reload playlist
                    setTimeout(() => {{
                        document.getElementById('upload-modal')?.remove();
                        htmx.ajax('GET', `/playlists/${{currentPlaylistId}}`, {{ target: 'body', swap: 'outerHTML' }});
                    }}, 1000);
                }} catch (err) {{
                    console.error('Upload error:', err);
                    alert('Upload failed: ' + err.message);
                    uploadBtn.disabled = false;
                }}
            }});


            }}
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
                            checked="checked",
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
            d.Div(
                classes="space-y-3 p-4 bg-gray-50 rounded-lg border border-gray-200",
                **xdata({"normalize": False}),
            )(
                d.Label(classes="flex items-center cursor-pointer gap-2")(
                    d.Input(
                        type="checkbox",
                        id="normalize-checkbox",
                        name="normalize",
                        classes="w-4 h-4 accent-indigo-600",
                        **xmodel("normalize"),
                    ),
                    d.Span(classes="text-sm font-semibold text-gray-900")("Normalize Audio"),
                ),
                d.Div(**xshow("normalize"), classes="space-y-3 pl-6")(
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
                            classes="w-4 h-4 accent-indigo-600",
                        ),
                        d.Span(classes="text-sm text-gray-700")("Batch mode (Album normalization)"),
                    ),
                ),
            ),
            # Analysis
            d.Div(
                classes="space-y-3 p-4 bg-gray-50 rounded-lg border border-gray-200",
                **xdata({"analyze": False}),
            )(
                d.Label(classes="flex items-center cursor-pointer gap-2")(
                    d.Input(
                        type="checkbox",
                        id="analyze_intro_outro-checkbox",
                        name="analyze_intro_outro",
                        classes="w-4 h-4 accent-indigo-600",
                        **xmodel("analyze"),
                    ),
                    d.Span(classes="text-sm font-semibold text-gray-900")("Analyze Intro/Outro"),
                ),
                d.Div(**xshow("analyze"), classes="space-y-3 pl-6")(
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
            hx_get=f"/playlists/{self.playlist_id}/upload-sessions",
            hx_trigger="load delay:1s",
            hx_swap="outerHTML",
        )(
            d.Div(id="uploads-list", classes="space-y-4")(),
        )


class NewPlaylistModalPartial(Component):
    """Modal dialog for creating a new playlist."""

    def render(self):
        return d.Div(
            id="new-playlist-modal",
            classes="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4",
            **xdata({"showCoverUrl": False, "coverPreview": None}),
            **xon().keydown.escape("document.getElementById('new-playlist-modal')?.remove()"),
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
                        **xon().click("document.getElementById('new-playlist-modal')?.remove()"),
                    )("✕"),
                ),
                # Form
                d.Form(
                    id="new-playlist-form",
                    hx_post="/playlists/create-with-cover",
                    hx_target="#playlist-list",
                    hx_swap="innerHTML",
                    hx_on_htmx_after_request="if(event.detail.successful) { document.getElementById('new-playlist-modal').remove(); }",
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
                                classes="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition",
                                required="required",
                            ),
                        ),
                        # Cover image section
                        d.Div(classes="flex flex-col")(
                            d.Label(classes="block text-sm font-semibold text-gray-900 mb-2")(
                                "Cover Image (Optional)"
                            ),
                            # Cover preview
                            d.Div(
                                classes="w-full h-40 bg-gray-100 rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center mb-3 text-gray-400",
                            )(
                                d.Template(**xif("!coverPreview"))(
                                    d.Div(classes="text-center")(
                                        d.Div(classes="text-2xl mb-2")("🖼️"),
                                        d.Div(classes="text-sm")("No image selected"),
                                    )
                                ),
                                d.Template(**xif("coverPreview"))(
                                    d.Img(
                                        **xbind().src("coverPreview"),
                                        classes="w-full h-full object-cover rounded-lg",
                                    )
                                ),
                            ),
                            # Upload options
                            d.Div(classes="flex gap-2")(
                                d.Button(
                                    type="button",
                                    classes="flex-1 px-4 py-2 border border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium text-sm",
                                    **xon().click(
                                        "document.getElementById('cover-file-input').click()"
                                    ),
                                )("📁 Upload File"),
                                d.Button(
                                    type="button",
                                    classes="flex-1 px-4 py-2 border border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium text-sm",
                                    **xon().click("showCoverUrl = !showCoverUrl"),
                                )("🔗 Use URL"),
                            ),
                            # File input (hidden)
                            d.Input(
                                type="file",
                                id="cover-file-input",
                                name="cover_file",
                                accept="image/*",
                                classes="hidden",
                                **xon().change(
                                    "const file = $el.files?.[0]; if (file) { const reader = new FileReader(); reader.onload = (e) => { coverPreview = e.target.result; }; reader.readAsDataURL(file); }"
                                ),
                            ),
                            # URL input (hidden by default)
                            d.Div(**xshow("showCoverUrl"), classes="mt-3")(
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
                            **xon().click(
                                "document.getElementById('new-playlist-modal')?.remove()"
                            ),
                        )("Cancel"),
                        d.Button(
                            type="submit",
                            classes="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium",
                        )("✨ Create Playlist"),
                    ),
                ),
            ),
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
            **xon().keydown.escape("document.getElementById('json-modal')?.remove()"),
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
                            **xon().click(
                                "navigator.clipboard.writeText(document.getElementById('json_content').innerText)"
                            ),
                        )("📋 Copy"),
                        d.Button(
                            classes="text-gray-500 hover:text-gray-700 text-2xl",
                            **xon().click("document.getElementById('json-modal')?.remove()"),
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


class UploadSessionsListPartial(Component):
    """Renders a list of active upload sessions for HTMX polling."""

    def __init__(self, *, playlist_id: str, sessions: list[UploadSession]):
        super().__init__()
        self.playlist_id = playlist_id
        self.sessions = sessions

    def render(self):
        if not self.sessions:
            return d.Div(
                id="active-uploads-container",
                classes="hidden",
                hx_get=f"/playlists/{self.playlist_id}/upload-sessions",
                hx_trigger="load delay:2s",
                hx_swap="outerHTML",
            )()

        return d.Div(
            id="active-uploads-container",
            classes="border-t border-gray-200 px-6 py-6 bg-gray-50",
            hx_get=f"/playlists/{self.playlist_id}/upload-sessions",
            hx_trigger="load delay:2s",
            hx_swap="outerHTML",
        )(
            d.H3(classes="text-lg font-semibold text-gray-900 mb-4")("⬆️ Active Uploads"),
            d.Div(id="uploads-list", classes="space-y-4")(
                *[self._render_session(session) for session in self.sessions]
            ),
        )

    def _render_session(self, session: UploadSession):
        """Render a single upload session."""
        total_files = len(session.files) if session.files else 0
        completed_files = (
            len([f for f in session.files if f.status == FileUploadStatus.DONE])
            if session.files
            else 0
        )
        progress = int(completed_files / total_files * 100) if total_files > 0 else 0
        is_done = session.overall_status in (
            SessionUploadStatus.DONE_SUCCESS,
            SessionUploadStatus.DONE_PARTIAL_SUCCESS,
            SessionUploadStatus.DONE_ALL_ERROR,
        )
        is_success = session.overall_status == SessionUploadStatus.DONE_SUCCESS
        is_partial = session.overall_status == SessionUploadStatus.DONE_PARTIAL_SUCCESS
        is_error = session.overall_status == SessionUploadStatus.DONE_ALL_ERROR

        return d.Div(
            id=f"upload-session-{session.session_id}",
            classes="border border-blue-200 rounded-lg p-4 bg-white",
        )(
            d.Div(classes="mb-3")(
                d.Div(classes="flex justify-between items-center mb-2")(
                    d.Span(classes="font-medium text-gray-900")(
                        f"Session {session.session_id[:8]}"
                    ),
                    d.Span(classes="text-sm text-gray-600")(f"{completed_files}/{total_files}"),
                ),
                d.Div(classes="w-full bg-gray-200 rounded-full h-2")(
                    d.Div(
                        classes="bg-blue-600 h-2 rounded-full transition-all",
                        style=f"width: {progress}%",
                    )()
                ),
            ),
            d.Div(classes="space-y-1 text-sm mb-3")(
                *[self._render_file(f) for f in (session.files or [])]
            ),
            d.Div(classes="flex justify-end")(
                # Dismiss
                d.Button(
                    type="button",
                    classes=classnames(
                        "px-3 py-1 text-sm rounded transition-colors text-white",
                        {
                            "bg-green-600 hover:bg-green-700": is_success,
                            "bg-yellow-600 hover:bg-yellow-700": is_partial,
                            "bg-red-600 hover:bg-red-700": is_error,
                        },
                    ),
                    hx_delete=f"/playlists/{self.playlist_id}/upload-session/{session.session_id}",
                    hx_target="#active-uploads-container",
                    hx_swap="outerHTML",
                    hx_on__after_swap=f"htmx.ajax('GET', '/playlists/{self.playlist_id}', {{target: '#playlist-detail', swap: 'innerHTML'}})",
                )("Dismiss")
                if is_done
                else None,
                # Stop button
                d.Button(
                    type="button",
                    classes=classnames(
                        "px-3 py-1 text-sm rounded transition-colors text-white",
                        "bg-red-600 hover:bg-red-700",
                    ),
                    hx_post=f"/playlists/{self.playlist_id}/upload-session/{session.session_id}/stop",
                    hx_target="#active-uploads-container",
                    hx_swap="outerHTML",
                )("Stop Upload")
                if not is_done
                else None,
            ),
        )

    def _render_file(self, file: UploadFileStatus):
        """Render a single file status."""
        status_icons = {
            FileUploadStatus.DONE: ("✅", "text-green-600"),
            FileUploadStatus.YOTO_UPLOADING: ("⬆️", "text-blue-600"),
            FileUploadStatus.PROCESSING: ("🔄", "text-yellow-600"),
            FileUploadStatus.QUEUED: ("📋", "text-gray-600"),
            FileUploadStatus.UPLOADING: ("⬆️", "text-blue-600"),
            FileUploadStatus.PENDING: ("⏳", "text-gray-500"),
        }

        icon, color = status_icons.get(file.status, ("⏳", "text-gray-500"))
        status_label = file.status.replace("_", " ")

        return d.Div(classes="flex items-center justify-between py-2")(
            d.Span(classes="text-sm text-gray-800")(f"📄 {file.filename}"),
            d.Span(**{"class": f"{color} text-sm font-medium"})(f"{icon} {status_label}"),
        )


class YouTubeMetadataPreviewPartial(Component):
    """HTMX-rendered YouTube metadata preview."""

    def __init__(self, metadata):
        super().__init__()
        self.metadata = metadata

    def render(self):
        """Render the metadata preview HTML to be swapped by HTMX."""
        return d.Div(
            classes="flex gap-4",
            hx_swap_oob="true",  # Out-of-band swap to also show the preview
        )(
            d.Img(
                src=self.metadata.thumbnail_url,
                alt=self.metadata.title,
                classes="w-32 h-32 rounded object-cover",
            ),
            d.Div(classes="flex-1 space-y-2")(
                d.H3(classes="text-lg font-semibold")(self.metadata.title),
                d.P(classes="text-sm text-gray-600")(f"By {self.metadata.uploader}"),
                d.P(classes="text-sm text-gray-600")(
                    f"Duration: {self._format_duration(self.metadata.duration_seconds)}"
                ),
                d.P(classes="text-sm text-gray-600")(f"Uploaded: {self.metadata.upload_date}"),
                d.P(classes="text-sm text-gray-500 line-clamp-2")(self.metadata.description),
                d.Button(
                    type="button",
                    classes="mt-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium",
                    hx_post="",  # Would be filled by JS to add to pending list
                    id=f"add-youtube-btn-{self.metadata.video_id}",
                )("+ Add to Upload"),
            ),
        )

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Format duration in seconds to human-readable format."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"


class YouTubeURLEntryPartial(Component):
    """URL entry item for pending YouTube URLs list - similar to file entry."""

    def __init__(self, video_id: str, title: str, duration_seconds: int):
        super().__init__()
        self.video_id = video_id
        self.title = title
        self.duration_seconds = duration_seconds

    def render(self):
        """Render a URL entry similar to file entry."""
        duration = self._format_duration(self.duration_seconds)
        return d.Div(
            classes="flex items-center justify-between py-2 border-b border-gray-100 last:border-0",
            data_video_id=self.video_id,
        )(
            d.Div(classes="flex-1")(
                d.Span(classes="text-sm text-gray-800")(f"▶️ {self.title}"),
                d.Span(classes="block text-xs text-gray-500 mt-1")(f"Duration: {duration}"),
            ),
            d.Button(
                type="button",
                classes="text-red-500 hover:text-red-700 text-sm font-medium",
                **xon().click(
                    f"event.target.closest('div[data-video-id=\"{self.video_id}\"]')?.remove()"
                ),
            )("✕"),
        )

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Format duration in seconds to human-readable format."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
