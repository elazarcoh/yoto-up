"""
Reusable components for playlists.
"""

from pydom import Component
from pydom import html as d

from yoto_web_server.api.models import Chapter, Track
from yoto_web_server.templates.icon_components import LazyIconImg
from yoto_web_server.utils.sanitation import html_id_safe


class ChapterItem(Component):
    """List item for a chapter with collapsible tracks."""

    def __init__(
        self,
        *,
        chapter: Chapter,
        index: int,
        card_id: str = "",
        playlist_id: str = "",
        is_new: bool = False,
    ):
        super().__init__()
        self.chapter = chapter
        self.index = index
        self.card_id = card_id
        self.playlist_id = playlist_id
        self.is_new = is_new

    def render(self):
        # Handle both Chapter objects and dicts
        title = self.chapter.title

        # Try to get duration
        duration = 0
        duration = self.chapter.duration or 0

        # Format duration
        duration = duration or 0  # Ensure it's not None
        mins = int(duration // 60)
        secs = int(duration % 60)
        duration_str = f"{mins}:{secs:02d}"

        # Get tracks if available
        tracks = []
        tracks = self.chapter.tracks

        # Build track items
        track_items = []
        if tracks:
            for track_idx, track in enumerate(tracks):
                track_items.append(
                    TrackItem(track=track, chapter_index=self.index, track_index=track_idx)
                )

        has_tracks = len(tracks) > 0

        return d.Li(classes="flex flex-col")(
            # Chapter item (expandable header)
            d.Div(
                classes=f"px-6 py-4 sm:px-8 {'bg-green-50 hover:bg-green-100' if self.is_new else 'hover:bg-indigo-50'} flex items-center justify-between transition-colors group border-b border-gray-100"
            )(
                # Drag handle (indicates item is orderable)
                d.Div(
                    classes="flex-shrink-0 select-none cursor-grab active:cursor-grabbing text-gray-400 hover:text-gray-600 transition-colors mr-2",
                    title="Drag to reorder",
                )("⋮⋮"),
                # Checkbox (hidden by default, shown in edit mode)
                d.Input(
                    type="checkbox",
                    classes="mr-4 w-5 h-5 hidden accent-indigo-600 cursor-pointer",
                    name="chapter_ids",
                    value=str(self.index),
                    data_chapter_id=self.index,
                ),
                # Chapter content with collapse/expand toggle
                d.Div(classes="flex items-center min-w-0 flex-1 gap-3")(
                    # Collapse/expand button (only if has tracks)
                    d.Button(
                        classes=f"flex-shrink-0 text-lg font-bold text-gray-600 hover:text-gray-900 transition-colors {'cursor-pointer' if has_tracks else 'invisible'} w-6 h-6 flex items-center justify-center",
                        id=f"toggle-btn-{self.chapter.key}",
                        onclick=f"toggleChapter({self.index})"
                        if has_tracks
                        else "event.preventDefault()",
                        type="button",
                    )(f"{'▼' if has_tracks else '▶'}"),
                    # Icon container with overlay label on the left
                    d.Div(classes="flex-shrink-0 flex items-center gap-2")(
                        # Overlay label (if exists) - clickable to edit
                        d.Div(
                            id=f"overlay-label-{self.index}",
                            classes="w-6 h-8 bg-black bg-opacity-70 rounded flex items-center justify-center text-xs font-bold text-white cursor-pointer hover:bg-opacity-90 transition-all"
                            if self.chapter.overlay_label else
                            "w-6 h-8 bg-gray-300 hover:bg-gray-400 rounded flex items-center justify-center text-xs font-bold text-gray-600 cursor-pointer transition-all",
                            hx_get=f"/playlists/{self.playlist_id}/edit-overlay-label/{self.index}",
                            hx_target=f"#overlay-label-{self.index}",
                            hx_swap="outerHTML",
                            title="Click to add or edit label (max 3 characters)",
                        )(
                            self.chapter.overlay_label if self.chapter.overlay_label else "+"
                        ),
                        d.Button(
                            type="button",
                            id=f"chapter-placeholder-{html_id_safe(self.chapter.key)}",
                            classes="flex-shrink-0 w-8 h-8 bg-gray-200 rounded flex items-center justify-center text-sm font-bold text-gray-600 hover:ring-2 hover:ring-indigo-500 cursor-pointer p-0 border-0 overflow-hidden",
                            hx_get=f"/playlists/{self.playlist_id}/icon-sidebar?chapter_ids={self.index}",
                            hx_target="#icon-sidebar-container",
                            hx_swap="innerHTML",
                        )(
                            LazyIconImg(icon_id=self.chapter.display.icon_16x16.replace("#", "%23"))
                            if self.chapter.display and self.chapter.display.icon_16x16
                            else d.Span()
                        ),
                    ),
                    # Chapter title
                    d.Span(
                        classes="text-base text-gray-900 group-hover:text-indigo-700 transition-colors break-words font-semibold"
                    )(title),
                    d.Span(
                        classes="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800"
                    )("New")
                    if self.is_new
                    else None,
                ),
                # Duration
                d.Span(classes="text-base text-gray-500 ml-4 flex-shrink-0")(duration_str),
            ),
            # Tracks (collapsible)
            d.Div(
                id=f"tracks-container-{self.index}",
                classes="bg-gray-50" + (" hidden" if not has_tracks else ""),
            )(
                d.Ul(classes="divide-y divide-gray-200")(*track_items)
                if track_items
                else d.Div(classes="px-8 py-4 text-sm text-gray-500")("No tracks")
            )
            if has_tracks
            else "",
        )


class TrackItem(Component):
    """List item for a track within a chapter."""

    def __init__(self, *, track: Track, chapter_index: int, track_index: int):
        super().__init__()
        self.track = track
        self.chapter_index = chapter_index
        self.track_index = track_index

    def render(self):
        # Handle both Track objects and dicts
        title = self.track.title

        # Try to get duration
        duration = self.track.duration or 0

        # Format duration
        mins = int(duration // 60)
        secs = int(duration % 60)
        duration_str = f"{mins}:{secs:02d}"

        return d.Li(
            classes="px-8 py-3 sm:px-12 hover:bg-indigo-100 transition-colors flex items-center justify-between"
        )(
            # Track content
            d.Div(classes="flex items-center min-w-0 flex-1 gap-2")(
                # Track number/indicator
                d.Span(classes="text-xs font-semibold text-gray-400 min-w-[1.5rem]")("└─"),
                # Track title
                d.Span(classes="text-sm text-gray-800 break-words")(title),
            ),
            # Duration
            d.Span(classes="text-sm text-gray-500 ml-4 flex-shrink-0")(duration_str),
        )


class CoverModalPartial(Component):
    """Modal for updating playlist cover image."""

    def __init__(self, *, playlist_id: str):
        super().__init__()
        self.playlist_id = playlist_id

    def render(self):
        return d.Div(
            id="cover-modal",
            classes="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4",
        )(
            d.Div(classes="bg-white rounded-lg shadow-xl max-w-md w-full overflow-hidden relative")(
                # Loading Overlay
                d.Div(
                    id="cover-loading",
                    classes="htmx-indicator absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center z-10 pointer-events-none",
                )(
                    d.Div(
                        classes="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"
                    )()
                ),
                d.Div(
                    classes="px-6 py-4 border-b border-gray-200 flex justify-between items-center"
                )(
                    d.H3(classes="text-lg font-medium text-gray-900")("Change Cover Image"),
                    d.Button(
                        type="button",
                        classes="text-gray-400 hover:text-gray-500",
                        onclick="document.getElementById('cover-modal').remove()",
                    )("✕"),
                ),
                d.Form(
                    hx_post=f"/playlists/{self.playlist_id}/cover",
                    hx_encoding="multipart/form-data",
                    hx_target="#playlist-detail",  # Reload the whole detail view
                    hx_swap="outerHTML",
                    hx_indicator="#cover-loading",
                    classes="p-6 space-y-4",
                    **{
                        "hx-on::after-request": "if(event.detail.successful) document.getElementById('cover-modal').remove()"
                    },
                )(
                    d.Div(classes="space-y-2")(
                        d.Label(classes="block text-sm font-medium text-gray-700")("Upload Image"),
                        d.Input(
                            type="file",
                            name="cover",
                            accept="image/*",
                            classes="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100",
                            required=True,
                        ),
                    ),
                    d.Div(classes="flex justify-between items-center mt-6")(
                        d.Button(
                            type="button",
                            classes="text-red-600 hover:text-red-800 text-sm font-medium",
                            hx_delete=f"/playlists/{self.playlist_id}/cover",
                            hx_target="#playlist-detail",
                            hx_swap="outerHTML",
                            hx_indicator="#cover-loading",
                            hx_confirm="Are you sure you want to remove the cover image?",
                            **{
                                "hx-on::after-request": "if(event.detail.successful) document.getElementById('cover-modal').remove()"
                            },
                        )("Remove Cover"),
                        d.Div(classes="flex gap-3")(
                            d.Button(
                                type="button",
                                classes="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50",
                                onclick="document.getElementById('cover-modal').remove()",
                            )("Cancel"),
                            d.Button(
                                type="submit",
                                classes="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md hover:bg-indigo-700",
                            )("Upload"),
                        ),
                    ),
                ),
            ),
        )
