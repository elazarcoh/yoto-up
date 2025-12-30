"""
Devices router.
"""

from datetime import time as dt_time
from typing import Annotated, Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from loguru import logger
from pydantic import BaseModel

from yoto_up.yoto_api_client import DAYS, ConfigAlarms, DeviceConfig, DeviceConfigUpdate
from yoto_up_server.dependencies import MqttServiceDep, YotoClientDep
from yoto_up_server.templates.alarms import AlarmCard
from yoto_up_server.templates.base import render_page, render_partial
from yoto_up_server.templates.device_detail import DeviceDetailPage
from yoto_up_server.templates.devices import DevicesPage
from yoto_up_server.templates.upload_components import JsonDisplayModalPartial

router = APIRouter(tags=["devices"])


@router.get("/", response_class=HTMLResponse)
async def devices_page(request: Request, yoto_client: YotoClientDep) -> str:
    """Render the devices page."""
    devices = await yoto_client.get_devices()
    return render_page(
        title="Devices - Yoto Up",
        content=DevicesPage(devices=devices),
        request=request,
    )


@router.get("/list", response_class=HTMLResponse)
async def list_devices(request: Request, yoto_client: YotoClientDep) -> str:
    """Return the device list partial (for refresh)."""
    devices = await yoto_client.get_devices()
    return render_partial(DevicesPage(devices=devices))


@router.get("/{device_id}", response_class=HTMLResponse)
async def device_detail(
    request: Request, device_id: str, yoto_client: YotoClientDep
) -> str:
    """Render device detail page."""
    devices = await yoto_client.get_devices()
    device = next((d for d in devices if d.deviceId == device_id), None)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    status = await yoto_client.get_device_status(device_id)
    config = await yoto_client.get_device_config(device_id)

    return render_page(
        title=f"{device.name} - Yoto Up",
        content=DeviceDetailPage(device=device, status=status, config=config),
        request=request,
    )


# ============================================================================
# Playback Controls (via MQTT)
# ============================================================================


@router.post("/{device_id}/playback/play", response_class=HTMLResponse)
async def play_card(
    device_id: str,
    card_id: Annotated[str, Form()],
    yoto_client: YotoClientDep,
    mqtt_service: MqttServiceDep,
    chapter: Optional[int] = Form(None),
    track: Optional[int] = Form(None),
    seconds: Optional[int] = Form(0),
) -> str:
    """Play a card via MQTT."""
    try:
        await mqtt_service.play_card(device_id, card_id, chapter, track, seconds)
    except RuntimeError as e:
        logger.warning(f"MQTT not connected: {e}, skipping playback command")
    return ""


@router.post("/{device_id}/playback/pause", response_class=HTMLResponse)
async def pause_player(
    device_id: str,
    yoto_client: YotoClientDep,
    mqtt_service: MqttServiceDep,
) -> str:
    """Pause playback via MQTT."""
    try:
        await mqtt_service.pause_player(device_id)
    except RuntimeError as e:
        logger.warning(f"MQTT not connected: {e}, skipping pause command")
    return ""


@router.post("/{device_id}/playback/resume", response_class=HTMLResponse)
async def resume_player(
    device_id: str,
    yoto_client: YotoClientDep,
    mqtt_service: MqttServiceDep,
) -> str:
    """Resume playback via MQTT."""
    try:
        await mqtt_service.resume_player(device_id)
    except RuntimeError as e:
        logger.warning(f"MQTT not connected: {e}, skipping resume command")
    return ""


@router.post("/{device_id}/playback/stop", response_class=HTMLResponse)
async def stop_player(
    device_id: str,
    yoto_client: YotoClientDep,
    mqtt_service: MqttServiceDep,
) -> str:
    """Stop playback via MQTT."""
    try:
        await mqtt_service.stop_player(device_id)
    except RuntimeError as e:
        logger.warning(f"MQTT not connected: {e}, skipping stop command")
    return ""


@router.post("/{device_id}/playback/next", response_class=HTMLResponse)
async def next_track(
    device_id: str,
    yoto_client: YotoClientDep,
    mqtt_service: MqttServiceDep,
) -> str:
    """Next track via MQTT."""
    try:
        await mqtt_service.next_track(device_id)
    except RuntimeError as e:
        logger.warning(f"MQTT not connected: {e}, skipping next command")
    return ""


@router.post("/{device_id}/playback/previous", response_class=HTMLResponse)
async def previous_track(
    device_id: str,
    yoto_client: YotoClientDep,
    mqtt_service: MqttServiceDep,
) -> str:
    """Previous track via MQTT."""
    try:
        await mqtt_service.previous_track(device_id)
    except RuntimeError as e:
        logger.warning(f"MQTT not connected: {e}, skipping previous command")
    return ""


@router.post("/{device_id}/volume", response_class=HTMLResponse)
async def set_volume(
    device_id: str,
    volume: Annotated[int, Form()],
    yoto_client: YotoClientDep,
    mqtt_service: MqttServiceDep,
) -> str:
    """Set volume via MQTT."""
    try:
        await mqtt_service.set_volume(device_id, volume)
    except (RuntimeError, ValueError) as e:
        logger.warning(f"Volume command failed: {e}")
    return ""


def _update_from_current_config(
    current_config: DeviceConfig,
) -> DeviceConfigUpdate:
    return DeviceConfigUpdate(
        name=current_config.device.name,
        config=DeviceConfigUpdate.UpdateConfig(
            locale=current_config.device.config.locale,
            bluetooth_enabled=current_config.device.config.bluetooth_enabled,
            repeat_all=current_config.device.config.repeat_all,
            show_diagnostics=current_config.device.config.show_diagnostics,
            bt_headphones_enabled=current_config.device.config.bt_headphones_enabled,
            pause_volume_down=current_config.device.config.pause_volume_down,
            pause_power_button=current_config.device.config.pause_power_button,
            display_dim_timeout=current_config.device.config.display_dim_timeout,
            shutdown_timeout=current_config.device.config.shutdown_timeout,
            headphones_volume_limited=current_config.device.config.headphones_volume_limited,
            day_time=current_config.device.config.day_time,
            max_volume_limit=current_config.device.config.max_volume_limit,
            ambient_colour=current_config.device.config.ambient_colour,
            day_display_brightness=current_config.device.config.day_display_brightness,
            day_yoto_daily=current_config.device.config.day_yoto_daily,
            day_yoto_radio=current_config.device.config.day_yoto_radio,
            day_sounds_off=current_config.device.config.day_sounds_off,
            night_time=current_config.device.config.night_time,
            night_max_volume_limit=current_config.device.config.night_max_volume_limit,
            night_ambient_colour=current_config.device.config.night_ambient_colour,
            night_display_brightness=current_config.device.config.night_display_brightness,
            night_yoto_daily=current_config.device.config.night_yoto_daily,
            night_yoto_radio=current_config.device.config.night_yoto_radio,
            night_sounds_off=current_config.device.config.night_sounds_off,
            hour_format=current_config.device.config.hour_format,
            display_dim_brightness=current_config.device.config.display_dim_brightness,
            system_volume=current_config.device.config.system_volume,
            volume_level=current_config.device.config.volume_level,
            clock_face=current_config.device.config.clock_face,
            log_level=current_config.device.config.log_level,
            alarms=[alarm.encode() for alarm in current_config.device.config.alarms],
        ),
    )


@router.post("/{device_id}/config", response_class=HTMLResponse)
async def update_config(
    device_id: str,
    yoto_client: YotoClientDep,
    request: Request,
) -> str:
    """Update device config via REST API."""
    # Get form data
    form_data = await request.form()

    # Fetch current config first
    current = await yoto_client.get_device_config(device_id)

    # Merge updates from form
    current_config = current.device.config
    new_config = current_config.model_copy(
        update={
            k: form_data[k]
            for k in form_data.keys()
            if k in current_config.model_fields_set
        }
    )
    current.device.config = new_config
    update = _update_from_current_config(current)

    # Create new config
    await yoto_client.update_device_config(device_id, update)

    return ""


# ============================================================================
# Alarm Management
# ============================================================================


@router.post("/{device_id}/alarms", response_class=HTMLResponse)
async def create_alarm(
    device_id: str,
    yoto_client: YotoClientDep,
) -> str:
    """Create a new alarm."""

    # Fetch current config
    current_config = await yoto_client.get_device_config(device_id)
    devices = await yoto_client.get_devices()
    device = next((d for d in devices if d.deviceId == device_id), None)
    name = device.name if device else "Yoto Player"

    # Create new alarm
    new_alarm = ConfigAlarms(
        weekdays={
            day: False
            for day in [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
        },
        time=dt_time(9, 0),
        tone_id=None,
        volume_level="3",
        is_enabled=True,
    )

    # Add to alarms list
    config_dict = current_config.device.config.model_dump(
        by_alias=True, exclude_none=True
    )
    alarms = config_dict.get("alarms", [])
    alarm_index = len(alarms)

    # Update config
    config_dict["alarms"] = alarms + [new_alarm.model_dump(by_alias=True)]
    new_config = DeviceConfig(**config_dict)
    await yoto_client.update_device_config(device_id, name, new_config)

    return render_partial(
        AlarmCard(alarm=new_alarm, alarm_index=alarm_index, device_id=device_id)
    )


@router.delete("/{device_id}/alarms/{alarm_index}", response_class=HTMLResponse)
async def delete_alarm(
    device_id: str,
    alarm_index: int,
    yoto_client: YotoClientDep,
) -> str:
    """Delete an alarm."""
    # Fetch current config
    current_config = await yoto_client.get_device_config(device_id)

    # Remove alarm
    alarms = current_config.device.config.alarms

    if 0 <= alarm_index < len(alarms):
        alarms.pop(alarm_index)
        current_config.device.config.alarms = alarms
        update = _update_from_current_config(current_config)
        await yoto_client.update_device_config(device_id, update)

    return ""


class UpdateForm(BaseModel):
    is_enabled: bool | None = None
    time: dt_time | None = None
    tone_id: Optional[str] = None
    volume_level: str | None = None
    # weekdays
    monday: bool | None = None
    tuesday: bool | None = None
    wednesday: bool | None = None
    thursday: bool | None = None
    friday: bool | None = None
    saturday: bool | None = None
    sunday: bool | None = None


@router.patch("/{device_id}/alarms/{alarm_index}", response_class=HTMLResponse)
async def update_alarm(
    device_id: str,
    alarm_index: int,
    yoto_client: YotoClientDep,
    request: Request,
    form_data: Annotated[UpdateForm, Form()],
) -> str:
    """Update an alarm and return updated card with saved state."""
    from yoto_up_server.templates.alarms import AlarmCard

    # Fetch current config
    current_config = await yoto_client.get_device_config(device_id)

    # Update alarm
    alarms = current_config.device.config.alarms

    if 0 <= alarm_index < len(alarms):
        alarm = alarms[alarm_index]
        updated_alarm = alarm.model_copy(
            update={
                k: v
                for k, v in form_data.model_dump(exclude_unset=True).items()
                if k in alarm.model_fields_set
            }
        )
        # update weekdays
        for day in DAYS:
            if (val := getattr(form_data, day)) is not None:
                updated_alarm.weekdays[day] = val
        alarms[alarm_index] = updated_alarm
        current_config.device.config.alarms = alarms
        update = _update_from_current_config(current_config)
        await yoto_client.update_device_config(device_id, update)

        # Return the updated alarm card with saved indication
        return render_partial(
            AlarmCard(
                alarm=updated_alarm,
                alarm_index=alarm_index,
                device_id=device_id,
                just_saved=True,
            )
        )

    return ""


# ============================================================================
# JSON Display Modals
# ============================================================================


@router.get("/{device_id}/status-json-modal", response_class=HTMLResponse)
async def get_status_json_modal(
    device_id: str,
    yoto_client: YotoClientDep,
) -> str:
    """Get JSON display modal with device status data."""
    try:
        status = await yoto_client.get_device_status(device_id)
        json_string = status.model_dump_json(indent=2)
        return render_partial(JsonDisplayModalPartial(json_data=json_string))
    except Exception as e:
        logger.error(f"Failed to get status JSON modal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{device_id}/config-json-modal", response_class=HTMLResponse)
async def get_config_json_modal(
    device_id: str,
    yoto_client: YotoClientDep,
) -> str:
    """Get JSON display modal with device config data."""
    try:
        config = await yoto_client.get_device_config(device_id)
        json_string = config.model_dump_json(indent=2)
        return render_partial(JsonDisplayModalPartial(json_data=json_string))
    except Exception as e:
        logger.error(f"Failed to get config JSON modal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
