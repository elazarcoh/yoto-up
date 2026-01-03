"""
Reusable configuration components for device settings.

These components handle different types of configuration inputs:
- Sliders for numeric values
- Toggles for boolean values
- Dropdowns for select values
- Time pickers for time values
- Sections for grouping related settings
"""

from typing import Any, Optional
from pydom import Component
from pydom import html as d


class ConfigSection(Component):
    """A section grouping related configuration settings."""

    def __init__(self, *, title: str, description: Optional[str] = None):
        self.title = title
        self.description = description
        self.children = []

    def add_child(self, child: Component) -> "ConfigSection":
        """Add a child component to this section."""
        self.children.append(child)
        return self

    def render(self):
        return d.Div(classes="mb-8")(
            d.Div(classes="mb-4")(
                d.H3(classes="text-lg font-semibold text-gray-900")(self.title),
                d.P(classes="text-sm text-gray-600 mt-1")(self.description or "")
                if self.description
                else None,
            ),
            d.Div(classes="bg-white rounded-lg shadow divide-y divide-gray-200")(*self.children),
        )


class SliderSetting(Component):
    """A slider control for numeric configuration values."""

    def __init__(
        self,
        *,
        label: str,
        name: str,
        value: int | str,
        min_val: int = 0,
        max_val: int = 100,
        step: int = 1,
        device_id: str,
        show_value: bool = True,
        help_text: Optional[str] = None,
    ):
        self.label = label
        self.name = name
        self.value = int(value) if isinstance(value, str) else value
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.device_id = device_id
        self.show_value = show_value
        self.help_text = help_text

    def render(self):
        return d.Div(classes="px-6 py-4 hover:bg-gray-50 transition-colors")(
            d.Div(classes="flex justify-between items-start mb-2")(
                d.Div()(
                    d.Label(classes="text-sm font-medium text-gray-700")(self.label),
                    d.P(classes="text-xs text-gray-500 mt-1")(self.help_text)
                    if self.help_text
                    else None,
                ),
                d.Span(
                    classes="inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium bg-indigo-100 text-indigo-800"
                )(str(self.value))
                if self.show_value
                else None,
            ),
            d.Input(
                type="range",
                name=self.name,
                min=str(self.min_val),
                max=str(self.max_val),
                step=str(self.step),
                value=str(self.value),
                classes="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600",
                hx_post=f"/devices/{self.device_id}/config",
                hx_trigger="change",
                hx_swap="none",
            ),
        )


class ToggleSetting(Component):
    """A toggle switch for boolean configuration values."""

    def __init__(
        self,
        *,
        label: str,
        name: str,
        value: bool,
        device_id: str,
        help_text: Optional[str] = None,
    ):
        self.label = label
        self.name = name
        self.value = value
        self.device_id = device_id
        self.help_text = help_text

    def render(self):
        return d.Div(classes="px-6 py-4 hover:bg-gray-50 transition-colors")(
            d.Div(classes="flex justify-between items-center")(
                d.Div()(
                    d.Label(classes="text-sm font-medium text-gray-700")(self.label),
                    d.P(classes="text-xs text-gray-500 mt-1")(self.help_text)
                    if self.help_text
                    else None,
                ),
                d.Button(
                    type="button",
                    classes=f"relative inline-flex flex-shrink-0 h-6 w-11 border-2 border-transparent rounded-full cursor-pointer transition-colors ease-in-out duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 "
                    f"{'bg-indigo-600' if self.value else 'bg-gray-200'}",
                    hx_post=f"/devices/{self.device_id}/config",
                    hx_vals=f'{{"' + self.name + f'": {str(self.value).lower()}}}',
                    hx_trigger="click",
                    hx_swap="none",
                )(
                    d.Span(
                        aria_hidden="true",
                        classes=f"pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transform ring-0 transition ease-in-out duration-200 "
                        f"{'translate-x-5' if self.value else 'translate-x-0'}",
                    )()
                ),
            ),
        )


class SelectSetting(Component):
    """A dropdown select control for configuration values."""

    def __init__(
        self,
        *,
        label: str,
        name: str,
        value: str,
        options: dict[str, str],
        device_id: str,
        help_text: Optional[str] = None,
    ):
        self.label = label
        self.name = name
        self.value = value
        self.options = options
        self.device_id = device_id
        self.help_text = help_text

    def render(self):
        return d.Div(classes="px-6 py-4 hover:bg-gray-50 transition-colors")(
            d.Div()(
                d.Label(
                    htmlFor=self.name,
                    classes="text-sm font-medium text-gray-700",
                )(self.label),
                d.P(classes="text-xs text-gray-500 mt-1")(self.help_text)
                if self.help_text
                else None,
                d.Select(
                    id=self.name,
                    name=self.name,
                    value=self.value,
                    classes="mt-2 block w-full rounded-md border border-gray-300 shadow-sm py-2 px-3 focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    hx_post=f"/devices/{self.device_id}/config",
                    hx_trigger="change",
                    hx_swap="none",
                )(*[d.Option(value=k)(v) for k, v in self.options.items()]),
            ),
        )


class TimeSetting(Component):
    """A time picker for time configuration values."""

    def __init__(
        self,
        *,
        label: str,
        name: str,
        value: str,
        device_id: str,
        help_text: Optional[str] = None,
    ):
        self.label = label
        self.name = name
        self.value = value  # Format: "HH:MM"
        self.device_id = device_id
        self.help_text = help_text

    def render(self):
        return d.Div(classes="px-6 py-4 hover:bg-gray-50 transition-colors")(
            d.Div()(
                d.Label(
                    htmlFor=self.name,
                    classes="text-sm font-medium text-gray-700",
                )(self.label),
                d.P(classes="text-xs text-gray-500 mt-1")(self.help_text)
                if self.help_text
                else None,
                d.Input(
                    type="time",
                    id=self.name,
                    name=self.name,
                    value=self.value,
                    classes="mt-2 block w-full rounded-md border border-gray-300 shadow-sm py-2 px-3 focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    hx_post=f"/devices/{self.device_id}/config",
                    hx_trigger="change",
                    hx_swap="none",
                ),
            ),
        )


class ColorPickerSetting(Component):
    """A color picker for ambient color configuration."""

    def __init__(
        self,
        *,
        label: str,
        name: str,
        value: str,
        device_id: str,
        help_text: Optional[str] = None,
    ):
        self.label = label
        self.name = name
        self.value = value  # Hex color code
        self.device_id = device_id
        self.help_text = help_text

    def render(self):
        return d.Div(classes="px-6 py-4 hover:bg-gray-50 transition-colors")(
            d.Div()(
                d.Label(
                    htmlFor=self.name,
                    classes="text-sm font-medium text-gray-700",
                )(self.label),
                d.P(classes="text-xs text-gray-500 mt-1")(self.help_text)
                if self.help_text
                else None,
                d.Div(classes="mt-2 flex items-center gap-3")(
                    d.Input(
                        type="color",
                        id=self.name,
                        name=self.name,
                        value=self.value,
                        classes="h-10 w-14 rounded-md border border-gray-300 cursor-pointer",
                        hx_post=f"/devices/{self.device_id}/config",
                        hx_trigger="change",
                        hx_swap="none",
                    ),
                    d.Code(classes="text-sm text-gray-600")(self.value),
                ),
            ),
        )


class TabGroup(Component):
    """A tab group for organizing configuration sections."""

    def __init__(self, *, tabs: dict[str, Component]):
        self.tabs = tabs
        self.tab_names = list(tabs.keys())

    def render(self):
        return d.Div(**{"x-data": "{activeTab: 'general'}", ":class": "{}"})(
            # Tab buttons
            d.Div(classes="border-b border-gray-200 mb-6")(
                d.Nav(classes="-mb-px flex space-x-8")(
                    *[
                        d.Button(
                            type="button",
                            classes=f"whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm cursor-pointer transition-colors "
                            f"{'border-indigo-500 text-indigo-600' if i == 0 else 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}",
                            **{
                                "@click": f"activeTab = '{tab_name}'",
                                ":class": f"{{active: activeTab === '{tab_name}' }}",
                            },
                        )(tab_name.replace("_", " ").title())
                        for i, tab_name in enumerate(self.tab_names)
                    ]
                )
            ),
            # Tab content
            *[
                d.Div(
                    **{":hidden": f"activeTab !== '{tab_name}'"},
                    classes="transition-opacity duration-200",
                )(content)
                for tab_name, content in self.tabs.items()
            ],
        )
