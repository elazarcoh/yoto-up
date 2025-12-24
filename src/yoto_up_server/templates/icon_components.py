"""
Icon-related components and partials for HTMX.
"""

from typing import List, Optional

from pydom import Component
from pydom import html as d


class IconGridPartial(Component):
    """Server-rendered icon grid for selection."""
    
    def __init__(
        self,
        icons: List[dict],
        title: str = "Icons",
        target_endpoint: str = "/playlists/update-chapter-icon",
    ):
        super().__init__()
        self.icons = icons
        self.title = title
        self.target_endpoint = target_endpoint
    
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
            *[
                self._render_icon(icon)
                for icon in self.icons
            ]
        )
    
    def _render_icon(self, icon: dict):
        """Render a single icon button."""
        icon_id = icon.get("mediaId") or icon.get("id")
        title = icon.get("title", "Untitled")
        thumbnail = icon.get("thumbnail")
        
        thumbnail_html = (
            d.Img(
                src=thumbnail,
                alt=title,
                classes="w-full h-full object-cover rounded"
            )
            if thumbnail
            else d.Div(
                classes="w-full h-full bg-gray-200 rounded flex items-center justify-center text-xs text-gray-400"
            )("No image")
        )
        
        return d.Button(
            classes="w-16 h-16 rounded border-2 border-gray-200 hover:border-indigo-500 hover:shadow-lg transition-all cursor-pointer flex items-center justify-center",
            title=title,
            hx_post=self.target_endpoint,
            hx_vals=f'{{"icon_id": "{icon_id}"}}',
            hx_trigger="click",
            hx_swap="none",
            **{"hx-on::after-request": "if(event.detail.successful) window.location.reload()"}
        )(thumbnail_html)


class IconSidebarPartial(Component):
    """Server-rendered icon sidebar with search."""
    
    def __init__(
        self,
        playlist_id: str,
        chapter_index: Optional[int] = None,
        batch_mode: bool = False,
    ):
        super().__init__()
        self.playlist_id = playlist_id
        self.chapter_index = chapter_index
        self.batch_mode = batch_mode
    
    def render(self):
        # Determine the update endpoint based on mode
        if self.batch_mode:
            target_endpoint = f"/playlists/{self.playlist_id}/batch-update-icons"
        else:
            target_endpoint = f"/playlists/{self.playlist_id}/update-chapter-icon"
        
        return d.Div(
            id="icon-sidebar",
            classes="fixed right-0 top-0 h-screen w-96 bg-white shadow-2xl z-50 overflow-y-auto",
            **{"hx-on:close-sidebar": "this.classList.add('hidden')"}
        )(
            # Header
            d.Div(classes="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center z-10")(
                d.H3(classes="text-xl font-bold text-gray-900")(
                    "Batch Edit Icons" if self.batch_mode else "Select Icon"
                ),
                d.Button(
                    classes="text-gray-500 hover:text-gray-700 text-2xl",
                    **{"hx-on:click": "this.closest('#icon-sidebar').classList.add('hidden'); document.getElementById('edit-overlay').classList.add('hidden')"}
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
                        hx_get=f"/icons/search",
                        hx_trigger="keyup changed delay:500ms",
                        hx_target="#icons-grid",
                        hx_include="[name='query']",
                        hx_indicator="#search-indicator",
                    ),
                    d.Div(
                        id="search-indicator",
                        classes="htmx-indicator flex items-center"
                    )(
                        d.Div(classes="animate-spin h-5 w-5 border-2 border-indigo-500 rounded-full border-t-transparent")
                    ),
                ),
                d.Div(classes="mt-2 flex gap-2")(
                    d.Button(
                        classes="text-sm text-indigo-600 hover:text-indigo-900",
                        hx_get="/icons/list?source=user&limit=100",
                        hx_target="#icons-grid",
                        hx_swap="innerHTML",
                    )("My Icons"),
                    d.Button(
                        classes="text-sm text-indigo-600 hover:text-indigo-900",
                        hx_get="/icons/list?source=yoto&limit=50",
                        hx_target="#icons-grid",
                        hx_swap="innerHTML",
                    )("Yoto Icons"),
                ),
            ),
            
            # Icons grid container
            d.Div(
                id="icons-grid",
                classes="px-6 py-4 grid grid-cols-4 gap-3",
                hx_get="/icons/list?source=user&limit=100",
                hx_trigger="load",
                hx_swap="innerHTML",
                **{"data-chapter-index": str(chapter_index) if chapter_index is not None else "batch"}
            )(),
        )


class IconSearchResultsPartial(Component):
    """Partial for icon search results."""
    
    def __init__(
        self,
        icons: List[dict],
        query: str,
        playlist_id: str,
        chapter_index: Optional[int] = None,
    ):
        super().__init__()
        self.icons = icons
        self.query = query
        self.playlist_id = playlist_id
        self.chapter_index = chapter_index
    
    def render(self):
        target_endpoint = f"/playlists/{self.playlist_id}/update-chapter-icon"
        
        if not self.icons:
            return d.Div(classes="col-span-4 p-4 text-center text-gray-500")(
                f'No icons found for "{self.query}"'
            )
        
        return IconGridPartial(
            icons=self.icons,
            title=f'Search Results ({len(self.icons)})',
            target_endpoint=target_endpoint,
        ).render()
