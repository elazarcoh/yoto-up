"""
Icon-related components and partials for HTMX.
"""

import json

from pydom import Component
from pydom import html as d

from yoto_web_server.api.models import DisplayIcon


class PaginationControls(Component):
    """Pagination controls for icon grids."""

    def __init__(
        self,
        *,
        page: int,
        per_page: int,
        total: int,
        source: list[str] | str,
        query: str | None = None,
        fuzzy: bool = True,
        target_id: str | None = None,
    ):
        super().__init__()
        self.page = page
        self.per_page = per_page
        self.total = total
        self.source = source if isinstance(source, list) else [source]
        self.query = query
        self.fuzzy = fuzzy
        self.total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        self.target_id = target_id or "official-icons-section"

    def _build_query_string(self, page: int) -> str:
        """Build query string for pagination link."""
        params = []
        for s in self.source:
            # Handle both enum and string values
            if hasattr(s, "value"):
                source_val: str = s.value  # type: ignore
            else:
                source_val = str(s)
            params.append(f"source={source_val}")
        params.append(f"page={page}")
        params.append(f"per_page={self.per_page}")
        if self.query:
            params.append(f"query={self.query}")
        if not self.fuzzy:
            params.append("fuzzy=false")
        return "&".join(params)

    def render(self):
        # Don't show pagination if only 1 page or less
        if self.total_pages <= 1:
            return d.Fragment()()

        prev_page = self.page - 1
        next_page = self.page + 1
        has_prev = self.page > 1
        has_next = self.page < self.total_pages

        # Build pagination buttons - only include HTMX attrs if enabled
        buttons = []

        # Previous button
        if has_prev:
            buttons.append(
                d.Button(
                    classes="px-4 py-2 text-sm font-medium rounded-lg border border-indigo-300 bg-white text-indigo-600 hover:bg-indigo-50 hover:border-indigo-400 transition-colors cursor-pointer",
                    type="button",
                    hx_get=f"/icons/grid?{self._build_query_string(prev_page)}",
                    hx_target=f"#{self.target_id}",
                    hx_swap="innerHTML",
                )("← Previous")
            )
        else:
            buttons.append(
                d.Button(
                    classes="px-4 py-2 text-sm font-medium rounded-lg border border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed",
                    type="button",
                    disabled=True,
                )("← Previous")
            )

        # Page info with better styling
        buttons.append(
            d.Div(classes="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg")(
                f"{self.page} / {self.total_pages}"
            )
        )

        # Next button
        if has_next:
            buttons.append(
                d.Button(
                    classes="px-4 py-2 text-sm font-medium rounded-lg border border-indigo-300 bg-white text-indigo-600 hover:bg-indigo-50 hover:border-indigo-400 transition-colors cursor-pointer",
                    type="button",
                    hx_get=f"/icons/grid?{self._build_query_string(next_page)}",
                    hx_target=f"#{self.target_id}",
                    hx_swap="innerHTML",
                )("Next →")
            )
        else:
            buttons.append(
                d.Button(
                    classes="px-4 py-2 text-sm font-medium rounded-lg border border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed",
                    type="button",
                    disabled=True,
                )("Next →")
            )

        return d.Div(
            classes="col-span-4 flex items-center justify-center gap-3 mt-6 pt-6 border-t border-gray-200"
        )(*buttons)


class IconGridPartial(Component):
    """Server-rendered icon grid for selection via HTMX form submission."""

    def __init__(
        self,
        *,
        icons: list[DisplayIcon],
        title: str = "Icons",
        use_lazy_loading: bool = False,
        total: int = 0,
        page: int = 1,
        per_page: int = 50,
        source: list[str] | str | None = None,
        query: str | None = None,
        fuzzy: bool = True,
    ):
        super().__init__()
        self.icons = icons
        self.title = title
        self.use_lazy_loading = use_lazy_loading
        self.total = total
        self.page = page
        self.per_page = per_page
        self.source = source
        self.query = query
        self.fuzzy = fuzzy

    def _get_target_id(self) -> str:
        """Determine the target ID based on source."""
        source_list = (
            self.source if isinstance(self.source, list) else [self.source] if self.source else []
        )
        if not source_list:
            return "official-icons-section"

        # Get string representation of first source
        first_source = source_list[0]
        if hasattr(first_source, "value"):
            source_str = str(first_source.value).lower()  # type: ignore
        else:
            source_str = str(first_source).lower()

        if "user" in source_str:
            return "user-icons-section"
        elif any(x in source_str for x in ["yotoicons", "online", "cached"]):
            return "yotoicons-section"
        else:
            return "official-icons-section"

    def render(self):
        if not self.icons:
            return d.Div(classes="col-span-4 p-4 text-center text-gray-500")("No icons found")

        # Convert source to string list if needed
        source_list = (
            self.source if isinstance(self.source, list) else [self.source] if self.source else []
        )

        # Build title with icon count
        title_text = (
            f"{self.title} ({self.total})" if self.total else f"{self.title} ({len(self.icons)})"
        )

        # Build content
        content = [
            d.Div(classes="col-span-4 mb-4")(
                d.H4(classes="font-semibold text-gray-700")(title_text)
            ),
            *[self._render_icon(icon) for icon in self.icons],
        ]

        # Add pagination controls if we have total info and multiple pages
        if self.total > 0:
            pagination = PaginationControls(
                page=self.page,
                per_page=self.per_page,
                total=self.total,
                source=source_list,
                query=self.query,
                fuzzy=self.fuzzy,
                target_id=self._get_target_id(),
            )
            content.append(pagination)

        return d.Fragment()(*content)

    def _render_icon(self, icon: DisplayIcon):
        """Render a single icon as a submit button in a form."""
        icon_id = icon.media_id
        title = icon.title or "Untitled"

        # Use lazy loading for all icons (official, user, and yotoicons)
        img_component = LazyIconImg(
            icon_id=icon_id,
            title=title,
            classes="w-full h-full object-cover rounded",
        )

        return d.Button(
            classes="w-16 h-16 rounded border-2 border-gray-200 hover:border-indigo-500 hover:shadow-lg transition-all cursor-pointer flex items-center justify-center",
            title=title,
            type="submit",
            name="icon_id",
            value=icon_id,
        )(img_component)


class IconSidebarPartial(Component):
    """Server-rendered icon sidebar with user and official icon grids."""

    def __init__(
        self,
        *,
        playlist_id: str,
        chapter_ids: list[int] | None = None,
        track_ids: list[tuple[int, int]] | None = None,
    ):
        super().__init__()
        self.playlist_id = playlist_id
        self.chapter_ids = chapter_ids or []
        self.track_ids = track_ids or []

    def render(self):
        return d.Form(
            id="icon-assignment-form",
            hx_post=f"/playlists/{self.playlist_id}/update-items-icon",
            hx_target="#playlist-detail",
            hx_swap="outerHTML",
            hx_vals=json.dumps(
                {
                    "chapter_ids": self.chapter_ids,
                    "track_ids": self.track_ids,
                }
            ),
            classes="fixed right-0 top-0 h-screen w-96 bg-white shadow-2xl z-50 overflow-y-auto flex flex-col",
        )(
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
                    on_click="closeIconSidebar()",
                )("✕"),
            ),
            # Search bar
            d.Div(classes="px-6 py-4 bg-gray-50 border-b border-gray-200")(
                d.Div(classes="flex flex-col gap-2")(
                    d.Div(classes="flex gap-2")(
                        d.Input(
                            type="text",
                            id="icon-search-input",
                            name="query",
                            placeholder="Search cached icons...",
                            classes="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500",
                            hx_get="/icons/grid?source=cached&page=1&per_page=12",
                            hx_trigger="keyup changed delay:500ms",
                            hx_target="#yotoicons-section",
                            hx_swap="innerHTML",
                            hx_indicator="#search-indicator",
                            hx_include="#icon-search-input",
                        ),
                        d.Button(
                            classes="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 whitespace-nowrap",
                            type="button",
                            hx_get="/icons/grid?source=online&page=1&per_page=12",
                            hx_include="#icon-search-input",
                            hx_target="#yotoicons-section",
                            hx_swap="innerHTML",
                            hx_indicator="#yotoicons-indicator",
                        )("Search Online"),
                    ),
                    d.Div(classes="flex justify-between text-xs text-gray-500")(
                        d.Span(id="search-indicator", classes="htmx-indicator")(
                            "Searching cached..."
                        ),
                        d.Span(id="yotoicons-indicator", classes="htmx-indicator")(
                            "Searching YotoIcons.com..."
                        ),
                    ),
                ),
            ),
            # Content area with scrollable grids
            d.Div(classes="flex-1 overflow-y-auto px-6 py-4 space-y-8")(
                # Live Search Results (YotoIcons)
                d.Div(
                    id="yotoicons-section",
                    classes="grid grid-cols-4 gap-3 empty:hidden",
                )(),
                # User icons grid
                d.Div(
                    id="user-icons-section",
                    hx_get="/icons/grid?source=user&page=1&per_page=12",
                    hx_trigger="load",
                    hx_target="this",
                    hx_swap="innerHTML",
                    classes="grid grid-cols-4 gap-3",
                )(),
                # Official icons grid - also acts as local search results container
                d.Div(
                    id="official-icons-section",
                    hx_get="/icons/grid?source=official&page=1&per_page=12",
                    hx_trigger="load",
                    hx_target="this",
                    hx_swap="innerHTML",
                    classes="grid grid-cols-4 gap-3",
                )(),
            ),
            # Script to handle sidebar interactions
            d.Script()("""//js
            // Helper function to close icon sidebar
            function closeIconSidebar() {
                const overlay = document.getElementById('edit-overlay');
                const sidebar = document.getElementById('icon-sidebar-container');
                if(overlay) overlay.classList.add('hidden');
                if(sidebar) sidebar.innerHTML = '';
            }
            
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
        *,
        icons: list[DisplayIcon],
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
        *,
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
        )


class LazyIconImg(Component):
    """
    Lazy-loaded icon image with HTMX loading state.

    Renders an initial placeholder (ph1) with HTMX hx-load trigger.
    On load, HTMX fetches from /icons/{icon_id} which returns an IconImg (ph2).
    """

    def __init__(
        self,
        *,
        icon_id: str,
        title: str = "Icon",
        classes: str = "w-6 h-6",
        container_id: str | None = None,
    ):
        super().__init__()
        self.icon_id = icon_id
        self.title = title
        self.classes = classes
        self.container_id = container_id or f"icon-{icon_id.replace('#', '')}"

    def render(self):
        loading_placeholder = d.Div(
            classes=self.classes,
            title="Loading icon...",
        )(
            d.Div(
                classes="animate-spin h-5 w-5 border-2 border-indigo-500 rounded-full border-t-transparent"
            )
        )

        # Container with HTMX load trigger
        return d.Div(
            id=self.container_id,
            hx_get=f"/icons/{self.icon_id}",
            hx_trigger="load",
            hx_swap="outerHTML",
            hx_target="this",
            classes="inline-block",
        )(loading_placeholder)


class LoadingIconIndicator(Component):
    """Indicator component for loading icon states (used with HTMX)."""

    def __init__(self, *, media_id: str, status: str = "loading"):
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
