"""
Device Detail templates.
"""

from pydom import Component
from pydom import html as d
from yoto_up.yoto_api_client import DeviceConfig, DeviceStatus, Device
from yoto_up_server.utils.alpine import xbind, xon, xdata, xshow
from yoto_up_server.templates.config_components import (
    ConfigSection,
    SliderSetting,
    ToggleSetting,
    SelectSetting,
    TimeSetting,
    ColorPickerSetting,
)
from yoto_up_server.templates.alarms import AlarmsSection


class AlarmsPanel(Component):
    """Alarms configuration UI."""

    def __init__(self, *, device_id: str, config: DeviceConfig):
        self.device_id = device_id
        self.config = config
        self.cfg = config.device.config

    def render(self):
        return d.Div(classes="space-y-8")(
            AlarmsSection(
                device_id=self.device_id,
                alarms=self.cfg.alarms,
            ),
        )


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
                    d.A(
                        href="#",
                        classes="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm cursor-pointer",
                        **xbind().classes(
                            "{ 'border-indigo-500 text-indigo-600': tab === 'alarms', 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300': tab !== 'alarms' }"
                        ),
                        **xon().click.prevent("tab = 'alarms'"),
                    )("Alarms"),
                )
            ),
            # Tab Content
            d.Div(**xshow("tab === 'control'"))(
                PlaybackControlPanel(device_id=self.device.deviceId, status=self.status)
            ),
            d.Div(**xshow("tab === 'settings'"))(
                SettingsPanel(device_id=self.device.deviceId, config=self.config)
            ),
            d.Div(**xshow("tab === 'alarms'"))(
                AlarmsPanel(device_id=self.device.deviceId, config=self.config)
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
                d.H3(classes="text-lg font-semibold text-gray-900")("Playback Control"),
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
    """Settings UI with comprehensive configuration options."""

    def __init__(self, *, device_id: str, config: DeviceConfig):
        self.device_id = device_id
        self.config = config
        self.cfg = config.device.config

    def render(self):
        return d.Div(classes="space-y-8")(
            # Display Settings Section
            ConfigSection(
                title="Display Settings",
                description="Control brightness and display behavior",
            )
            .add_child(
                SliderSetting(
                    label="Day Brightness",
                    name="day_display_brightness",
                    value=self.cfg.day_display_brightness,
                    min_val=0,
                    max_val=100,
                    device_id=self.device_id,
                    help_text="Brightness level during daytime",
                )
            )
            .add_child(
                SliderSetting(
                    label="Night Brightness",
                    name="night_display_brightness",
                    value=self.cfg.night_display_brightness,
                    min_val=0,
                    max_val=100,
                    device_id=self.device_id,
                    help_text="Brightness level during nighttime",
                )
            )
            .add_child(
                SliderSetting(
                    label="Dim Brightness",
                    name="display_dim_brightness",
                    value=self.cfg.display_dim_brightness,
                    min_val=0,
                    max_val=100,
                    device_id=self.device_id,
                    help_text="Brightness when display dims",
                )
            )
            .add_child(
                SelectSetting(
                    label="Dim Timeout",
                    name="display_dim_timeout",
                    value=self.cfg.display_dim_timeout,
                    options={
                        "30": "30 seconds",
                        "60": "1 minute",
                        "300": "5 minutes",
                        "600": "10 minutes",
                        "1800": "30 minutes",
                        "3600": "1 hour",
                        "0": "Never",
                    },
                    device_id=self.device_id,
                    help_text="Time before display dims",
                )
            )
            .add_child(
                SelectSetting(
                    label="Clock Face",
                    name="clock_face",
                    value=self.cfg.clock_face,
                    options={
                        "0": "Analog",
                        "1": "Digital",
                        "2": "Minimal",
                    },
                    device_id=self.device_id,
                    help_text="Clock display style",
                )
            )
            .add_child(
                SelectSetting(
                    label="Hour Format",
                    name="hour_format",
                    value=self.cfg.hour_format,
                    options={
                        "12": "12-hour (AM/PM)",
                        "24": "24-hour",
                    },
                    device_id=self.device_id,
                )
            )
            .add_child(
                ColorPickerSetting(
                    label="Day Ambient Colour",
                    name="ambient_colour",
                    value=self.cfg.ambient_colour,
                    device_id=self.device_id,
                    help_text="Background color during day",
                )
            )
            .add_child(
                ColorPickerSetting(
                    label="Night Ambient Colour",
                    name="night_ambient_colour",
                    value=self.cfg.night_ambient_colour,
                    device_id=self.device_id,
                    help_text="Background color at night",
                )
            ),
            # Volume Settings Section
            ConfigSection(
                title="Volume & Audio",
                description="Control volume levels and audio behavior",
            )
            .add_child(
                SliderSetting(
                    label="Max Volume Limit (Day)",
                    name="max_volume_limit",
                    value=self.cfg.max_volume_limit,
                    min_val=0,
                    max_val=16,
                    device_id=self.device_id,
                    help_text="Maximum volume allowed during day",
                )
            )
            .add_child(
                SliderSetting(
                    label="Max Volume Limit (Night)",
                    name="night_max_volume_limit",
                    value=self.cfg.night_max_volume_limit,
                    min_val=0,
                    max_val=16,
                    device_id=self.device_id,
                    help_text="Maximum volume allowed at night",
                )
            )
            .add_child(
                SliderSetting(
                    label="System Volume",
                    name="system_volume",
                    value=self.cfg.system_volume,
                    min_val=0,
                    max_val=100,
                    device_id=self.device_id,
                    help_text="Overall system volume",
                )
            )
            .add_child(
                ToggleSetting(
                    label="Bluetooth Enabled",
                    name="bluetooth_enabled",
                    value=self.cfg.bluetooth_enabled == "true",
                    device_id=self.device_id,
                    help_text="Allow Bluetooth connections",
                )
            )
            .add_child(
                ToggleSetting(
                    label="Bluetooth Headphones Limited",
                    name="headphones_volume_limited",
                    value=self.cfg.headphones_volume_limited,
                    device_id=self.device_id,
                    help_text="Limit volume for headphones",
                )
            )
            .add_child(
                ToggleSetting(
                    label="Bluetooth Headphones Enabled",
                    name="bt_headphones_enabled",
                    value=self.cfg.bt_headphones_enabled,
                    device_id=self.device_id,
                    help_text="Enable Bluetooth headphone support",
                )
            ),
            # Time Schedule Section
            ConfigSection(
                title="Time Schedule",
                description="Set day and night time boundaries",
            )
            .add_child(
                TimeSetting(
                    label="Day Start Time",
                    name="day_time",
                    value=self.cfg.day_time,
                    device_id=self.device_id,
                    help_text="When daytime settings become active",
                )
            )
            .add_child(
                TimeSetting(
                    label="Night Start Time",
                    name="night_time",
                    value=self.cfg.night_time,
                    device_id=self.device_id,
                    help_text="When nighttime settings become active",
                )
            ),
            # Controls Section
            ConfigSection(
                title="Controls",
                description="Configure button and control behavior",
            )
            .add_child(
                ToggleSetting(
                    label="Pause with Volume Down",
                    name="pause_volume_down",
                    value=self.cfg.pause_volume_down,
                    device_id=self.device_id,
                    help_text="Pressing volume down will pause playback",
                )
            )
            .add_child(
                ToggleSetting(
                    label="Pause with Power Button",
                    name="pause_power_button",
                    value=self.cfg.pause_power_button,
                    device_id=self.device_id,
                    help_text="Pressing power button will pause playback",
                )
            )
            .add_child(
                SelectSetting(
                    label="Shutdown Timeout",
                    name="shutdown_timeout",
                    value=self.cfg.shutdown_timeout,
                    options={
                        "300": "5 minutes",
                        "600": "10 minutes",
                        "900": "15 minutes",
                        "1800": "30 minutes",
                        "3600": "1 hour",
                        "7200": "2 hours",
                        "0": "Never",
                    },
                    device_id=self.device_id,
                    help_text="Auto-shutdown after inactivity",
                )
            ),
            # Content Settings Section
            ConfigSection(
                title="Content Settings",
                description="Control available content and features",
            )
            .add_child(
                ToggleSetting(
                    label="Repeat All",
                    name="repeat_all",
                    value=self.cfg.repeat_all,
                    device_id=self.device_id,
                    help_text="Always repeat content when finished",
                )
            )
            .add_child(
                ToggleSetting(
                    label="Show Diagnostics",
                    name="show_diagnostics",
                    value=self.cfg.show_diagnostics,
                    device_id=self.device_id,
                    help_text="Show diagnostic information on device",
                )
            )
            .add_child(
                SelectSetting(
                    label="Log Level",
                    name="log_level",
                    value=self.cfg.log_level,
                    options={
                        "0": "None",
                        "1": "Error",
                        "2": "Warning",
                        "3": "Info",
                        "4": "Debug",
                    },
                    device_id=self.device_id,
                    help_text="Device logging verbosity",
                )
            ),
        )


def StatusMetric(label: str, value: str):
    """Render a single metric."""
    return d.Div(classes="border-l-4 border-indigo-500 pl-3 py-2")(
        d.P(classes="text-xs text-gray-600 font-medium")(label),
        d.P(classes="text-lg font-semibold text-gray-900")(value),
    )
