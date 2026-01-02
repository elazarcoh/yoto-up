"""
Devices templates.
"""

from typing import List
from pydom import Component
from pydom import html as d
from yoto_up.models import Device


class DevicesPage(Component):
    """Devices page content."""

    def __init__(self, *, devices: List[Device]):
        self.devices = devices

    def render(self):
        return d.Div()(
            d.Div(classes="flex justify-between items-center mb-6")(
                d.H1(classes="text-2xl font-bold text-gray-900")("Devices"),
                d.Button(
                    type="button",
                    classes="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 cursor-pointer",
                    hx_get="/devices/list",
                    hx_target="#device-list",
                    hx_swap="outerHTML",
                )("🔄 Refresh"),
            ),
            # Device list container
            d.Div(
                id="device-list",
                classes="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6",
            )(*[DeviceCard(device=device) for device in self.devices]),
        )


class DeviceCard(Component):
    """Display device status with key metrics."""

    def __init__(self, *, device: Device):
        self.device = device

    def render(self):
        return d.Div(
            classes="bg-white rounded-lg shadow p-6 hover:shadow-lg transition"
        )(
            # Header with status indicator
            d.Div(classes="flex justify-between items-start mb-4")(
                d.Div()(
                    d.H3(classes="text-lg font-semibold text-gray-900")(
                        self.device.name or "Unknown"
                    ),
                    d.P(classes="text-sm text-gray-500")(f"ID: {self.device.deviceId}"),
                ),
                d.Span(
                    classes=f"px-3 py-1 rounded-full text-sm font-medium "
                    f"{'bg-green-100 text-green-800' if self.device.online else 'bg-red-100 text-red-800'}"
                )("🟢 Online" if self.device.online else "🔴 Offline"),
            ),
            # Action buttons
            d.Div(classes="mt-6 flex gap-2")(
                d.A(
                    href=f"/devices/{self.device.deviceId}",
                    classes="flex-1 px-3 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 text-sm text-center block",
                )("Manage Device"),
            ),
        )
