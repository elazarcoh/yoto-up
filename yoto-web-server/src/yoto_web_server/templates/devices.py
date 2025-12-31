"""
Devices page templates.
"""

from pydom import html as d
from pydom.component import Component
from pydom.element import Element

from yoto_web_server.api.models import Device


class DeviceCard(Component):
    """Single device card component."""

    def __init__(self, device: Device) -> None:
        self.device = device

    def render(self) -> Element:
        # Status indicator
        is_online = self.device.online if hasattr(self.device, "online") else False
        status_color = "bg-green-500" if is_online else "bg-gray-400"
        status_text = "Online" if is_online else "Offline"

        # Device name
        name = self.device.name or self.device.deviceId

        return d.A(href=f"/devices/{self.device.deviceId}", classes="block")(
            d.Div(classes="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow")(
                d.Div(classes="flex items-center justify-between")(
                    d.Div(classes="flex items-center gap-4")(
                        # Device icon
                        d.Div(
                            classes="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center"
                        )(d.Span(classes="text-2xl")("📻")),
                        d.Div()(
                            d.H3(classes="font-semibold text-gray-800")(name),
                            d.P(classes="text-sm text-gray-500")(
                                f"ID: {self.device.deviceId[:8]}..."
                                if len(self.device.deviceId) > 8
                                else f"ID: {self.device.deviceId}"
                            ),
                        ),
                    ),
                    # Status indicator
                    d.Div(classes="flex items-center gap-2")(
                        d.Div(classes=f"w-3 h-3 rounded-full {status_color}")(),
                        d.Span(classes="text-sm text-gray-600")(status_text),
                    ),
                ),
                # Device details
                d.Div(classes="mt-4 pt-4 border-t border-gray-200")(
                    d.Div(classes="grid grid-cols-2 gap-2 text-sm")(
                        d.Div()(
                            d.Span(classes="text-gray-500")("Firmware: "),
                            d.Span(classes="text-gray-700")(
                                getattr(self.device, "firmwareVersion", "Unknown")
                            ),
                        ),
                        d.Div()(
                            d.Span(classes="text-gray-500")("Model: "),
                            d.Span(classes="text-gray-700")(
                                getattr(self.device, "model", "Yoto Player")
                            ),
                        ),
                    ),
                ),
            )
        )


class DevicesPage(Component):
    """Devices listing page."""

    def __init__(
        self,
        devices: list[Device] | None = None,
        error: str | None = None,
    ) -> None:
        self.devices = devices or []
        self.error = error

    def render(self) -> Element:
        if self.error:
            return d.Div(classes="max-w-4xl mx-auto")(
                d.Div(classes="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded")(
                    d.P()(f"Error loading devices: {self.error}")
                )
            )

        if not self.devices:
            return d.Div(classes="max-w-4xl mx-auto text-center py-12")(
                d.P(classes="text-gray-600 text-xl")("No devices found."),
                d.P(classes="text-gray-500 mt-2")(
                    "Connect a Yoto Player to your account to see it here."
                ),
            )

        return d.Div(classes="max-w-4xl mx-auto")(
            d.H1(classes="text-3xl font-bold text-gray-800 mb-6")("My Devices"),
            d.Div(classes="space-y-4")(*[DeviceCard(device=device) for device in self.devices]),
        )


class DeviceDetailPage(Component):
    """Device detail page."""

    def __init__(
        self,
        device: Device | None = None,
        error: str | None = None,
    ) -> None:
        self.device = device
        self.error = error

    def render(self) -> Element:
        if self.error or not self.device:
            return d.Div(classes="max-w-4xl mx-auto")(
                d.Div(classes="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded")(
                    d.P()(f"Error: {self.error or 'Device not found'}")
                ),
                d.A(href="/devices", classes="text-blue-600 hover:underline mt-4 inline-block")(
                    "← Back to Devices"
                ),
            )

        name = self.device.name or self.device.deviceId

        return d.Div(classes="max-w-4xl mx-auto")(
            d.A(href="/devices", classes="text-blue-600 hover:underline mb-4 inline-block")(
                "← Back to Devices"
            ),
            d.Div(classes="bg-white rounded-lg shadow-md p-6")(
                d.Div(classes="flex items-center gap-4 mb-6")(
                    d.Div(
                        classes="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center"
                    )(d.Span(classes="text-4xl")("📻")),
                    d.H1(classes="text-2xl font-bold text-gray-800")(name),
                ),
                d.Dl(classes="grid grid-cols-1 md:grid-cols-2 gap-4")(
                    d.Div(classes="bg-gray-50 px-4 py-3 rounded")(
                        d.Dt(classes="text-sm text-gray-500")("Device ID"),
                        d.Dd(classes="font-mono text-sm")(self.device.deviceId),
                    ),
                    d.Div(classes="bg-gray-50 px-4 py-3 rounded")(
                        d.Dt(classes="text-sm text-gray-500")("Status"),
                        d.Dd()(
                            d.Span(classes="inline-flex items-center gap-2")(
                                d.Div(
                                    classes=f"w-2 h-2 rounded-full {'bg-green-500' if getattr(self.device, 'online', False) else 'bg-gray-400'}"
                                )(),
                                "Online" if getattr(self.device, "online", False) else "Offline",
                            )
                        ),
                    ),
                ),
            ),
        )
