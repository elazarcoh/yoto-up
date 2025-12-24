"""
Playlists templates.
"""

from typing import List

from pydom import Component
from pydom import html as d

from yoto_up.models import Card
from yoto_up_server.templates.components import ChapterItem, TrackItem
# Deprecated: old scripts-based approach
# from yoto_up_server.templates.scripts import get_playlist_scripts


class PlaylistsPage(Component):
    """Playlists page content."""
    
    def render(self):
        return d.Div()(
            d.Div(classes="flex justify-between items-center mb-6")(
                d.H1(classes="text-2xl font-bold text-gray-900")("Playlists"),
                d.A(
                    href="/upload/",
                    classes="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700"
                )("Upload New")
            ),
            # Filters
            d.Div(classes="bg-white p-6 rounded-lg shadow mb-8")(
                d.Form(
                    hx_get="/playlists/list",
                    hx_target="#playlist-list",
                    hx_trigger="submit",
                    hx_indicator="#list-loading",
                    classes="grid grid-cols-1 md:grid-cols-4 gap-4 items-end"
                )(
                    d.Div(classes="flex flex-col")(
                        d.Label(html_for="title-filter", classes="block text-sm font-medium text-gray-700")("Title"),
                        d.Input(
                            type="text",
                            name="title_filter",
                            id="title-filter",
                            placeholder="Filter by title...",
                            classes="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                        ),
                    ),
                    d.Div(classes="flex flex-col")(
                        d.Label(html_for="category-filter", classes="block text-sm font-medium text-gray-700")("Category"),
                        d.Select(
                            name="category",
                            id="category-filter",
                            classes="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                        )(
                            d.Option(value="")("All"),
                            d.Option(value="none")("None"),
                            d.Option(value="stories")("Stories"),
                            d.Option(value="music")("Music"),
                            d.Option(value="radio")("Radio"),
                            d.Option(value="podcast")("Podcast"),
                            d.Option(value="activities")("Activities"),
                        ),
                    ),
                    d.Button(
                        type="submit",
                        classes="w-full inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500",
                    )("Apply Filters"),
                    d.Button(
                        type="button",
                        classes="w-full inline-flex justify-center py-2 px-4 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500",
                        hx_get="/playlists/list",
                        hx_target="#playlist-list",
                        onclick="document.getElementById('title-filter').value=''; document.getElementById('category-filter').value='';"
                    )("Clear"),
                ),
            ),
            # Loading indicator
            d.Div(id="list-loading", classes="htmx-indicator flex items-center justify-center space-x-2 py-8")(
                d.Div(classes="animate-spin h-6 w-6 border-2 border-indigo-500 rounded-full border-t-transparent"),
                d.Span(classes="text-gray-500")("Loading playlists..."),
            ),
            # Playlist list container
            d.Div(
                id="playlist-list",
                hx_get="/playlists/list",
                hx_trigger="load",
                hx_indicator="#list-loading",
            ),
        )


class PlaylistListPartial(Component):
    """Partial for playlist list."""
    
    def __init__(self, cards: List[Card]):
        super().__init__()
        self.cards = cards
    
    def render(self):
        if not self.cards:
            return d.Div(classes="text-center py-12")(
                d.Div(classes="text-4xl mb-4")("📭"),
                d.P(classes="text-gray-500 text-lg")("No playlists found."),
            )
        
        return d.Div(classes="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-7 xl:grid-cols-8 gap-3")(
            *[_render_playlist_card(card) for card in self.cards]
        )


def _render_playlist_card(card: Card):
    """Render a single playlist card."""
    # Card objects use 'cardId' attribute
    card_id = card.cardId
    title = card.title or "Untitled"
    
    # Get category from metadata
    category = 'Uncategorized'
    if card.metadata:
        category = card.metadata.get('category', 'Uncategorized') if isinstance(card.metadata, dict) else getattr(card.metadata, 'category', 'Uncategorized') or 'Uncategorized'
    
    # Get cover image URL - try multiple sources
    cover_url = None
    
    # Try metadata.cover first
    if card.metadata:
        metadata = card.metadata if isinstance(card.metadata, dict) else card.metadata
        if isinstance(metadata, dict):
            cover_data = metadata.get('cover', {})
            if isinstance(cover_data, dict):
                cover_url = cover_data.get('imageL') or cover_data.get('imageM') or cover_data.get('imageS')
        else:
            # Try as object
            if hasattr(metadata, 'cover') and metadata.cover:
                cover = metadata.cover
                if hasattr(cover, 'imageL') and cover.imageL:
                    cover_url = cover.imageL
                elif hasattr(cover, 'imageM') and cover.imageM:
                    cover_url = cover.imageM
                elif hasattr(cover, 'imageS') and cover.imageS:
                    cover_url = cover.imageS
    
    # Count chapters and tracks (only available if card content was fully loaded)
    total_chapters = 0
    total_tracks = 0
    if card.content and hasattr(card.content, 'chapters') and card.content.chapters:
        total_chapters = len(card.content.chapters)
        for chapter in card.content.chapters:
            if hasattr(chapter, 'tracks') and chapter.tracks:
                total_tracks += len(chapter.tracks)
    
    return d.Div(classes="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow flex flex-col h-full")(
        d.Div(classes="aspect-square bg-gray-200 relative overflow-hidden group")(
            d.Img(src=cover_url, alt=title, classes="w-full h-full object-cover")
            if cover_url
            else d.Div(classes="w-full h-full flex items-center justify-center text-2xl text-gray-400")("🎵"),
            # Overlay with view button
            d.A(
                href=f"/playlists/{card_id}",
                classes="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100"
            )(
                d.Span(classes="bg-white/90 rounded-full p-2 shadow-lg text-indigo-600 text-sm")("👁️")
            ),
        ),
        d.Div(classes="p-2 flex-1 flex flex-col")(
            d.H3(classes="text-xs font-semibold text-gray-900 truncate", title=title)(title),
            d.P(classes="text-xs text-gray-500 capitalize mt-auto")(category),
        ),
        d.Div(classes="p-1 bg-gray-50 border-t border-gray-200 flex justify-between items-center gap-1")(
            d.A(
                href=f"/playlists/{card_id}",
                classes="flex-1 text-center text-xs text-indigo-600 hover:text-indigo-900 font-medium py-0.5"
            )("View"),
            d.Button(
                classes="text-xs text-red-600 hover:text-red-900 font-medium py-0.5 px-1",
                hx_delete=f"/playlists/{card_id}",
                hx_confirm="Delete this playlist?",
                hx_target="closest .bg-white",
                hx_swap="outerHTML",
            )("Delete"),
        ),
    )


class PlaylistCard(Component):
    """Card component for a single playlist."""
    
    def __init__(self, card):
        super().__init__()
        self.card = card
    
    def render(self):
        # Handle both Card objects and dicts
        card_id = self.card.id if hasattr(self.card, 'id') else self.card.get("id")
        title = self.card.title if hasattr(self.card, 'title') else self.card.get("title", "Untitled")
        
        # Get category from metadata
        if hasattr(self.card, 'metadata'):
            metadata = self.card.metadata or {}
            category = metadata.get('category', 'Uncategorized') if isinstance(metadata, dict) else 'Uncategorized'
        else:
            category = self.card.get("category", "Uncategorized")
        
        # Get cover image
        cover_url = None
        if hasattr(self.card, 'display'):
            display = self.card.display
            if display and hasattr(display, 'coverArtUri'):
                cover_url = display.coverArtUri
        if not cover_url:
            cover_url = self.card.get("cover_url") if isinstance(self.card, dict) else None
        
        return d.Div(classes="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow flex flex-col")(
            d.Div(classes="aspect-square bg-gray-200 relative overflow-hidden group")(
                d.Img(src=cover_url, alt=title, classes="w-full h-full object-cover")
                if cover_url
                else d.Div(classes="w-full h-full flex items-center justify-center text-4xl text-gray-400")("🎵"),
                # Overlay with view button
                d.A(
                    href=f"/playlists/{card_id}",
                    classes="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100"
                )(
                    d.Span(classes="bg-white/90 rounded-full p-3 shadow-lg text-indigo-600")("👁️")
                ),
            ),
            d.Div(classes="p-4 flex-1")(
                d.H3(classes="text-lg font-medium text-gray-900 truncate", title=title)(title),
                d.P(classes="text-sm text-gray-500 capitalize")(category),
            ),
            d.Div(classes="p-4 bg-gray-50 border-t border-gray-200 flex justify-between items-center")(
                d.A(
                    href=f"/playlists/{card_id}",
                    classes="text-indigo-600 hover:text-indigo-900 text-sm font-medium"
                )("View Details"),
                d.Button(
                    classes="text-red-600 hover:text-red-900 text-sm font-medium",
                    hx_delete=f"/playlists/{card_id}",
                    hx_confirm="Are you sure you want to delete this playlist?",
                    hx_target="closest .bg-white",  # Target the card itself
                    hx_swap="outerHTML",
                )("Delete"),
            ),
        )


class PlaylistDetailPartial(Component):
    """Partial for playlist details."""
    
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
            # Sortable.js library
            d.Script(src="https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js"),
            
            # Header
            d.Div(classes="mb-6")(
                d.A(href="/playlists/", classes="inline-flex items-center px-4 py-2 text-indigo-600 hover:text-indigo-900 hover:bg-indigo-50 rounded-md transition-colors")(
                    d.Span(classes="mr-2")("←"), "Back to Playlists"
                )
            ),
            
            # Main content with edit mode toggle
            d.Div(classes="bg-white shadow-lg rounded-lg overflow-hidden")(
                # Playlist Header
                d.Div(classes="px-6 py-8 sm:px-8 bg-gradient-to-r from-indigo-50 to-blue-50")(
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
                            d.Div(classes="mt-6 flex flex-col sm:flex-row gap-3")(
                                d.Button(
                                    id="edit-toggle-btn",
                                    classes="inline-flex items-center justify-center px-6 py-2 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 transition-colors",
                                    onclick="toggleEditMode()"
                                )("✏️ Edit"),
                                d.Button(
                                    classes="inline-flex items-center justify-center px-6 py-2 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors",
                                    onclick="openUploadModal()"
                                )("⬆️ Upload Items"),
                                d.Button(classes="inline-flex items-center justify-center px-6 py-2 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors")("🖼️ Change Cover"),
                                d.Button(
                                    classes="inline-flex items-center justify-center px-6 py-2 border border-gray-300 shadow-sm text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors",
                                    onclick="displayJsonModal()"
                                )("📋 Display JSON"),
                            ),
                        ),
                    ),
                ),
                
                # Uploading Section (shows active uploads)
                d.Div(id="uploading-section", classes="border-t border-gray-200 hidden")(
                    d.Div(classes="px-6 py-6 sm:px-8")(
                        d.H3(classes="text-xl leading-6 font-bold text-gray-900 mb-4")("⬆️ Uploading"),
                        d.Div(id="uploading-files-list", classes="space-y-3"),
                    ),
                ),
                
                # Chapters/Items Section
                d.Div(classes="border-t border-gray-200")(
                    d.Div(classes="px-6 py-6 sm:px-8")(
                        d.Div(classes="flex justify-between items-center mb-3 flex-wrap gap-2")(
                            d.H3(classes="text-xl leading-6 font-bold text-gray-900")("Items"),
                            d.Div(id="tree-controls", classes="flex gap-2")(
                                d.Button(classes="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors", onclick="collapseAll()", title="Collapse all chapters")("⊖ Collapse All"),
                                d.Button(classes="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors", onclick="expandAll()", title="Expand all chapters")("⊕ Expand All"),
                            ),
                            d.Div(id="edit-controls" , classes="hidden flex gap-2")(
                                d.Button(classes="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors", onclick="selectAllChapters()", title="Select all items")("✓ Select All"),
                                d.Button(classes="px-3 py-1 text-sm bg-blue-400 text-white rounded hover:bg-blue-500 transition-colors", onclick="invertSelection()", title="Invert selection")("⟲ Invert"),
                                d.Button(classes="px-3 py-1 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition-colors", title="Delete selected items")("🗑️ Delete Selected"),
                                d.Button(id="batch-edit-icons-btn", classes="px-3 py-1 text-sm bg-purple-500 text-white rounded hover:bg-purple-600 transition-colors", onclick="openBatchIconEdit()", title="Edit icons for selected items")("🎨 Edit Icons"),
                            ),
                        ),
                    ),
                    d.Ul(id="chapters-list", classes="divide-y divide-gray-100")(
                        *[ChapterItem(chapter=chapter, index=i, card_id=self.card.cardId) for i, chapter in enumerate(chapters)]
                    ) if chapters else d.Div(classes="px-6 py-8 sm:px-8 text-center text-gray-500")("No items found."),
                ),
            ),
            
            # Edit Icon Sidebar (hidden by default)
            d.Div(id="icon-sidebar" , classes="hidden fixed right-0 top-0 h-screen w-96 bg-white shadow-2xl z-50 overflow-y-auto")(
                d.Div(classes="p-6 flex flex-col h-full")(
                    d.Div(classes="flex justify-between items-center mb-4")(
                        d.H3(classes="text-xl font-bold text-gray-900")("Edit Icons"),
                        d.Button(
                            classes="text-gray-500 hover:text-gray-700 text-2xl",
                            onclick="closeIconSidebar()"
                        )("✕"),
                    ),
                    d.Div(classes="mb-4 flex gap-2")(
                        d.Input(
                            type="text",
                            id="icon-search",
                            placeholder="Search icons...",
                            classes="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500",
                        ),
                        d.Button(
                            id="icon-search-btn",
                            classes="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium",
                            type="button"
                        )("🔍 Search"),
                    ),
                    d.Div(id="icons-grid", classes="grid grid-cols-4 gap-2 flex-1 overflow-y-auto")(
                        # Icons will be loaded dynamically
                    ),
                ),
            ),
            
            # Edit mode overlay
            d.Div(id="edit-overlay", classes="hidden fixed inset-0 bg-black bg-opacity-50 z-40", onclick="if(sidebarOpen) closeIconSidebar();"),
            
            # Upload modal
            d.Div(id="upload-modal", classes="hidden fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4")(
                d.Div(classes="bg-white rounded-lg shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto")(
                    # Modal header
                    d.Div(classes="sticky top-0 px-6 py-4 border-b border-gray-200 bg-white flex justify-between items-center")(
                        d.H3(classes="text-2xl font-bold text-gray-900")("Upload Items"),
                        d.Button(
                            classes="text-gray-500 hover:text-gray-700 text-2xl",
                            onclick="closeUploadModal()"
                        )("✕"),
                    ),
                    
                    # Modal content
                    d.Div(classes="px-6 py-6 space-y-6")(
                        # File selection section
                        d.Div(classes="space-y-3")(
                            d.Label(classes="block text-sm font-semibold text-gray-900")("Files & Folders"),
                            d.Div(classes="flex gap-3")(
                                d.Button(
                                    id="upload-files-btn",
                                    classes="flex-1 px-4 py-3 border-2 border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium",
                                    onclick="selectFiles()"
                                )("📁 Select Files"),
                                d.Button(
                                    id="upload-folder-btn",
                                    classes="flex-1 px-4 py-3 border-2 border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors font-medium",
                                    onclick="selectFolder()"
                                )("📂 Select Folder"),
                            ),
                            # Hidden file input
                            d.Input(
                                type="file",
                                id="file-input",
                                multiple="true",
                                classes="hidden",
                                accept="audio/*"
                            ),
                        ),
                        
                        # Selected files preview
                        d.Div(classes="space-y-2")(
                            d.Label(classes="block text-sm font-semibold text-gray-900")("Selected Files"),
                            d.Div(
                                id="files-list",
                                classes="max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-3 bg-gray-50 space-y-1"
                            )(
                                d.Div(classes="text-sm text-gray-500 text-center py-2")("No files selected")
                            ),
                        ),
                        
                        # Upload mode
                        d.Div(classes="space-y-2")(
                            d.Label(classes="block text-sm font-semibold text-gray-900")("Upload As"),
                            d.Div(classes="flex gap-4")(
                                d.Label(classes="flex items-center cursor-pointer")(
                                    d.Input(
                                        type="radio",
                                        name="upload-mode",
                                        value="chapters",
                                        checked="true",
                                        classes="w-4 h-4 accent-indigo-600"
                                    ),
                                    d.Span(classes="ml-2 text-sm text-gray-700")("Chapters"),
                                ),
                                d.Label(classes="flex items-center cursor-pointer")(
                                    d.Input(
                                        type="radio",
                                        name="upload-mode",
                                        value="tracks",
                                        classes="w-4 h-4 accent-indigo-600"
                                    ),
                                    d.Span(classes="ml-2 text-sm text-gray-700")("Tracks"),
                                ),
                            ),
                        ),
                        
                        # Normalization section
                        d.Div(classes="space-y-3 p-4 bg-gray-50 rounded-lg border border-gray-200")(
                            d.Label(classes="flex items-center cursor-pointer gap-2")(
                                d.Input(
                                    type="checkbox",
                                    id="normalize-checkbox",
                                    classes="w-4 h-4 accent-indigo-600"
                                ),
                                d.Span(classes="text-sm font-semibold text-gray-900")("Normalize Audio"),
                            ),
                            d.Div(id="normalize-options", classes="hidden space-y-3 pl-6")(
                                d.Div(classes="space-y-2")(
                                    d.Label(classes="block text-sm text-gray-700")("Target LUFS"),
                                    d.Input(
                                        type="number",
                                        id="target-lufs",
                                        value="-23.0",
                                        step="0.1",
                                        classes="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                                    ),
                                ),
                                d.Label(classes="flex items-center cursor-pointer gap-2")(
                                    d.Input(
                                        type="checkbox",
                                        id="normalize-batch",
                                        classes="w-4 h-4 accent-indigo-600"
                                    ),
                                    d.Span(classes="text-sm text-gray-700")("Batch mode (Album normalization)"),
                                ),
                            ),
                        ),
                        
                        # Analysis section
                        d.Div(classes="space-y-3 p-4 bg-gray-50 rounded-lg border border-gray-200")(
                            d.Label(classes="flex items-center cursor-pointer gap-2")(
                                d.Input(
                                    type="checkbox",
                                    id="analyze-intro-outro-checkbox",
                                    classes="w-4 h-4 accent-indigo-600"
                                ),
                                d.Span(classes="text-sm font-semibold text-gray-900")("Analyze Intro/Outro"),
                            ),
                            d.Div(id="analysis-options", classes="hidden space-y-3 pl-6")(
                                d.Div(classes="space-y-2")(
                                    d.Label(classes="block text-sm text-gray-700")("Segment Seconds"),
                                    d.Input(
                                        type="number",
                                        id="segment-seconds",
                                        value="10.0",
                                        step="0.5",
                                        classes="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                                    ),
                                ),
                                d.Div(classes="space-y-2")(
                                    d.Label(classes="block text-sm text-gray-700")("Similarity Threshold"),
                                    d.Input(
                                        type="number",
                                        id="similarity-threshold",
                                        value="0.75",
                                        step="0.05",
                                        min="0",
                                        max="1",
                                        classes="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                                    ),
                                ),
                            ),
                        ),
                        
                        # Show waveform option
                        d.Label(classes="flex items-center cursor-pointer gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200")(
                            d.Input(
                                type="checkbox",
                                id="show-waveform-checkbox",
                                classes="w-4 h-4 accent-indigo-600"
                            ),
                            d.Span(classes="text-sm font-semibold text-gray-900")("Show waveform visualization"),
                        ),
                    ),
                    
                    # Modal footer
                    d.Div(classes="sticky bottom-0 px-6 py-4 border-t border-gray-200 bg-white flex justify-end gap-3")(
                        d.Button(
                            classes="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium",
                            onclick="closeUploadModal()"
                        )("Cancel"),
                        d.Button(
                            id="start-upload-btn",
                            classes="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium disabled:bg-gray-400 disabled:cursor-not-allowed",
                            onclick="startUpload()"
                        )("⬆️ Start Upload"),
                    ),
                ),
            ),
            
            # JSON Display Modal
            d.Div(id="json-modal", classes="hidden fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4")(
                d.Div(classes="bg-white rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto")(
                    # Modal header
                    d.Div(classes="sticky top-0 px-6 py-4 border-b border-gray-200 bg-white flex justify-between items-center")(
                        d.H3(classes="text-2xl font-bold text-gray-900")("Playlist JSON"),
                        d.Div(classes="flex gap-2")(
                            d.Button(
                                classes="px-3 py-1 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-medium",
                                onclick="copyJsonToClipboard()"
                            )("📋 Copy"),
                            d.Button(
                                classes="text-gray-500 hover:text-gray-700 text-2xl",
                                onclick="closeJsonModal()"
                            )("✕"),
                        ),
                    ),
                    
                    # Modal content
                    d.Div(classes="px-6 py-6")(
                        d.Pre(
                            id="json-content",
                            classes="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm font-mono max-h-[70vh] overflow-y-auto"
                        )(),
                    ),
                ),
            ),
        )