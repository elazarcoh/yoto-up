"""
Upload-related components for HTMX-driven file uploads.
"""

from typing import Optional

from pydom import Component
from pydom import html as d


class UploadModalPartial(Component):
    """Server-rendered upload modal - replaces JS-generated modal."""
    
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
                        **{"hx-on:click": "document.getElementById('upload-modal').classList.add('hidden')"}
                    )("✕"),
                ),
                
                # Upload form
                d.Form(
                    id="upload-form",
                    hx_post=f"/playlists/{self.playlist_id}/upload-items",
                    hx_encoding="multipart/form-data",
                    hx_target="#uploading-section",
                    hx_swap="innerHTML",
                    **{"hx-on::after-request": "if(event.detail.successful) { document.getElementById('upload-modal').classList.add('hidden'); document.getElementById('uploading-section').classList.remove('hidden'); }"}
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
                                **{"hx-on:change": "htmx.trigger('#file-preview', 'update-preview')"}
                            ),
                        ),
                        
                        # File preview
                        d.Div(
                            id="file-preview",
                            classes="max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-3 bg-gray-50",
                            **{"hx-on:update-preview": "updateFilePreview()"}
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
                            **{"hx-on:click": "document.getElementById('upload-modal').classList.add('hidden')"}
                        )("Cancel"),
                        d.Button(
                            type="submit",
                            classes="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
                        )("⬆️ Start Upload"),
                    ),
                ),
                
                # Inline script for file preview
                d.Script()("""
                    function updateFilePreview() {
                        const input = document.getElementById('file-input');
                        const preview = document.getElementById('file-preview');
                        if (!input.files || input.files.length === 0) {
                            preview.innerHTML = '<div class="text-sm text-gray-500 text-center py-2">No files selected</div>';
                            return;
                        }
                        const html = Array.from(input.files).map(file => {
                            const sizeMB = (file.size / 1024 / 1024).toFixed(2);
                            return `<div class="text-sm text-gray-700 py-1">📄 ${file.name} (${sizeMB} MB)</div>`;
                        }).join('');
                        preview.innerHTML = html;
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
    """Server-rendered upload progress display."""
    
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
                    d.P(classes="font-medium text-gray-900")("Processing..."),
                    d.Span(classes="inline-block mt-2 px-2 py-1 rounded text-xs font-medium bg-blue-200 text-blue-800")(
                        "Uploading"
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
                    classes="bg-blue-600 h-full transition-all duration-300",
                    style="width: 0%"
                )()
            ),
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
