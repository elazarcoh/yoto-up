"""
Base template components.

Provides the base HTML structure and common rendering utilities.
"""

from fastapi import Request
from pydom import Component, render
from pydom import html as d
from pydom.context import get_context
from pydom.context.standard import transformers
from pydom.types import Renderable

from yoto_web_server.container import Container
from yoto_web_server.utils.setup_htmx import HTMX, HtmxExtensions

# Initialize HTMX with extensions
htmx = HTMX()
get_context().add_prop_transformer(
    HtmxExtensions.class_tools.transformer(),
    before=[
        transformers.DashTransformer,
    ],
)
get_context().add_prop_transformer(
    htmx.transformer(),
    before=[
        transformers.DashTransformer,
    ],
)


class BaseLayout(Component):
    """Base HTML layout with HTMX and navigation."""

    def __init__(
        self,
        *,
        title: str = "Yoto Up",
        content: Renderable | None = None,
        is_authenticated: bool = False,
    ) -> None:
        self.title = title
        self.content = content
        self.is_authenticated = is_authenticated

    def render(self):
        return d.Html(lang="en")(
            d.Head()(
                d.Meta(charset="utf-8"),
                d.Meta(name="viewport", content="width=device-width, initial-scale=1"),
                d.Title()(self.title),
                # Tailwind CSS v4
                d.Script(src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"),
                # HTMX
                htmx.script(),
                HtmxExtensions.sse.script(),
                HtmxExtensions.class_tools.script(),
                # Alpine.js for simple interactivity
                d.Script(src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js", defer=True),
                # App JavaScript
                d.Script(src="/static/js/app.js", defer=True),
                # Custom styles
                d.Style()("""
                    @layer utilities {
                        input[type="checkbox"]:not(.hidden) {
                            @apply block !important;
                        }
                        input[type="checkbox"].hidden {
                            @apply hidden !important;
                        }
                        .group-hover\\/icon:hover > button {
                            @apply opacity-100;
                        }
                        #edit-overlay.hidden {
                            @apply pointer-events-none !important hidden !important;
                        }
                        #edit-overlay:not(.hidden) {
                            @apply pointer-events-auto !important block !important;
                        }
                        .group\\/icon button {
                            @apply pointer-events-none;
                        }
                        .group\\/icon:hover button {
                            @apply pointer-events-auto;
                        }
                    }
                """),
            ),
            d.Body(classes="bg-gray-50 min-h-screen flex flex-col")(
                # Navigation
                Navigation(is_authenticated=self.is_authenticated),
                # Main content
                d.Main(classes="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-grow w-full")(
                    self.content or d.Div()("No content"),
                ),
                # Footer
                d.Footer(classes="bg-gray-800 text-white py-8 mt-auto")(
                    d.Div(classes="max-w-7xl mx-auto px-4 text-center")(
                        d.Span()("Yoto Up Server"),
                        d.Span()(" | "),
                        d.A(
                            href="https://github.com/xkjq/yoto-up",
                            target="_blank",
                            classes="text-gray-300 hover:text-white",
                        )("GitHub"),
                    ),
                ),
                # Loading indicator
                d.Div(
                    id="global-loading",
                    classes="htmx-indicator hidden fixed inset-0 bg-gray-500/75 flex items-center justify-center z-50",
                )(
                    d.Div(classes="flex flex-col items-center")(
                        d.Div(
                            classes="animate-spin h-10 w-10 border-4 border-indigo-500 rounded-full border-t-transparent mb-4"
                        ),
                        d.Span(classes="text-white font-medium")("Loading..."),
                    ),
                ),
            ),
        )


class Navigation(Component):
    """Navigation component."""

    def __init__(self, *, is_authenticated: bool = False) -> None:
        self.is_authenticated = is_authenticated

    def render(self):
        nav_items = [
            ("Home", "/"),
        ]

        if self.is_authenticated:
            nav_items.extend(
                [
                    ("Playlists", "/playlists/"),
                    ("Devices", "/devices/"),
                    ("Icons", "/icons/"),
                    # ("Upload", "/upload/"),
                    # ("Cards", "/cards/"),
                ]
            )

        return d.Nav(classes="bg-white shadow")(
            d.Div(classes="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8")(
                d.Div(classes="flex justify-between h-16")(
                    d.Div(classes="flex")(
                        d.A(
                            href="/",
                            classes="flex-shrink-0 flex items-center text-indigo-600 font-bold text-xl",
                        )(
                            d.Span(classes="mr-2 text-2xl")("🎵"),
                            d.Span()("Yoto Up"),
                        ),
                        d.Div(classes="hidden sm:ml-6 sm:flex sm:space-x-8")(
                            *[
                                d.A(
                                    href=url,
                                    hx_boost="true",
                                    classes="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium",
                                )(label)
                                for label, url in nav_items
                            ]
                        ),
                    ),
                    d.Div(classes="flex items-center")(
                        d.A(
                            href="/auth/logout",
                            hx_post="/auth/logout",
                            hx_swap="none",
                            classes="text-gray-500 hover:text-gray-700 px-3 py-2 rounded-md text-sm font-medium",
                        )("Logout")
                        if self.is_authenticated
                        else d.A(
                            href="/auth/",
                            classes="text-indigo-600 hover:text-indigo-900 px-3 py-2 rounded-md text-sm font-medium",
                        )("Login")
                    ),
                ),
            ),
        )


class Alert(Component):
    """Alert message component."""

    def __init__(
        self,
        *,
        message: str,
        type: str = "info",  # info, success, warning, error
        dismissible: bool = True,
    ) -> None:
        self.message = message
        self.type = type
        self.dismissible = dismissible

    def render(self):
        colors = {
            "info": "bg-blue-50 text-blue-700",
            "success": "bg-green-50 text-green-700",
            "warning": "bg-yellow-50 text-yellow-700",
            "error": "bg-red-50 text-red-700",
        }
        color_class = colors.get(self.type, colors["info"])

        close_btn = (
            d.Button(
                classes="ml-auto -mx-1.5 -my-1.5 rounded-lg focus:ring-2 focus:ring-blue-400 p-1.5 inline-flex h-8 w-8 text-blue-500 hover:bg-blue-200",
                onclick="this.parentElement.remove()",
            )(d.Span(classes="sr-only")("Close"), "×")
            if self.dismissible
            else None
        )

        return d.Div(classes=f"rounded-md p-4 mb-4 flex items-center {color_class}", role="alert")(
            d.Span(classes="flex-grow")(self.message),
            close_btn,
        )


class Card(Component):
    """Card container component."""

    def __init__(
        self,
        *,
        title: str | None = None,
        content: Component | None = None,
        footer: Component | None = None,
    ) -> None:
        self.title = title
        self.content = content
        self.footer = footer

    def render(self):
        header = (
            d.Div(classes="px-4 py-5 sm:px-6 border-b border-gray-200")(
                d.H3(classes="text-lg leading-6 font-medium text-gray-900")(self.title)
            )
            if self.title
            else None
        )

        footer_el = (
            d.Div(classes="px-4 py-4 sm:px-6 bg-gray-50 border-t border-gray-200")(self.footer)
            if self.footer
            else None
        )

        return d.Div(classes="bg-white overflow-hidden shadow rounded-lg mb-6")(
            header,
            d.Div(classes="px-4 py-5 sm:p-6")(self.content) if self.content else None,
            footer_el,
        )


class LoadingSpinner(Component):
    """Loading spinner component."""

    def __init__(self, *, text: str = "Loading...") -> None:
        self.text = text

    def render(self):
        return d.Div(classes="flex items-center space-x-2")(
            d.Div(
                classes="animate-spin h-5 w-5 border-2 border-indigo-500 rounded-full border-t-transparent"
            ),
            d.Span(classes="text-gray-500")(self.text),
        )


class ProgressBar(Component):
    """Progress bar component."""

    def __init__(self, *, progress: float = 0.0, label: str | None = None) -> None:
        self.progress = max(0, min(100, progress * 100))
        self.label = label

    def render(self):
        return d.Div(classes="w-full")(
            d.Div(classes="flex justify-between mb-1")(
                d.Span(classes="text-sm font-medium text-indigo-700")(self.label)
                if self.label
                else None,
                d.Span(classes="text-sm font-medium text-indigo-700")(f"{self.progress:.0f}%"),
            ),
            d.Div(classes="w-full bg-gray-200 rounded-full h-2.5")(
                d.Div(
                    classes="bg-indigo-600 h-2.5 rounded-full transition-all duration-300",
                    style=f"width: {self.progress}%",
                ),
            ),
        )


def render_page(
    title: str,
    content: Renderable,
    request: Request,
    is_authenticated: bool | None = None,
) -> str:
    """
    Render a full HTML page.

    Args:
        title: Page title.
        content: Main content component.
        request: FastAPI request object.
        is_authenticated: Override authentication status.

    Returns:
        Rendered HTML string.
    """
    # Check auth status if not provided
    if is_authenticated is None:
        try:
            # Try to get session_id from request state (set by middleware)
            session_id = getattr(request.state, "session_id", None)

            # If not in state, try to get from cookies
            if not session_id:
                from yoto_web_server.middleware.session_middleware import (
                    SESSION_COOKIE_NAME,
                )

                cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
                if cookie_value:
                    # Validate and decrypt cookie to get session_id
                    container: Container = request.app.state.container
                    session_service = container.session_service()
                    cookie_payload = session_service.validate_and_decrypt_cookie(cookie_value)
                    if cookie_payload:
                        session_id = cookie_payload.session_id

            # Check if session is authenticated
            if session_id:
                container: Container = request.app.state.container
                session_api_service = container.session_aware_api_service()
                is_authenticated = session_api_service.is_session_authenticated(session_id)
            else:
                is_authenticated = False
        except Exception:
            is_authenticated = False

    layout = BaseLayout(
        title=title,
        content=content,
        is_authenticated=is_authenticated,
    )

    return render(layout)


def render_partial(content: Renderable | str) -> str:
    """
    Render an HTML partial (for HTMX responses).

    Args:
        content: Component or raw HTML string.

    Returns:
        Rendered HTML string.
    """
    if isinstance(content, str):
        return content
    return render(content)
