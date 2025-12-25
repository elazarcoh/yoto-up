"""
Icons templates.
"""

from typing import List, Optional

from pydom import Component
from pydom import html as d

from yoto_up_server.models import Icon


class IconsPage(Component):
    """Icons browser page content."""
    
    def render(self):
        return d.Div()(
            d.H1(classes="text-2xl font-bold text-gray-900 mb-2")("Icon Browser"),
            d.P(classes="text-gray-600 mb-8")("Search and manage icons for your Yoto cards."),
            
            # Search section
            d.Div(classes="bg-white p-6 rounded-lg shadow mb-8")(
                d.Form(
                    hx_get="/icons/search",
                    hx_target="#icon-grid",
                    hx_trigger="submit",
                    hx_indicator="#search-loading",
                )(
                    d.Div(classes="flex gap-4")(
                        d.Input(
                            type="text",
                            name="query",
                            id="icon-search",
                            placeholder="Search icons...",
                            classes="flex-1 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                        ),
                        d.Button(
                            type="submit",
                            classes="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500",
                        )("Search"),
                    ),
                    d.Div(classes="mt-4 flex items-center gap-6")(
                        d.Label(classes="flex items-center space-x-2 cursor-pointer")(
                            d.Input(
                                type="checkbox",
                                name="fuzzy",
                                id="fuzzy-checkbox",
                                classes="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
                            ),
                            d.Span(classes="text-sm text-gray-700")("Fuzzy match"),
                        ),
                        d.Div(classes="flex items-center space-x-2")(
                            d.Label(html_for="threshold", classes="text-sm text-gray-700")("Threshold:"),
                            d.Input(
                                type="number",
                                name="threshold",
                                id="threshold",
                                value="0.6",
                                min="0",
                                max="1",
                                step="0.1",
                                classes="w-20 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                            ),
                        ),
                    ),
                ),
                
                # Source filters
                d.Div(classes="mt-6 flex items-center space-x-2")(
                    d.Span(classes="text-sm font-medium text-gray-700 mr-2")("Source:"),
                    d.Button(
                        classes="px-3 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800 hover:bg-indigo-200",
                        hx_get="/icons/search",
                        hx_target="#icon-grid",
                    )("All"),
                    d.Button(
                        classes="px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800 hover:bg-gray-200",
                        hx_get="/icons/search?source=official",
                        hx_target="#icon-grid",
                    )("Official"),
                    d.Button(
                        classes="px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800 hover:bg-gray-200",
                        hx_get="/icons/search?source=yotoicons",
                        hx_target="#icon-grid",
                    )("YotoIcons"),
                    d.Button(
                        classes="px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800 hover:bg-gray-200",
                        hx_get="/icons/search?source=local",
                        hx_target="#icon-grid",
                    )("Local"),
                ),
            ),
            
            # Loading indicator
            d.Div(id="search-loading", classes="htmx-indicator flex items-center justify-center space-x-2 py-8")(
                d.Div(classes="animate-spin h-6 w-6 border-2 border-indigo-500 rounded-full border-t-transparent"),
                d.Span(classes="text-gray-500")("Searching icons..."),
            ),
            
            # Icon grid
            d.Div(classes="relative")(
                d.Div(
                    id="icon-grid",
                    hx_get="/icons/search",
                    hx_trigger="load",
                    hx_indicator="#search-loading",
                    classes="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-4"
                ),
                # Detail panel container (will be populated by HTMX)
                d.Div(id="icon-detail-container"),
            ),
        )


class IconGridPartial(Component):
    """Partial for icon grid."""
    
    def __init__(self, icons: List[Icon], query: Optional[str] = None, source: Optional[str] = None):
        super().__init__()
        self.icons = icons
        self.query = query
        self.source = source
    
    def render(self):
        if not self.icons:
            return d.Div(classes="col-span-full text-center py-12 text-gray-500")(
                "No icons found."
            )
        
        # Render each IconTile and return the rendered elements
        tiles = [IconTile(icon).render() for icon in self.icons]
        return d.Fragment()(*tiles)


class IconTile(Component):
    """Single icon tile component."""
    
    def __init__(self, icon: Icon):
        super().__init__()
        self.icon = icon
    
    def render(self):
        icon_id = self.icon.id
        name = self.icon.name
        url = self.icon.data
        
        return d.Div(
            classes="aspect-square bg-white rounded-lg shadow hover:shadow-md transition-all cursor-pointer p-2 flex flex-col items-center justify-center border border-gray-200 hover:border-indigo-500 group",
            hx_get=f"/icons/{icon_id}",
            hx_target="#icon-detail-container",
            hx_swap="innerHTML",
        )(
            d.Div(classes="w-full h-full flex items-center justify-center overflow-hidden")(
                d.Img(
                    src=url,
                    alt=name,
                    classes="max-w-full max-h-full object-contain rendering-pixelated"
                )
            ),
            d.Div(classes="mt-1 text-[10px] text-center text-gray-500 truncate w-full group-hover:text-indigo-600")(
                name
            ),
        )


class IconDetailPartial(Component):
    """Partial for icon details panel."""
    
    def __init__(self, icon: Icon):
        super().__init__()
        self.icon = icon
    
    def render(self):
        name = self.icon.name
        url = self.icon.data
        source = self.icon.metadata.source.value if self.icon.metadata else "unknown"
        
        return d.Div(classes="fixed right-0 top-16 bottom-0 w-80 bg-white shadow-xl p-6 overflow-y-auto transform transition-transform duration-300 border-l border-gray-200 z-40")(
            d.Div(classes="flex justify-between items-start mb-6")(
                d.H2(classes="text-xl font-bold text-gray-900")(name),
                d.Button(
                    classes="text-gray-400 hover:text-gray-500",
                    onclick="this.closest('.fixed').remove()"
                )("×")
            ),
            
            d.Div(classes="bg-gray-100 rounded-lg p-8 mb-6 flex items-center justify-center")(
                d.Img(
                    src=url,
                    alt=name,
                    classes="w-32 h-32 object-contain rendering-pixelated shadow-sm"
                )
            ),
            
            d.Div(classes="space-y-4")(
                d.Div(
                    d.H3(classes="text-sm font-medium text-gray-500")("Source"),
                    d.P(classes="mt-1 text-sm text-gray-900 capitalize")(source),
                ),
                d.Div(
                    d.H3(classes="text-sm font-medium text-gray-500")("Dimensions"),
                    d.P(classes="mt-1 text-sm text-gray-900")("16 x 16 pixels"),
                ),
                d.Div(classes="pt-4 border-t border-gray-200")(
                    d.Button(
                        classes="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 mb-3"
                    )("Use This Icon"),
                    d.Button(
                        classes="w-full flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    )("Download"),
                ),
            ),
        )
