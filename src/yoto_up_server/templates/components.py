"""
Reusable components for playlists.
"""

from pydom import Component
from pydom import html as d

from yoto_up.models import Chapter, Track
from yoto_up_server.templates.icon_components import LazyIconImg


class ChapterItem(Component):
    """List item for a chapter with collapsible tracks."""

    def __init__(
        self, chapter: Chapter, index: int, card_id: str = "", playlist_id: str = ""
    ):
        super().__init__()
        self.chapter = chapter
        self.index = index
        self.card_id = card_id
        self.playlist_id = playlist_id

    def render(self):
        # Handle both Chapter objects and dicts
        title = (
            self.chapter.title
            if hasattr(self.chapter, "title")
            else self.chapter.get("title", f"Chapter {self.index + 1}")
            if isinstance(self.chapter, dict)
            else f"Chapter {self.index + 1}"
        )

        # Try to get duration
        duration = 0
        if hasattr(self.chapter, "duration"):
            duration = self.chapter.duration or 0
        elif isinstance(self.chapter, dict):
            duration = self.chapter.get("duration") or 0

        # Format duration
        duration = duration or 0  # Ensure it's not None
        mins = int(duration // 60)
        secs = int(duration % 60)
        duration_str = f"{mins}:{secs:02d}"

        # Get tracks if available
        tracks = []
        if hasattr(self.chapter, "tracks") and self.chapter.tracks:
            tracks = self.chapter.tracks
        elif isinstance(self.chapter, dict) and "tracks" in self.chapter:
            tracks = self.chapter.get("tracks", [])

        # Build track items
        track_items = []
        if tracks:
            for track_idx, track in enumerate(tracks):
                track_items.append(
                    TrackItem(
                        track=track, chapter_index=self.index, track_index=track_idx
                    )
                )

        has_tracks = len(tracks) > 0

        return d.Li(classes="flex flex-col", **{"data-chapter-index": str(self.index)})(
            # Chapter item (expandable header)
            d.Div(
                classes="px-6 py-4 sm:px-8 hover:bg-indigo-50 flex items-center justify-between transition-colors group border-b border-gray-100"
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
                    name="chapter_id",
                    value=str(self.index),
                    data_chapter_id=self.index,
                ),
                # Chapter content with collapse/expand toggle
                d.Div(classes="flex items-center min-w-0 flex-1 gap-3")(
                    # Collapse/expand button (only if has tracks)
                    d.Button(
                        classes=f"flex-shrink-0 text-lg font-bold text-gray-600 hover:text-gray-900 transition-colors {'cursor-pointer' if has_tracks else 'invisible'} w-6 h-6 flex items-center justify-center",
                        id=f"toggle-btn-{self.index}",
                        onclick=f"toggleChapter({self.index})"
                        if has_tracks
                        else "event.preventDefault()",
                        type="button",
                    )(f"{'▼' if has_tracks else '▶'}"),
                    d.Div(
                        id=f"chapter-placeholder-{self.index}",
                        classes="flex-shrink-0 w-8 h-8 bg-gray-200 rounded flex items-center justify-center text-sm font-bold text-gray-600",
                    )(
                        LazyIconImg(icon_id=self.chapter.display.icon16x16.replace('#', '%23'))
                        if self.chapter.display and self.chapter.display.icon16x16
                        else d.Span()(str(self.index + 1))
                    ),
                    # Chapter title
                    d.Span(
                        classes="text-base text-gray-900 group-hover:text-indigo-700 transition-colors break-words font-semibold"
                    )(title),
                ),
                # Duration
                d.Span(classes="text-base text-gray-500 ml-4 flex-shrink-0")(
                    duration_str
                ),
            ),
            # Tracks (collapsible)
            d.Div(
                id=f"tracks-container-{self.index}",
                classes=f"bg-gray-50" + (" hidden" if not has_tracks else ""),
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

    def __init__(self, track: Track, chapter_index: int, track_index: int):
        super().__init__()
        self.track = track
        self.chapter_index = chapter_index
        self.track_index = track_index

    def render(self):
        # Handle both Track objects and dicts
        title = (
            self.track.title
            if hasattr(self.track, "title")
            else self.track.get("title", f"Track {self.track_index + 1}")
            if isinstance(self.track, dict)
            else f"Track {self.track_index + 1}"
        )

        # Try to get duration
        duration = 0
        if hasattr(self.track, "duration"):
            duration = self.track.duration or 0
        elif isinstance(self.track, dict):
            duration = self.track.get("duration") or 0

        # Format duration
        duration = duration or 0  # Ensure it's not None
        mins = int(duration // 60)
        secs = int(duration % 60)
        duration_str = f"{mins}:{secs:02d}"

        return d.Li(
            classes="px-8 py-3 sm:px-12 hover:bg-indigo-100 transition-colors flex items-center justify-between"
        )(
            # Track content
            d.Div(classes="flex items-center min-w-0 flex-1 gap-2")(
                # Track number/indicator
                d.Span(classes="text-xs font-semibold text-gray-400 min-w-[1.5rem]")(
                    "└─"
                ),
                # Track title
                d.Span(classes="text-sm text-gray-800 break-words")(title),
            ),
            # Duration
            d.Span(classes="text-sm text-gray-500 ml-4 flex-shrink-0")(duration_str),
        )
