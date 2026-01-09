"""
Refactored playlist detail component using HTMX patterns.
This replaces the JS-heavy version with server-side rendering.
"""

from pydom import Component
from pydom import html as d

from yoto_web_server.api.models import Card
from yoto_web_server.templates.htmx_helpers import (
    ClipboardCopyScript,
    FilePickerScript,
    SortableInitScript,
    ToastNotificationSystem,
    ToggleClassScript,
)
from yoto_web_server.templates.playlist_components import ChapterItem
from yoto_web_server.templates.upload_components import ActiveUploadsSection
from yoto_web_server.utils.alpine import xon


class PlaylistDetail(Component):
    """Refactored playlist detail page using HTMX principles."""

    def __init__(self, *, card: Card, playlist_id: str = "", new_chapters: list[str] | None = None):
        super().__init__()
        self.card = card
        self.playlist_id = playlist_id
        self.new_chapters = new_chapters or []

    def render(self):
        title = self.card.title or "Untitled"
        description = ""
        cover_url = None

        # Get cover from metadata
        if self.card.metadata:
            description = getattr(self.card.metadata, "description", "")
            cover = getattr(self.card.metadata, "cover", None)
            if cover:
                cover_url = getattr(cover, "image_l", None)

        # Get chapters from card content if available
        chapters = []
        if hasattr(self.card, "content") and self.card.content:
            content = self.card.content
            if hasattr(content, "chapters") and content.chapters:
                chapters = content.chapters

        return d.Div(
            classes="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8",
            id="playlist-detail",
            data_playlist_id=self.card.card_id,
        )(
            # Include necessary JavaScript libraries and helpers
            d.Script(src="https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js"),
            SortableInitScript(
                list_id="chapters-list",
                save_endpoint=f"/playlists/{self.card.card_id}/reorder-chapters",
                handle_class="drag-handle",
            ),
            FilePickerScript(),
            ToggleClassScript(),
            ClipboardCopyScript(
                source_id="json_content", success_message="JSON copied to clipboard!"
            ),
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
                d.A(
                    href="/playlists/",
                    classes="inline-flex items-center px-4 py-2 text-indigo-600 hover:text-indigo-900 hover:bg-indigo-50 rounded-md transition-colors",
                )(d.Span(classes="mr-2")("←"), "Back to Playlists")
            ),
            # Main content
            d.Div(classes="bg-white shadow-lg rounded-lg overflow-hidden")(
                # Header section
                self._render_header(title, description, cover_url),
                # Active uploads section
                ActiveUploadsSection(playlist_id=self.card.card_id),
                # Chapters/Items section
                self._render_chapters_section(chapters),
            ),
            # Modals and overlays (hidden by default, shown via HTMX)
            d.Div(id="edit-overlay", classes="hidden fixed inset-0 bg-black bg-opacity-50 z-40"),
            # Upload modal placeholder (loaded via HTMX when needed)
            d.Div(id="upload-modal-container")(),
            # JSON modal placeholder (loaded via HTMX when needed)
            d.Div(id="json-modal-container")(),
            # Icon Sidebar Container
            d.Div(id="icon-sidebar-container"),
            # Overlay for sidebar
            d.Div(
                id="edit-overlay",
                classes="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity hidden z-40",
                onclick="closeIconSidebar()",
            ),
        )

    def _render_header(self, title: str, description: str, cover_url: str | None):
        """Render playlist header with cover and actions."""
        return d.Div(classes="px-6 py-8 sm:px-8 bg-gradient-to-r from-indigo-50 to-blue-50")(
            d.Div(classes="flex flex-col sm:flex-row gap-8")(
                # Cover Image
                d.Div(classes="flex-shrink-0")(
                    d.Img(
                        src=cover_url,
                        alt=title,
                        classes="h-56 w-56 object-cover rounded-lg shadow-md border-2 border-gray-100",
                    )
                    if cover_url
                    else d.Div(
                        classes="h-56 w-56 bg-gradient-to-br from-indigo-100 to-indigo-50 rounded-lg flex items-center justify-center text-6xl shadow-md border-2 border-gray-100"
                    )("🎵")
                ),
                # Title and Actions
                d.Div(classes="flex-1 flex flex-col justify-between")(
                    d.Div()(
                        d.H2(classes="text-3xl font-bold text-gray-900 mb-2")(title),
                        d.P(classes="text-base text-gray-600 leading-relaxed max-w-2xl")(
                            description
                        )
                        if description
                        else "",
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
                hx_get=f"/playlists/{self.card.card_id}/toggle-edit-mode?enable=true",
                hx_target="#edit-controls-container",
                hx_swap="innerHTML",
            )("✏️ Edit"),
            # Quick upload button - loads upload modal via HTMX
            d.Button(
                classes="inline-flex items-center justify-center px-6 py-2 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors",
                hx_get=f"/playlists/{self.card.card_id}/upload-modal",
                hx_target="#upload-modal-container",
                hx_swap="innerHTML",
                hx_on__after_request="document.getElementById('upload-modal-container').classList.remove('hidden')",
            )("⬆️ Quick Upload"),
            # Advanced upload button - creates session and redirects
            d.Button(
                classes="inline-flex items-center justify-center px-6 py-2 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors",
                hx_post=f"/playlists/{self.card.card_id}/advanced-upload-session",
                hx_on__after_request="const response = event.detail.xhr.response; const data = JSON.parse(response); window.location.href = data.redirect;",
            )("⬆️ Advanced Upload"),
            # Change cover - would load cover selection modal
            d.Button(
                classes="inline-flex items-center justify-center px-6 py-2 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors",
                hx_get=f"/playlists/{self.card.card_id}/cover-modal",
                hx_target="body",
                hx_swap="beforeend",
            )("🖼️ Change Cover"),
            # Display JSON - loads JSON modal via HTMX
            d.Button(
                classes="inline-flex items-center justify-center px-6 py-2 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors",
                hx_get=f"/playlists/{self.card.card_id}/json-modal",
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
                            title="Collapse all chapters",
                        )("⊖ Collapse All"),
                        d.Button(
                            classes="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors",
                            onclick="expandAll()",
                            title="Expand all chapters",
                        )("⊕ Expand All"),
                    ),
                    # Edit controls - loaded dynamically via HTMX when edit mode is enabled
                    d.Div(id="edit-controls-container")(),
                ),
            ),
            # Chapters list - draggable via Sortable.js
            d.Ul(
                id="chapters-list",
                classes="divide-y divide-gray-100",
            )(
                *[
                    ChapterItem(
                        chapter=chapter,
                        index=i,
                        card_id=self.card.card_id,
                        playlist_id=self.playlist_id,
                        is_new=str(i) in self.new_chapters,
                    )
                    for i, chapter in enumerate(chapters)
                ]
            )
            if chapters
            else d.Div(classes="px-6 py-8 sm:px-8 text-center text-gray-500")("No items found."),
        )


class EditControlsPartial(Component):
    """Edit mode controls - shown when edit mode is active."""

    def __init__(self, *, playlist_id: str, edit_mode_active: bool = True):
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
                    **xon().click(
                        "document.querySelectorAll('#chapters-list input[type=checkbox]').forEach(cb => cb.checked = true)"
                    ),
                    title="Select all items",
                )("✓ Select All"),
                # Invert selection
                d.Button(
                    classes="px-3 py-1 text-sm bg-blue-400 text-white rounded hover:bg-blue-500 transition-colors",
                    type="button",
                    **xon().click(
                        "document.querySelectorAll('#chapters-list input[type=checkbox]').forEach(cb => cb.checked = !cb.checked)"
                    ),
                    title="Invert selection",
                )("⟲ Invert"),
                # Set Icon for selected
                d.Button(
                    classes="px-3 py-1 text-sm bg-indigo-500 text-white rounded hover:bg-indigo-600 transition-colors",
                    hx_get=f"/playlists/{self.playlist_id}/icon-sidebar",
                    hx_include="[data-chapter-id]:checked",
                    hx_target="#icon-sidebar-container",
                    hx_swap="innerHTML",
                    title="Set icon for selected items",
                )("🖼️ Set Icon"),
                # Re-number chapters
                d.Button(
                    classes="px-3 py-1 text-sm bg-orange-500 text-white rounded hover:bg-orange-600 transition-colors",
                    hx_post=f"/playlists/{self.playlist_id}/renumber-chapters",
                    hx_confirm="Re-number chapters by their order?",
                    hx_target="#chapters-list",
                    hx_swap="innerHTML",
                    title="Auto-number chapters sequentially",
                )("🔢 Re-number"),
                # Delete selected
                d.Button(
                    classes="px-3 py-1 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition-colors",
                    hx_post=f"/playlists/{self.playlist_id}/delete-selected",
                    hx_confirm="Delete selected items?",
                    hx_include="[data-chapter-id]:checked",
                    hx_target="#chapters-list",
                    hx_swap="innerHTML",
                    title="Delete selected items",
                )("🗑️ Delete Selected"),
                # Cancel button - exits edit mode
                d.Button(
                    classes="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors",
                    hx_get=f"/playlists/{self.playlist_id}/toggle-edit-mode?enable=false",
                    hx_target="#edit-controls-container",
                    hx_swap="innerHTML",
                    title="Cancel edit mode",
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
            ),
        )
