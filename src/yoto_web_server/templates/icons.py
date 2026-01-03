"""
Icons page templates.
"""

from typing import Optional

from pydom import html as d
from pydom.component import Component
from pydom.element import Element


class IconGrid(Component):
    """Grid of icons for display."""

    def __init__(self, icons: list[dict], title: str = "Icons") -> None:
        self.icons = icons
        self.title = title

    def render(self) -> Element:
        if not self.icons:
            return d.Div(classes="text-center py-8 text-gray-500")("No icons found")

        return d.Div()(
            d.H2(classes="text-xl font-semibold text-gray-800 mb-4")(self.title),
            d.Div(classes="grid grid-cols-4 md:grid-cols-8 lg:grid-cols-12 gap-2")(
                *[
                    d.Button(
                        classes="aspect-square bg-gray-100 rounded hover:bg-gray-200 transition-colors flex items-center justify-center",
                        title=icon.get("name", ""),
                        **{"x-on:click": f"selectedIcon = '{icon.get('id', '')}'"},
                    )(
                        d.Img(
                            src=icon.get("url", ""),
                            classes="w-8 h-8",
                            alt=icon.get("name", ""),
                        )
                        if icon.get("url")
                        else d.Span(classes="text-2xl")("🖼️")
                    )
                    for icon in self.icons
                ]
            ),
        )


class IconSearchForm(Component):
    """Icon search form component."""

    def __init__(self, query: str = "") -> None:
        self.query = query

    def render(self) -> Element:
        return d.Form(
            classes="mb-6",
            hx_get="/icons/search",
            hx_target="#icon-results",
            hx_trigger="submit",
        )(
            d.Div(classes="flex gap-2")(
                d.Input(
                    type="text",
                    name="q",
                    value=self.query,
                    placeholder="Search icons...",
                    classes="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                ),
                d.Button(
                    type="submit",
                    classes="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors",
                )("Search"),
            ),
        )


class IconsPage(Component):
    """Icons browsing page."""

    def __init__(
        self,
        icons: Optional[list[dict]] = None,
        query: str = "",
        error: Optional[str] = None,
    ) -> None:
        self.icons = icons or []
        self.query = query
        self.error = error

    def render(self) -> Element:
        return d.Div(classes="max-w-6xl mx-auto", **{"x-data": "{ selectedIcon: null }"})(
            d.H1(classes="text-3xl font-bold text-gray-800 mb-6")("Icon Browser"),
            # Search form
            IconSearchForm(query=self.query),
            # Error display
            d.Div(classes="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4")(
                d.P()(f"Error: {self.error}")
            )
            if self.error
            else None,
            # Results
            d.Div(id="icon-results")(
                IconGrid(icons=self.icons, title="Public Icons")
                if self.icons
                else d.P(classes="text-gray-500 text-center py-8")(
                    "Enter a search term to find icons"
                )
            ),
            # Selected icon preview (Alpine.js)
            d.Div(
                classes="fixed bottom-4 right-4 bg-white rounded-lg shadow-lg p-4",
                **{
                    "x-show": "selectedIcon",
                    "x-transition": "",
                },
            )(
                d.P(classes="text-sm text-gray-600")("Selected Icon:"),
                d.P(classes="font-mono text-sm", **{"x-text": "selectedIcon"})(),
            ),
        )


class IconSearchResults(Component):
    """Search results partial for HTMX."""

    def __init__(
        self,
        icons: list[dict],
        query: str = "",
        error: Optional[str] = None,
    ) -> None:
        self.icons = icons
        self.query = query
        self.error = error

    def render(self) -> Element:
        if self.error:
            return d.Div(classes="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded")(
                d.P()(f"Search error: {self.error}")
            )

        if not self.icons:
            return d.P(classes="text-gray-500 text-center py-8")(
                f'No icons found for "{self.query}"'
            )

        return IconGrid(
            icons=self.icons,
            title=f'Results for "{self.query}" ({len(self.icons)} icons)',
        )
