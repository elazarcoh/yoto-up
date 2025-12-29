"""
Device Detail templates.
"""

from pydom import Component
from pydom import html as d
from yoto_up.models import Device, DeviceConfig
from yoto_up.yoto_api_client import DeviceStatus
from yoto_up_server.utils.alpine import xbind, xon, xdata, xshow


class DeviceDetailPage(Component):
    """Device detail page with tabs."""

    def __init__(self, *, device: Device, status: DeviceStatus, config: DeviceConfig):
        self.device = device
        self.status = status
        self.config = config

    def render(self):
        return d.Div(**xdata({"tab": "control"}))(
            # Header
            d.Div(classes="flex justify-between items-center mb-6")(
                d.Div()(
                    d.H1(classes="text-2xl font-bold text-gray-900")(self.device.name),
                    d.P(classes="text-sm text-gray-500")(f"ID: {self.device.deviceId}"),
                ),
                d.Span(
                    classes=f"px-3 py-1 rounded-full text-sm font-medium "
                    f"{'bg-green-100 text-green-800' if self.device.online else 'bg-red-100 text-red-800'}"
                )("🟢 Online" if self.device.online else "🔴 Offline"),
            ),
            # Tabs
            d.Div(classes="mb-6 border-b border-gray-200")(
                d.Nav(classes="-mb-px flex space-x-8")(
                    d.A(
                        href="#",
                        classes="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm cursor-pointer",
                        **xbind().classes(
                            "{ 'border-indigo-500 text-indigo-600': tab === 'control', 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300': tab !== 'control' }"
                        ),
                        **xon().click.prevent("tab = 'control'"),
                    )("Control"),
                    d.A(
                        href="#",
                        classes="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm cursor-pointer",
                        **xbind().classes(
                            "{ 'border-indigo-500 text-indigo-600': tab === 'settings', 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300': tab !== 'settings' }"
                        ),
                        **xon().click.prevent("tab = 'settings'"),
                    )("Settings"),
                )
            ),
            # Tab Content
            d.Div(**xshow("tab === 'control'"))(
                PlaybackControlPanel(device_id=self.device.deviceId, status=self.status)
            ),
            d.Div(**xshow("tab === 'settings'"))(
                SettingsPanel(device_id=self.device.deviceId, config=self.config)
            ),
            
            # Modal containers for JSON display
            d.Div(id="status-json-modal-container")(),
            d.Div(id="config-json-modal-container")(),
        )


class PlaybackControlPanel(Component):
    """Playback control UI."""

    def __init__(self, *, device_id: str, status: DeviceStatus):
        self.device_id = device_id
        self.status = status

    def render(self):
        return d.Div(
            classes="bg-white rounded-lg shadow p-6"
        )(
            d.Div(classes="flex justify-between items-center mb-4")(
                d.H3(classes="text-lg font-semibold text-gray-900")(
                    "Playback Control"
                ),
                d.Button(
                    classes="px-3 py-1 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 text-sm font-medium",
                    hx_get=f"/devices/{self.device_id}/status-json-modal",
                    hx_target="#status-json-modal-container",
                    hx_swap="innerHTML",
                )("📋 Status JSON"),
            ),
            # Status Info
            d.Div(classes="grid grid-cols-2 gap-4 mb-6")(
                StatusMetric("Battery", f"{self.status.battery_level_percentage}%"),
                StatusMetric("Volume", f"{self.status.user_volume_percentage}%"),
                StatusMetric("WiFi", f"{self.status.wifi_strength} dBm"),
                StatusMetric("Temp", f"{self.status.temperature_celsius}°C"),
            ),
            # Controls
            d.Div(classes="flex justify-center gap-4 mb-6")(
                d.Button(
                    classes="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300",
                    hx_post=f"/devices/{self.device_id}/playback/previous",
                    hx_swap="none",
                )("⏮️ Prev"),
                d.Button(
                    classes="px-6 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700",
                    hx_post=f"/devices/{self.device_id}/playback/resume",  # Assuming resume for play
                    hx_swap="none",
                )("▶️ Play"),
                d.Button(
                    classes="px-6 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700",
                    hx_post=f"/devices/{self.device_id}/playback/pause",
                    hx_swap="none",
                )("⏸️ Pause"),
                d.Button(
                    classes="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700",
                    hx_post=f"/devices/{self.device_id}/playback/stop",
                    hx_swap="none",
                )("⏹️ Stop"),
                d.Button(
                    classes="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300",
                    hx_post=f"/devices/{self.device_id}/playback/next",
                    hx_swap="none",
                )("⏭️ Next"),
            ),
            # Volume Slider
            d.Div(classes="mb-4")(
                d.Label(classes="block text-sm font-medium text-gray-700 mb-2")(
                    "Volume"
                ),
                d.Input(
                    type="range",
                    min="0",
                    max="16",
                    value=str(
                        int(self.status.user_volume_percentage / 100 * 16)
                    ),  # Approx conversion
                    classes="w-full",
                    name="volume",
                    hx_post=f"/devices/{self.device_id}/volume",
                    hx_trigger="change",
                    hx_swap="none",
                ),
            ),
        )


class SettingsPanel(Component):
    """Settings UI."""

    def __init__(self, *, device_id: str, config: DeviceConfig):
        self.device_id = device_id
        self.config = config

    def render(self):
        return d.Div(classes="bg-white rounded-lg shadow p-6")(
            d.Div(classes="flex justify-between items-center mb-4")(
                d.H3(classes="text-lg font-semibold text-gray-900")("Settings"),
                d.Button(
                    classes="px-3 py-1 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 text-sm font-medium",
                    hx_get=f"/devices/{self.device_id}/config-json-modal",
                    hx_target="#config-json-modal-container",
                    hx_swap="innerHTML",
                )("📋 Config JSON"),
            ),
            # Brightness
            d.Div(classes="mb-4")(
                d.Label(classes="block text-sm font-medium text-gray-700 mb-2")(
                    "Day Brightness"
                ),
                d.Input(
                    type="range",
                    min="0",
                    max="100",
                    value=str(self.config.dayDisplayBrightness),
                    classes="w-full",
                    name="dayDisplayBrightness",
                    hx_post=f"/devices/{self.device_id}/config",
                    hx_trigger="change",
                    hx_swap="none",
                ),
            ),
            # Night Brightness
            d.Div(classes="mb-4")(
                d.Label(classes="block text-sm font-medium text-gray-700 mb-2")(
                    "Night Brightness"
                ),
                d.Input(
                    type="range",
                    min="0",
                    max="100",
                    value=str(self.config.nightDisplayBrightness),
                    classes="w-full",
                    name="nightDisplayBrightness",
                    hx_post=f"/devices/{self.device_id}/config",
                    hx_trigger="change",
                    hx_swap="none",
                ),
            ),
            # Max Volume
            d.Div(classes="mb-4")(
                d.Label(classes="block text-sm font-medium text-gray-700 mb-2")(
                    "Max Volume Limit"
                ),
                d.Input(
                    type="range",
                    min="0",
                    max="16",
                    value=str(self.config.maxVolumeLimit),
                    classes="w-full",
                    name="maxVolumeLimit",
                    hx_post=f"/devices/{self.device_id}/config",
                    hx_trigger="change",
                    hx_swap="none",
                ),
            ),
        )


def StatusMetric(label: str, value: str):
    """Render a single metric."""
    return d.Div(classes="border-l-4 border-indigo-500 pl-3 py-2")(
        d.P(classes="text-xs text-gray-600 font-medium")(label),
        d.P(classes="text-lg font-semibold text-gray-900")(value),
    )
