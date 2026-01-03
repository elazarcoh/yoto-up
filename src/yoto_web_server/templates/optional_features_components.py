"""Optional features UI components."""

from pydom import Component
from pydom import html as d
from pydom.types import Renderable

from yoto_web_server.services.optional_features_service import FeatureStatus


class FeatureCard(Component):
    """Card displaying a single feature's status."""

    def __init__(self, status: FeatureStatus, details: Renderable | None = None) -> None:
        self.status = status
        self.details = details

    @staticmethod
    def _format_feature_name(identifier: str) -> str:
        """Format feature identifier to readable name."""
        return identifier.replace("_", " ").title()

    def render(self):
        feature_name = self._format_feature_name(self.status.identifier)

        card_classes = "p-6 rounded-lg border-2 bg-white shadow-sm transition-all hover:shadow-md"
        if self.status.available:
            card_classes += " border-green-200"
        else:
            card_classes += " border-red-200"

        reasons = None
        if self.status.reasons:
            reasons = d.Div(classes="mt-4 space-y-2")(
                d.P(classes="text-sm font-medium text-gray-600")("Reasons:"),
                d.Ul(classes="list-disc list-inside text-sm text-gray-600")(
                    *[d.Li(classes="text-red-700")(reason) for reason in self.status.reasons]
                ),
            )

        # Build the badge inline
        if self.status.available:
            badge = d.Span(
                classes="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-100 text-green-800"
            )(
                d.Span(classes="w-2 h-2 rounded-full bg-green-600"),
                d.Span(classes="text-sm font-medium")("Available"),
            )
        else:
            badge = d.Span(
                classes="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-100 text-red-800"
            )(
                d.Span(classes="w-2 h-2 rounded-full bg-red-600"),
                d.Span(classes="text-sm font-medium")("Unavailable"),
            )

        return d.Div(classes=card_classes)(
            d.Div(classes="flex items-center justify-between")(
                d.H3(classes="text-lg font-semibold text-gray-900")(feature_name),
                badge,
            ),
            d.P(classes="mt-2 text-sm text-gray-600 font-mono")(f"[{self.status.identifier}]"),
            self.details if self.details else None,
            reasons if reasons else None,
        )


class FeaturesGrid(Component):
    """Grid displaying all optional features."""

    def __init__(self, features: list[FeatureStatus]) -> None:
        self.features = features

    def render(self):
        available_count = sum(1 for f in self.features if f.available)
        total_count = len(self.features)

        return d.Div(classes="space-y-6")(
            d.Div(classes="bg-white rounded-lg shadow p-6")(
                d.H2(classes="text-2xl font-bold text-gray-900")("Optional Features"),
                d.P(classes="mt-2 text-gray-600")(
                    f"Status: {available_count} of {total_count} features available"
                ),
            ),
            d.Div(classes="grid grid-cols-1 md:grid-cols-2 gap-6")(
                *[FeatureCard(status=feature) for feature in self.features]
            ),
        )


class FeatureToggleExample(Component):
    """Example component showing how to use feature status in UI."""

    def __init__(self, status: FeatureStatus) -> None:
        self.status = status

    def render(self):
        if self.status.available:
            return d.Div(classes="p-4 bg-green-50 border border-green-200 rounded-lg")(
                d.H4(classes="font-semibold text-green-900")(
                    f"{self._format_name(self.status.identifier)} is enabled"
                ),
                d.P(classes="mt-2 text-sm text-green-700")(
                    "This feature is available and can be used."
                ),
            )
        else:
            return d.Div(classes="p-4 bg-gray-50 border border-gray-200 rounded-lg")(
                d.H4(classes="font-semibold text-gray-900")(
                    f"{self._format_name(self.status.identifier)} is disabled"
                ),
                d.P(classes="mt-2 text-sm text-gray-600")(
                    "This feature is not available in your installation."
                ),
            )

    @staticmethod
    def _format_name(identifier: str) -> str:
        """Format feature identifier to readable name."""
        return identifier.replace("_", " ").title()
