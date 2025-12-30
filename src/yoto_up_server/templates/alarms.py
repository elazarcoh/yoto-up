"""
Alarm management components for device configuration.
"""

from datetime import time as dt_time
import json
from typing import Optional
from pydom import Component
from pydom import html as d
from yoto_up.yoto_api_client import ConfigAlarms, Day, DAYS
from yoto_up_server.utils.alpine import xdata, xtext, xmodel


class AlarmCard(Component):
    """A card representing a single alarm."""

    def __init__(
        self,
        *,
        alarm: ConfigAlarms,
        alarm_index: int,
        device_id: str,
        just_saved: bool = False,
    ):
        self.alarm = alarm
        self.alarm_index = alarm_index
        self.device_id = device_id
        self.just_saved = just_saved

    def render(self):
        days_str = ", ".join(
            [day.title() for day in DAYS if self.alarm.weekdays.get(day, False)]
        )
        time_str = self.alarm.time.strftime("%H:%M")
        volume_str = (
            str(self.alarm.volume_level)
            if isinstance(self.alarm.volume_level, int)
            else self.alarm.volume_level
        )

        # Card classes with conditional green background if just saved
        card_classes = "bg-white rounded-lg border border-gray-200 shadow hover:shadow-md transition-shadow p-4 mb-3 relative"
        if self.just_saved:
            card_classes += " bg-green-50 htmx-settling"

        return d.Div(
            classes=card_classes,
            data_alarm_index=str(self.alarm_index),
            hx_target="this",
            hx_swap="outerHTML",
            hx_ext="class-tools",
        )(
            # Saved indicator (appears and fades out via CSS animation)
            d.Div(
                id=f"alarm_{self.alarm_index}_saved",
                classes="absolute top-3 right-3 items-center px-3 py-1 rounded-full bg-green-100 border border-green-300 text-green-700 text-sm font-semibold"
                + " transition-opacity"
                + (" inline-flex" if self.just_saved else " hidden"),
                hx_classes="add opacity-0:2s, add hidden, remove inline-flex",
            )(
                d.Span(classes="mr-1")("✓"),
                "Saved",
            ),
            d.Div(classes="flex justify-between items-start mb-3")(
                d.Div()(
                    d.H4(classes="text-lg font-semibold text-gray-900")(
                        f"Alarm {self.alarm_index + 1}"
                    ),
                    d.P(classes="text-sm text-gray-600 mt-1")(
                        f"🕐 {time_str} · {days_str or 'No days selected'}"
                    ),
                ),
                d.Button(
                    type="button",
                    classes="inline-flex items-center px-3 py-1.5 border border-transparent text-sm leading-4 font-medium rounded-md text-red-700 bg-red-50 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-all",
                    hx_delete=f"/devices/{self.device_id}/alarms/{self.alarm_index}",
                    hx_confirm="Are you sure you want to delete this alarm?",
                    hx_swap="outerHTML swap:1s",
                )("Delete"),
            ),
            # Enabled toggle
            d.Div(classes="mb-4 p-3 bg-gray-50 rounded")(
                d.Label(classes="flex items-center cursor-pointer")(
                    d.Input(
                        type="checkbox",
                        name="is_enabled",
                        hx_vals=json.dumps({"is_enabled": not self.alarm.is_enabled}),
                        checked="checked" if self.alarm.is_enabled else None,
                        classes="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
                        hx_patch=f"/devices/{self.device_id}/alarms/{self.alarm_index}",
                    ),
                    d.Span(classes="ml-2 text-sm font-medium text-gray-700")(
                        "Enabled" if self.alarm.is_enabled else "Disabled"
                    ),
                )
            ),
            # Time picker
            d.Div(classes="mb-4")(
                d.Label(
                    htmlFor=f"alarm_{self.alarm_index}_time",
                    classes="block text-sm font-medium text-gray-700 mb-2",
                )("Time"),
                d.Input(
                    type="time",
                    id=f"alarm_{self.alarm_index}_time",
                    name="time",
                    value=time_str,
                    classes="block w-full rounded-md border border-gray-300 shadow-sm py-2 px-3 focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    hx_patch=f"/devices/{self.device_id}/alarms/{self.alarm_index}",
                    hx_trigger="change",
                ),
            ),
            # Days of week
            d.Div(classes="mb-4")(
                d.Label(classes="block text-sm font-medium text-gray-700 mb-2")("Days"),
                d.Div(classes="grid grid-cols-4 gap-2")(
                    *[
                        d.Label(
                            classes="flex items-center cursor-pointer p-2 rounded border "
                            f"{'border-indigo-300 bg-indigo-50' if self.alarm.weekdays.get(day, False) else 'border-gray-300 bg-white'}"
                        )(
                            d.Input(
                                type="checkbox",
                                name=day,
                                hx_vals=json.dumps(
                                    {day: not self.alarm.weekdays.get(day, False)}
                                ),
                                checked="checked"
                                if self.alarm.weekdays.get(day, False)
                                else None,
                                classes="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
                                hx_patch=f"/devices/{self.device_id}/alarms/{self.alarm_index}",
                            ),
                            d.Span(classes="ml-2 text-sm font-medium text-gray-700")(
                                day[:3].title()
                            ),
                        )
                        for day in DAYS
                    ]
                ),
            ),
            # Volume level (slider)
            d.Div(classes="mb-4", **xdata({"volumeLevel": volume_str}))(
                d.Label(
                    htmlFor=f"alarm_{self.alarm_index}_volume",
                    classes="block text-sm font-medium text-gray-700 mb-2",
                )(
                    d.Span()("Volume: "),
                    d.Span(
                        id=f"alarm_{self.alarm_index}_volume_value",
                        classes="font-bold text-indigo-600",
                        **xtext("volumeLevel"),
                    )(volume_str),
                ),
                d.Input(
                    type="range",
                    id=f"alarm_{self.alarm_index}_volume",
                    name="volume_level",
                    min="1",
                    max="16",
                    value=volume_str,
                    **xmodel().debounce(500)("volumeLevel"),
                    classes="block w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600",
                    hx_patch=f"/devices/{self.device_id}/alarms/{self.alarm_index}",
                    hx_trigger="change",
                ),
            ),
            # Tone ID (if supported)
            d.Div(classes="mb-4")(
                d.Label(
                    htmlFor=f"alarm_{self.alarm_index}_tone",
                    classes="block text-sm font-medium text-gray-700 mb-2",
                )("Alarm Tone"),
                d.Input(
                    type="text",
                    id=f"alarm_{self.alarm_index}_tone",
                    name="tone_id",
                    value=self.alarm.tone_id or "",
                    placeholder="Tone ID (if supported)",
                    classes="block w-full rounded-md border border-gray-300 shadow-sm py-2 px-3 focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    hx_patch=f"/devices/{self.device_id}/alarms/{self.alarm_index}",
                    hx_trigger="change",
                ),
            ),
            # Hidden field for weekdays JSON
            d.Input(
                type="hidden",
                name="weekdays",
                value="{}",
                classes="alarm-weekdays-field",
            ),
            # Script to handle day checkbox changes
            d.Script()(self._make_alarm_script()),
            # CSS transitions for saved state
            d.Style()(f"""
                #alarm_{self.alarm_index}_saved {{
                    transition: opacity 0.3s ease, transform 0.3s ease;
                }}
                
                [data-alarm-index="{self.alarm_index}"].htmx-settling {{
                    transition: background-color 0.3s ease;
                }}
                
                [data-alarm-index="{self.alarm_index}"].htmx-settling #alarm_{self.alarm_index}_saved {{
                    animation: fadeOutUp 0.3s ease 2.7s forwards;
                }}
                
                @keyframes fadeOutUp {{
                    from {{
                        opacity: 1;
                        transform: translateY(0);
                    }}
                    to {{
                        opacity: 0;
                        transform: translateY(-10px);
                    }}
                }}
            """),
        )

    def _make_alarm_script(self) -> str:
        """Create inline script for alarm card interactions."""
        return f"""
        (function() {{
            const container = document.currentScript.closest('[data-alarm-index]');
            if (!container) return;
            
            const updateWeekdays = () => {{
                const checkboxes = container.querySelectorAll('input[type="checkbox"]:not([name="is_enabled"])');
                const weekdays = {{}};
                const daysList = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
                
                daysList.forEach(day => {{
                    weekdays[day] = false;
                }});
                
                checkboxes.forEach(cb => {{
                    const day = cb.name;
                    weekdays[day] = cb.checked;
                }});
                
                const weekdaysField = container.querySelector('.alarm-weekdays-field');
                if (weekdaysField) {{
                    weekdaysField.value = JSON.stringify(weekdays);
                }}
                
                // Submit the form
                htmx.ajax('PATCH', '/devices/{self.device_id}/alarms/{self.alarm_index}', {{
                    target: container,
                    swap: 'outerHTML',
                    values: container.querySelectorAll('input, select')
                }});
            }};
            
            container._updateDaysField = updateWeekdays;
            
            const dayCheckboxes = container.querySelectorAll('input[type="checkbox"]:not([name="is_enabled"])');
            dayCheckboxes.forEach(cb => {{
                cb.addEventListener('change', updateWeekdays);
            }});
        }})();
        """


class AlarmsSection(Component):
    """Section for managing all alarms."""

    def __init__(self, *, device_id: str, alarms: list[ConfigAlarms]):
        self.device_id = device_id
        self.alarms = alarms

    def render(self):
        return d.Div()(
            d.Div(classes="mb-6")(
                d.Div(classes="flex justify-between items-center mb-4")(
                    d.Div()(
                        d.H3(classes="text-lg font-semibold text-gray-900")("Alarms"),
                        d.P(classes="text-sm text-gray-600 mt-1")(
                            "Set up alarms to wake your child or remind them of activities"
                        ),
                    ),
                    d.Button(
                        type="button",
                        classes="inline-flex items-center px-4 py-2 border border-transparent text-sm leading-4 font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500",
                        hx_post=f"/devices/{self.device_id}/alarms",
                        hx_target="#alarms-list",
                        hx_swap="beforeend",
                    )("+ Add Alarm"),
                ),
                # Alarms list
                d.Div(id="alarms-list", classes="space-y-3")(
                    *[
                        AlarmCard(
                            alarm=alarm,
                            alarm_index=i,
                            device_id=self.device_id,
                        )
                        for i, alarm in enumerate(self.alarms)
                    ]
                ),
            ),
        )
