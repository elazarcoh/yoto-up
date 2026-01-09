"""
Advanced upload session page component.

Provides the main page for managing an advanced upload session with file list
and edit capabilities.
"""

from pydom import Component
from pydom import html as d

from yoto_web_server.models import UploadSession
from yoto_web_server.templates.session_edit_components import SessionFileListPartial


class AdvancedUploadSessionPage(Component):
    """Advanced upload session page with file management."""

    def __init__(self, *, session: UploadSession, playlist_id: str):
        super().__init__()
        self.session = session
        self.playlist_id = playlist_id

    def render(self):
        return d.Div(
            classes="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8",
        )(
            # Header
            d.Div(classes="mb-6")(
                d.A(
                    href=f"/playlists/{self.playlist_id}",
                    classes="inline-flex items-center px-4 py-2 text-indigo-600 hover:text-indigo-900 hover:bg-indigo-50 rounded-md transition-colors",
                )("← Back to Playlist")
            ),
            # Main card
            d.Div(classes="bg-white shadow-lg rounded-lg overflow-hidden")(
                # Header section
                d.Div(classes="px-6 py-8 sm:px-8 bg-gradient-to-r from-indigo-50 to-blue-50")(
                    d.H1(classes="text-3xl font-bold text-gray-900 mb-2")("Advanced Upload"),
                    d.P(classes="text-base text-gray-600")(
                        f"Session ID: {self.session.session_id}"
                    ),
                ),
                # Content section
                d.Div(classes="border-t border-gray-200 px-6 py-8 sm:px-8")(
                    d.Div(classes="grid grid-cols-1 lg:grid-cols-3 gap-8")(
                        # Left column: File list and upload
                        d.Div(classes="lg:col-span-1")(
                            d.H2(classes="text-lg font-semibold text-gray-900 mb-4")(
                                "Files & URLs"
                            ),
                            d.Div(
                                id="session-files-container",
                                classes="space-y-4",
                            )(
                                SessionFileListPartial(session=self.session),
                                # Upload buttons
                                d.Div(classes="border-t border-gray-200 pt-4 mt-4 space-y-3")(
                                    d.Button(
                                        type="button",
                                        id="advanced-upload-files-btn",
                                        classes="w-full px-4 py-3 border-2 border-dashed border-indigo-300 rounded-lg hover:border-indigo-500 hover:bg-indigo-50 transition-colors text-center font-medium text-gray-700",
                                    )(
                                        d.Div()("📄 Upload Files"),
                                    ),
                                    d.Button(
                                        type="button",
                                        id="advanced-upload-folder-btn",
                                        classes="w-full px-4 py-3 border-2 border-dashed border-indigo-300 rounded-lg hover:border-indigo-500 hover:bg-indigo-50 transition-colors text-center font-medium text-gray-700",
                                    )(
                                        d.Div()("📁 Upload Folder"),
                                    ),
                                    d.Button(
                                        type="button",
                                        id="advanced-upload-youtube-btn",
                                        classes="w-full px-4 py-3 border-2 border-dashed border-red-300 rounded-lg hover:border-red-500 hover:bg-red-50 transition-colors text-center font-medium text-gray-700",
                                        hx_get="/youtube/advanced-upload-modal/",
                                        hx_target="#youtube-modal-container",
                                        hx_swap="outerHTML",
                                    )(
                                        d.Div()("▶️ YouTube URL"),
                                    ),
                                ),
                            ),
                        ),
                        # Right column: File editor
                        d.Div(classes="lg:col-span-2")(
                            d.H2(classes="text-lg font-semibold text-gray-900 mb-4")(
                                "File Details"
                            ),
                            d.Div(
                                id="session-file-editor",
                                classes="text-center py-8 text-gray-500",
                            )("Select a file to edit its details"),
                        ),
                    ),
                ),
                # Action footer
                d.Div(classes="border-t border-gray-200 px-6 py-6 sm:px-8 bg-gray-50 flex gap-3")(
                    d.Button(
                        type="button",
                        classes="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors font-medium",
                        hx_post=f"/playlists/{self.playlist_id}/upload-session/{self.session.session_id}/cancel",
                        hx_confirm="Are you sure you want to cancel this upload session?",
                        hx_on__after_request="const response = event.detail.xhr.response; const data = JSON.parse(response); if (data.redirect) window.location.href = data.redirect;",
                    )("✕ Cancel Session"),
                    d.Button(
                        type="button",
                        classes="ml-auto px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed",
                        id="finish-session-btn",
                        disabled=len(self.session.files) == 0,
                        hx_post=f"/playlists/{self.playlist_id}/upload-session/{self.session.session_id}/finish",
                        hx_confirm="Start processing uploaded files?",
                        hx_on__after_request="const response = event.detail.xhr.response; const data = JSON.parse(response); if (data.redirect) window.location.href = data.redirect;",
                    )("🎬 Finish & Process"),
                ),
            ),
            # YouTube modal container
            d.Div(id="youtube-modal-container")(),
            # Script for file upload handling
            d.Script()(
                rf"""//js
                {{
                    const sessionId = '{self.session.session_id}';
                    const playlistId = '{self.playlist_id}';

                    // File selection handler
                    document.getElementById('advanced-upload-files-btn')?.addEventListener('click', async () => {{
                        try {{
                            if ('showOpenFilePicker' in window) {{
                                const fileHandles = await window.showOpenFilePicker({{
                                    multiple: true,
                                    types: [{{ description: 'Audio files', accept: {{ 'audio/*': ['.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac', '.m4b'] }} }}]
                                }});
                                for (const handle of fileHandles) {{
                                    const file = await handle.getFile();
                                    uploadFile(file);
                                }}
                            }} else {{
                                const input = document.createElement('input');
                                input.type = 'file';
                                input.multiple = true;
                                input.accept = 'audio/*';
                                input.onchange = (e) => {{
                                    for (const file of e.target.files) uploadFile(file);
                                }};
                                input.click();
                            }}
                        }} catch (err) {{
                            if (err.name !== 'AbortError') console.error('File selection error:', err);
                        }}
                    }});

                    // Folder selection handler
                    document.getElementById('advanced-upload-folder-btn')?.addEventListener('click', async () => {{
                        try {{
                            if ('showDirectoryPicker' in window) {{
                                const dirHandle = await window.showDirectoryPicker();
                                for await (const [name, handle] of dirHandle.entries()) {{
                                    if (handle.kind === 'file') {{
                                        const file = await handle.getFile();
                                        uploadFile(file);
                                    }}
                                }}
                            }} else {{
                                alert('Directory picker not supported in your browser');
                            }}
                        }} catch (err) {{
                            if (err.name !== 'AbortError') console.error('Folder selection error:', err);
                        }}
                    }});

                    async function uploadFile(file) {{
                        try {{
                            console.log('Uploading file:', file.name, 'Size:', file.size);
                            
                            // Step 1: Register file in session (metadata only)
                            const formData = new FormData();
                            formData.append('filename', file.name);
                            formData.append('size_bytes', file.size);
                            
                            const registerResponse = await fetch(
                                `/playlists/${{playlistId}}/upload-session/${{sessionId}}/register-file`,
                                {{
                                    method: 'POST',
                                    body: formData
                                }}
                            );
                            
                            if (!registerResponse.ok) {{
                                throw new Error(`Failed to register file: ${{registerResponse.statusText}}`);
                            }}
                            
                            const registerData = await registerResponse.json();
                            const fileId = registerData.file_id;
                            console.log('File registered with ID:', fileId);
                            
                            // Step 2: Upload the actual file content
                            const uploadFormData = new FormData();
                            uploadFormData.append('file', file);
                            
                            const uploadResponse = await fetch(
                                `/playlists/${{playlistId}}/upload-session/${{sessionId}}/upload-file/${{fileId}}`,
                                {{
                                    method: 'POST',
                                    body: uploadFormData
                                }}
                            );
                            
                            if (!uploadResponse.ok) {{
                                throw new Error(`Failed to upload file: ${{uploadResponse.statusText}}`);
                            }}
                            
                            const uploadData = await uploadResponse.json();
                            console.log('File uploaded successfully:', uploadData);
                            
                            // Refresh the page to show the new file in the list
                            location.reload();
                        }} catch (err) {{
                            console.error('File upload error:', err);
                            alert(`Upload failed: ${{err.message}}`);
                        }}
                    }}
                }}
                """
            ),
        )
