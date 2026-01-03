"""
Home page template.
"""

from pydom import Component
from pydom import html as d


class HomePage(Component):
    """Home page content."""

    def __init__(self, *, is_authenticated: bool = False):
        self.is_authenticated = is_authenticated

    def render(self):
        if self.is_authenticated:
            return AuthenticatedHome()
        return UnauthenticatedHome()


class UnauthenticatedHome(Component):
    """Home page for unauthenticated users."""

    def render(self):
        return d.Div()(
            d.Section(classes="text-center py-20")(
                d.H1(
                    classes="text-4xl font-extrabold text-gray-900 sm:text-5xl sm:tracking-tight lg:text-6xl"
                )("Welcome to Yoto Up"),
                d.P(classes="mt-5 max-w-xl mx-auto text-xl text-gray-500")(
                    "Manage your Yoto cards, upload audio content, and customize icons - all from your browser."
                ),
                d.Div(classes="mt-10 flex justify-center gap-4")(
                    d.A(
                        href="/auth/",
                        classes="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700",
                    )("Get Started"),
                ),
            ),
            d.Section(classes="mt-12")(
                d.H2(classes="text-3xl font-extrabold text-gray-900 text-center mb-12")("Features"),
                d.Div(classes="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3")(
                    FeatureCard(
                        icon="📚",
                        title="Card Management",
                        description="Easily upload and organize your Yoto cards with custom audio content.",
                    ),
                    FeatureCard(
                        icon="🎨",
                        title="Icon Creation",
                        description="Design and assign unique icons to your cards using our built-in library.",
                    ),
                    FeatureCard(
                        icon="📟",
                        title="Device Control",
                        description="Manage your Yoto devices remotely, monitor status, and update settings.",
                    ),
                ),
            ),
        )


class AuthenticatedHome(Component):
    """Home page for authenticated users."""

    def render(self):
        return d.Div()(
            d.H1(classes="text-3xl font-bold text-gray-900 mb-8")("Dashboard"),
            d.Div(classes="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4")(
                QuickAction(
                    title="My Playlists",
                    icon="📚",
                    url="/playlists/",
                    description="View and manage your cards",
                    color="bg-blue-500",
                ),
                QuickAction(
                    title="Icon Library",
                    icon="🎨",
                    url="/icons/",
                    description="Browse and create icons",
                    color="bg-purple-500",
                ),
                QuickAction(
                    title="Devices",
                    icon="📟",
                    url="/devices/",
                    description="Manage your devices",
                    color="bg-orange-500",
                ),
            ),
        )


class FeatureCard(Component):
    """Feature card component."""

    def __init__(self, *, icon: str, title: str, description: str):
        self.icon = icon
        self.title = title
        self.description = description

    def render(self):
        return d.Div(
            classes="bg-white overflow-hidden shadow rounded-lg p-6 text-center hover:shadow-md transition-shadow"
        )(
            d.Div(classes="text-4xl mb-4")(self.icon),
            d.H3(classes="text-lg font-medium text-gray-900 mb-2")(self.title),
            d.P(classes="text-gray-500")(self.description),
        )


class QuickAction(Component):
    """Quick action card component."""

    def __init__(self, *, title: str, icon: str, url: str, description: str, color: str):
        self.title = title
        self.icon = icon
        self.url = url
        self.description = description
        self.color = color

    def render(self):
        return d.A(
            href=self.url,
            classes="block bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow p-6 flex items-center space-x-4",
        )(
            d.Div(
                classes=f"flex-shrink-0 h-12 w-12 rounded-full {self.color} flex items-center justify-center text-white text-2xl"
            )(self.icon),
            d.Div(classes="flex-1")(
                d.H3(classes="text-lg font-medium text-gray-900")(self.title),
                d.P(classes="text-sm text-gray-500")(self.description),
            ),
        )
