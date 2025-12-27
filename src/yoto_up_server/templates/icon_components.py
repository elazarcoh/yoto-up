"""
Icon-related components and partials for HTMX.
"""

from typing import List, Optional
import json

from pydom import Component
from pydom import html as d


class IconGridPartial(Component):
    """Server-rendered icon grid for selection via HTMX form submission."""

    def __init__(
        self,
        icons: List[dict],
        title: str = "Icons",
    ):
        super().__init__()
        self.icons = icons
        self.title = title

    def render(self):
        if not self.icons:
            return d.Div(classes="col-span-4 p-4 text-center text-gray-500")(
                "No icons found"
            )

        return d.Fragment()(
            d.Div(classes="col-span-4 mb-4")(
                d.H4(classes="font-semibold text-gray-700")(
                    f"{self.title} ({len(self.icons)})"
                )
            ),
            *[self._render_icon(icon) for icon in self.icons],
        )

    def _render_icon(self, icon: dict):
        """Render a single icon as a submit button in a form."""
        icon_id = icon.get("mediaId") or icon.get("id")
        title = icon.get("title", "Untitled")
        thumbnail = icon.get("thumbnail")

        thumbnail_html = (
            d.Img(
                src=thumbnail, alt=title, classes="w-full h-full object-cover rounded"
            )
            if thumbnail
            else d.Div(
                classes="w-full h-full bg-gray-200 rounded flex items-center justify-center text-xs text-gray-400"
            )("No image")
        )

        return d.Button(
            classes="w-16 h-16 rounded border-2 border-gray-200 hover:border-indigo-500 hover:shadow-lg transition-all cursor-pointer flex items-center justify-center",
            title=title,
            type="submit",
            name="icon_id",
            value=icon_id,
        )(thumbnail_html)


class IconSidebarPartial(Component):
    """Server-rendered icon sidebar with HTMX form submission."""

    def __init__(
        self,
        playlist_id: str,
        chapter_ids: Optional[List[int]] = None,
        track_ids: Optional[List[int]] = None,
    ):
        super().__init__()
        self.playlist_id = playlist_id
        self.chapter_ids = chapter_ids or []
        self.track_ids = track_ids or []

    def render(self):
        return d.Form(
            id="icon-assignment-form",
            hx_post=f"/playlists/{self.playlist_id}/update-chapter-icon",
            hx_target="#playlist-detail",
            hx_swap="outerHTML",
            classes="fixed right-0 top-0 h-screen w-96 bg-white shadow-2xl z-50 overflow-y-auto flex flex-col",
        )(
            # Hidden inputs for chapter and track IDs (will be sent as form data)
            *[
                d.Input(type="hidden", name="chapter_id", value=str(ch_id))
                for ch_id in self.chapter_ids
            ],
            *[
                d.Input(type="hidden", name="track_id", value=str(tr_id))
                for tr_id in self.track_ids
            ],
            # Header
            d.Div(
                classes="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center z-10"
            )(
                d.H3(classes="text-xl font-bold text-gray-900")(
                    f"Select Icon ({len(self.chapter_ids) + len(self.track_ids)} items)"
                ),
                d.Button(
                    classes="text-gray-500 hover:text-gray-700 text-2xl",
                    type="button",
                    id="close-icon-sidebar-btn",
                )("✕"),
            ),
            # Search
            d.Div(classes="px-6 py-4 bg-gray-50 border-b border-gray-200")(
                d.Div(classes="flex gap-2")(
                    d.Input(
                        type="text",
                        id="icon-search-input",
                        name="query",
                        placeholder="Search icons...",
                        classes="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500",
                        hx_get="/icons/grid",
                        hx_trigger="keyup changed delay:500ms",
                        hx_target="#icons-grid",
                        hx_include="[name='query']",
                        hx_indicator="#search-indicator",
                    ),
                    d.Div(
                        id="search-indicator",
                        classes="htmx-indicator flex items-center",
                    )(
                        d.Div(
                            classes="animate-spin h-5 w-5 border-2 border-indigo-500 rounded-full border-t-transparent"
                        )
                    ),
                ),
                d.Div(classes="mt-2 flex gap-2")(
                    d.Button(
                        classes="text-sm text-indigo-600 hover:text-indigo-900",
                        type="button",
                        hx_get="/icons/grid?source=user&limit=100",
                        hx_target="#icons-grid",
                        hx_swap="innerHTML",
                    )("My Icons"),
                    d.Button(
                        classes="text-sm text-indigo-600 hover:text-indigo-900",
                        type="button",
                        hx_get="/icons/grid?source=yotoicons&limit=50",
                        hx_target="#icons-grid",
                        hx_swap="innerHTML",
                    )("Yoto Icons"),
                ),
            ),
            # Icons grid container - flex-grow to fill remaining space
            d.Div(
                id="icons-grid",
                classes="flex-1 overflow-y-auto px-6 py-4 grid grid-cols-4 gap-3",
                hx_get="/icons/grid?source=user&limit=100",
                hx_trigger="load",
                hx_swap="innerHTML",
            )(),
            # Script to handle sidebar interactions
            d.Script()("""//js
            // Helper function to close icon sidebar
            function closeIconSidebar() {
                const overlay = document.getElementById('edit-overlay');
                const sidebar = document.getElementById('icon-sidebar-container');
                if(overlay) overlay.classList.add('hidden');
                if(sidebar) sidebar.innerHTML = '';
            }
            
            // Add event listener to close button
            document.addEventListener('DOMContentLoaded', function() {
                const closeBtn = document.getElementById('close-icon-sidebar-btn');
                if(closeBtn) {
                    closeBtn.addEventListener('click', closeIconSidebar);
                }
            });
            
            // Listen for successful form submissions
            document.addEventListener('htmx:afterRequest', function(event) {
                if(event.detail.target && event.detail.target.id === 'icon-assignment-form') {
                    if(event.detail.xhr.status === 200) {
                        // Form submitted successfully, close the sidebar
                        closeIconSidebar();
                    }
                }
            });
            """),
        )


class IconSearchResultsPartial(Component):
    """Partial for icon search results."""

    def __init__(
        self,
        icons: List[dict],
        query: str,
    ):
        super().__init__()
        self.icons = icons
        self.query = query

    def render(self):
        if not self.icons:
            return d.Div(classes="col-span-4 p-4 text-center text-gray-500")(
                f'No icons found for "{self.query}"'
            )

        return IconGridPartial(
            icons=self.icons,
            title=f"Search Results ({len(self.icons)})",
        ).render()


class IconImg(Component):
    """
    Icon image component with lazy loading via HTMX.

    Renders an <img> element for a Yoto icon.
    This is the ph2 (placeholder 2) - the actual icon returned by the fetch route.
    """

    def __init__(
        self,
        icon_id: str,
        src: str,
        title: str = "Icon",
        classes: str = "w-6 h-6",
    ):
        super().__init__()
        self.icon_id = icon_id
        self.src = src
        self.title = title
        self.classes = classes

    def render(self):
        # For now, return a placeholder. Once Yoto API supports icon fetching,
        # we can construct the actual URL or base64 data
        return d.Img(
            src=self.src,
            alt=self.title,
            title=self.title,
            classes=self.classes,
            loading="lazy",
        )


class LazyIconImg(Component):
    """
    Lazy-loaded icon image with HTMX loading state.

    Renders an initial placeholder (ph1) with HTMX hx-load trigger.
    On load, HTMX fetches from /icons/{icon_id} which returns an IconImg (ph2).
    """

    def __init__(
        self,
        icon_id: str,
        title: str = "Icon",
        classes: str = "w-6 h-6",
        container_id: Optional[str] = None,
    ):
        super().__init__()
        self.icon_id = icon_id
        self.title = title
        self.classes = classes
        self.container_id = container_id or f"icon-{icon_id.replace('#', '')}"

    def render(self):
        # ph1 (placeholder 1) - loading state
        # This will be replaced by ph2 once the icon is loaded
        loading_placeholder = d.Img(
            src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ccircle cx='12' cy='12' r='10' fill='%23e5e7eb' opacity='0.5'/%3E%3C/svg%3E",
            alt=f"{self.title} (loading)",
            title=f"{self.title} (loading)",
            classes=f"{self.classes} animate-pulse",
        )

        # Container with HTMX load trigger
        return d.Div(
            id=self.container_id,
            hx_get=f"/icons/{self.icon_id}",
            hx_trigger="load",
            hx_swap="outerHTML",
            classes="inline-block",
        )(loading_placeholder)


class LoadingIconIndicator(Component):
    """Indicator component for loading icon states (used with HTMX)."""

    def __init__(self, media_id: str, status: str = "loading"):
        super().__init__()
        self.media_id = media_id
        self.status = status  # "loading", "error", "not_found"

    def render(self):
        if self.status == "loading":
            return d.Div(
                classes="w-6 h-6 flex items-center justify-center",
                title="Loading icon...",
            )(
                d.Div(
                    classes="animate-spin h-5 w-5 border-2 border-indigo-500 rounded-full border-t-transparent"
                )
            )
        elif self.status == "error":
            return d.Div(
                classes="w-6 h-6 flex items-center justify-center text-red-500",
                title="Error loading icon",
            )("⚠️")
        elif self.status == "not_found":
            return d.Div(
                classes="w-6 h-6 flex items-center justify-center text-gray-400",
                title="Icon not found",
            )("❓")
        else:
            return d.Div()("")
