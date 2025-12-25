"""
Cards templates.
"""

from typing import List, Dict, Any, Optional

from pydom import Component
from pydom import html as d


class CardsPage(Component):
    """Cards management page content."""
    
    def render(self):
        return d.Div()(
            d.H1(classes="text-2xl font-bold text-gray-900 mb-2")("Card Management"),
            d.P(classes="text-gray-600 mb-8")("View and edit your Yoto cards."),
            
            # Filters
            d.Div(classes="bg-white p-6 rounded-lg shadow mb-8")(
                d.Form(
                    hx_get="/cards/list",
                    hx_target="#card-list",
                    hx_trigger="submit",
                    hx_indicator="#list-loading",
                )(
                    d.Div(classes="flex flex-col sm:flex-row gap-4")(
                        d.Input(
                            type="text",
                            name="title_filter",
                            id="title-filter",
                            placeholder="Filter by title...",
                            classes="flex-1 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                        ),
                        d.Select(
                            name="category",
                            id="category-filter",
                            classes="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                        )(
                            d.Option(value="")("All Categories"),
                            d.Option(value="none")("None"),
                            d.Option(value="stories")("Stories"),
                            d.Option(value="music")("Music"),
                            d.Option(value="radio")("Radio"),
                            d.Option(value="podcast")("Podcast"),
                            d.Option(value="activities")("Activities"),
                        ),
                        d.Button(
                            type="submit",
                            classes="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500",
                        )("Filter"),
                    ),
                ),
            ),
            
            # Loading indicator
            d.Div(id="list-loading", classes="htmx-indicator flex items-center justify-center space-x-2 py-8")(
                d.Div(classes="animate-spin h-6 w-6 border-2 border-indigo-500 rounded-full border-t-transparent"),
                d.Span(classes="text-gray-500")("Loading cards..."),
            ),
            
            # Card list
            d.Div(
                id="card-list",
                hx_get="/cards/list",
                hx_trigger="load",
                hx_indicator="#list-loading",
                classes="space-y-4"
            ),
            
            # Edit modal container
            d.Div(id="edit-modal-container"),
        )


class CardListPartial(Component):
    """Partial for card list display."""
    
    def __init__(
        self,
        cards: List[Dict[str, Any]],
        total: int = 0,
        page: int = 1,
        page_size: int = 20,
    ):
        print(f"DEBUG: CardListPartial init with {len(cards)} cards. First type: {type(cards[0]) if cards else 'None'}")
        self.cards = cards
        self.total = total
        self.page = page
        self.page_size = page_size
    
    def render(self):
        if not self.cards:
            return d.Div(classes="text-center py-12 bg-white rounded-lg shadow")(
                d.P(classes="text-gray-500")("No cards found."),
            )
        
        total_pages = (self.total + self.page_size - 1) // self.page_size
        
        items = []
        for card in self.cards:
            items.append(CardListItem(card=card))

        return d.Div()(
            d.Div(classes="space-y-4")(
                *items
            ),
            
            # Pagination
            d.Div(classes="mt-6 flex items-center justify-between border-t border-gray-200 pt-4")(
                d.Div(classes="flex-1 flex justify-between sm:hidden")(
                    d.Button(
                        classes="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50",
                        disabled=self.page <= 1,
                        hx_get=f"/cards/list?page={self.page-1}",
                        hx_target="#card-list",
                    )("Previous"),
                    d.Button(
                        classes="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50",
                        disabled=self.page >= total_pages,
                        hx_get=f"/cards/list?page={self.page+1}",
                        hx_target="#card-list",
                    )("Next"),
                ),
                d.Div(classes="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between")(
                    d.Div(
                        d.P(classes="text-sm text-gray-700")(
                            "Showing ",
                            d.Span(classes="font-medium")(str((self.page - 1) * self.page_size + 1)),
                            " to ",
                            d.Span(classes="font-medium")(str(min(self.page * self.page_size, self.total))),
                            " of ",
                            d.Span(classes="font-medium")(str(self.total)),
                            " results"
                        )
                    ),
                    d.Div(
                        d.Nav(classes="relative z-0 inline-flex rounded-md shadow-sm -space-x-px", aria_label="Pagination")(
                            d.Button(
                                classes="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50",
                                disabled=self.page <= 1,
                                hx_get=f"/cards/list?page={self.page-1}",
                                hx_target="#card-list",
                            )(d.Span(classes="sr-only")("Previous"), "←"),
                            d.Button(
                                classes="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50",
                                disabled=self.page >= total_pages,
                                hx_get=f"/cards/list?page={self.page+1}",
                                hx_target="#card-list",
                            )(d.Span(classes="sr-only")("Next"), "→"),
                        )
                    ),
                ),
            ),
        )


class CardListItem(Component):
    """Single card list item."""
    
    def __init__(self, card: Dict[str, Any] = None):
        self.card = card or {}
    
    def render(self):
        card_id = self.card.get("cardId") or self.card.get("id")
        title = self.card.get("title", "Untitled")
        metadata = self.card.get("metadata", {}) or {}
        category = metadata.get("category") or self.card.get("category", "Uncategorized")
        
        cover_data = metadata.get("cover") or self.card.get("cover_url")
        if isinstance(cover_data, dict):
            cover_url = cover_data.get("imageL") or cover_data.get("imageS")
        else:
            cover_url = cover_data
        
        return d.Div(classes="bg-white shadow rounded-lg p-4 flex items-center gap-4 hover:shadow-md transition-shadow")(
            d.Div(classes="h-16 w-16 rounded bg-gray-200 flex-shrink-0 overflow-hidden")(
                d.Img(src=cover_url, alt=title, classes="h-full w-full object-cover")
                if cover_url
                else d.Div(classes="h-full w-full flex items-center justify-center text-2xl text-gray-400")("🎵")
            ),
            d.Div(classes="flex-1 min-w-0")(
                d.H3(classes="text-lg font-medium text-gray-900 truncate")(title),
                d.P(classes="text-sm text-gray-500 capitalize")(category),
            ),
            d.Div(classes="flex items-center gap-2")(
                d.Button(
                    classes="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500",
                    hx_get=f"/cards/{card_id}/edit",
                    hx_target="#edit-modal-container",
                    hx_swap="innerHTML",
                )("Edit"),
                d.Button(
                    classes="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500",
                    hx_delete=f"/cards/{card_id}",
                    hx_confirm="Are you sure you want to delete this card?",
                    hx_target="closest .bg-white",
                    hx_swap="outerHTML",
                )("Delete"),
            ),
        )


class CardEditForm(Component):
    """Form for editing a card."""
    
    def __init__(self, card: Dict[str, Any]):
        self.card = card
    
    def render(self):
        card_id = self.card.get("id")
        title = self.card.get("title", "")
        description = self.card.get("description", "")
        category = self.card.get("category", "none")
        
        return d.Div(classes="fixed inset-0 z-50 overflow-y-auto")(
            d.Div(classes="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0")(
                d.Div(classes="fixed inset-0 transition-opacity", aria_hidden="true")(
                    d.Div(classes="absolute inset-0 bg-gray-500 opacity-75", onclick="document.getElementById('edit-modal-container').innerHTML=''")
                ),
                d.Span(classes="hidden sm:inline-block sm:align-middle sm:h-screen", aria_hidden="true")("&#8203;"),
                d.Div(classes="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full")(
                    d.Form(
                        hx_put=f"/cards/{card_id}",
                        hx_target="#card-list",
                        hx_swap="innerHTML",  # Reload list
                        # Close modal on success
                        hx_on__after_request="if(event.detail.successful) document.getElementById('edit-modal-container').innerHTML=''"
                    )(
                        d.Div(classes="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4")(
                            d.H3(classes="text-lg leading-6 font-medium text-gray-900 mb-4")("Edit Card"),
                            d.Div(classes="space-y-4")(
                                d.Div(
                                    d.Label(html_for="edit-title", classes="block text-sm font-medium text-gray-700")("Title"),
                                    d.Input(
                                        type="text",
                                        name="title",
                                        id="edit-title",
                                        value=title,
                                        classes="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                                    ),
                                ),
                                d.Div(
                                    d.Label(html_for="edit-description", classes="block text-sm font-medium text-gray-700")("Description"),
                                    d.TextArea(
                                        name="description",
                                        id="edit-description",
                                        rows="3",
                                        classes="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                                    )(description),
                                ),
                                d.Div(
                                    d.Label(html_for="edit-category", classes="block text-sm font-medium text-gray-700")("Category"),
                                    d.Select(
                                        name="category",
                                        id="edit-category",
                                        classes="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                                    )(
                                        d.Option(value="none", selected=category=="none")("None"),
                                        d.Option(value="stories", selected=category=="stories")("Stories"),
                                        d.Option(value="music", selected=category=="music")("Music"),
                                        d.Option(value="radio", selected=category=="radio")("Radio"),
                                        d.Option(value="podcast", selected=category=="podcast")("Podcast"),
                                        d.Option(value="activities", selected=category=="activities")("Activities"),
                                    ),
                                ),
                            ),
                        ),
                        d.Div(classes="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse")(
                            d.Button(
                                type="submit",
                                classes="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:ml-3 sm:w-auto sm:text-sm"
                            )("Save Changes"),
                            d.Button(
                                type="button",
                                classes="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm",
                                onclick="document.getElementById('edit-modal-container').innerHTML=''"
                            )("Cancel"),
                        ),
                    ),
                ),
            ),
        )
