"""
Session edit components for advanced upload flow.

Provides UI components for editing file metadata during advanced uploads.
"""

from pydom import Component
from pydom import html as d

from yoto_web_server.models import UploadSession


class SessionFileListPartial(Component):
    """List of files in an upload session with click handlers."""

    def __init__(self, *, session: UploadSession):
        super().__init__()
        self.session = session

    def render(self):
        return d.Div(
            id="session-files-list",
            classes="space-y-2",
        )(
            *[
                d.Button(
                    type="button",
                    id=f"file-{file.file_id}",
                    classes="w-full text-left px-4 py-3 border border-gray-200 rounded-lg hover:bg-indigo-50 hover:border-indigo-300 transition-colors",
                    hx_get=f"/playlists/{self.session.playlist_id}/upload-session/{self.session.session_id}/file/{file.file_id}/edit",
                    hx_target="#session-file-editor",
                    hx_swap="innerHTML",
                )(
                    d.Div(classes="flex justify-between items-start")(
                        d.Div(classes="flex-1")(
                            d.Div(classes="text-sm font-semibold text-gray-900")(file.filename),
                            d.Div(classes="text-xs text-gray-500 mt-1")(
                                f"Size: {file.size_bytes / (1024 * 1024):.1f} MB"
                            ),
                        ),
                        d.Div(
                            classes="flex-shrink-0",
                        )(
                            d.Span(
                                classes="inline-block px-2 py-1 text-xs font-semibold rounded-full "
                                + (
                                    "bg-yellow-100 text-yellow-800"
                                    if file.status.value == "pending"
                                    else "bg-blue-100 text-blue-800"
                                    if file.status.value in ["uploading_local", "uploading"]
                                    else "bg-green-100 text-green-800"
                                    if file.status.value == "done"
                                    else "bg-red-100 text-red-800"
                                ),
                            )(file.status.value),
                        ),
                    ),
                )
                for file in self.session.files
            ]
            if self.session.files
            else [d.Div(classes="text-center py-8 text-gray-500")("No files uploaded yet")]
        )


class SessionFileEditorPartial(Component):
    """File editor panel showing metadata for a single file."""

    def __init__(self, *, session: UploadSession, file_id: str):
        super().__init__()
        self.session = session
        self.file_id = file_id
        self.file = next(
            (f for f in session.files if f.file_id == file_id),
            None,
        )

    def render(self):
        if not self.file:
            return d.Div(classes="text-center py-8 text-gray-500")("File not found")

        return d.Div(
            id="session-file-editor",
            classes="border border-gray-200 rounded-lg p-6 bg-gray-50",
        )(
            # File header
            d.Div(classes="mb-6 pb-6 border-b border-gray-200")(
                d.H3(classes="text-lg font-semibold text-gray-900")(
                    f"Editing: {self.file.filename}"
                ),
                d.P(classes="text-sm text-gray-600 mt-2")(
                    f"Size: {self.file.size_bytes / (1024 * 1024):.1f} MB"
                ),
            ),
            # Edit form
            d.Form(
                id="file-edit-form",
                hx_post=f"/playlists/{self.session.playlist_id}/upload-session/{self.session.session_id}/file/{self.file_id}/update",
                hx_target="#session-file-editor",
                hx_swap="innerHTML",
                classes="space-y-4",
            )(
                # Title field
                d.Div(classes="space-y-2")(
                    d.Label(
                        htmlFor="file-title",
                        classes="block text-sm font-medium text-gray-900",
                    )("Title"),
                    d.Input(
                        id="file-title",
                        type="text",
                        name="title",
                        value=self.file.custom_title
                        or self.file.filename.rsplit(".", 1)[0],  # Use custom_title if set
                        classes="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500",
                        placeholder="Enter file title",
                    ),
                    d.P(classes="text-xs text-gray-500 mt-1")(
                        "This will be used as the chapter/track title"
                    ),
                ),
                # Button group
                d.Div(classes="flex gap-3 pt-4")(
                    d.Button(
                        type="submit",
                        classes="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium",
                    )("💾 Save Changes"),
                    d.Button(
                        type="button",
                        classes="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors",
                        onclick="document.getElementById('session-file-editor').innerHTML = ''",
                    )("Cancel"),
                ),
            ),
        )
