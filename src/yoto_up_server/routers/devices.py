"""
Devices router.
"""

import json
from typing import Annotated, Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from loguru import logger

from yoto_up.models import DeviceConfig
from yoto_up_server.dependencies import MqttServiceDep, YotoClientDep
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


@router.post("/{device_id}/config", response_class=HTMLResponse)
async def update_config(
    device_id: str,
    yoto_client: YotoClientDep,
    dayDisplayBrightness: Optional[int] = Form(None),
    nightDisplayBrightness: Optional[int] = Form(None),
    maxVolumeLimit: Optional[int] = Form(None),
) -> str:
    """Update device config via REST API."""
    # Fetch current config first
    current_config = await yoto_client.get_device_config(device_id)
    devices = await yoto_client.get_devices()
    device = next((d for d in devices if d.deviceId == device_id), None)
    name = device.name if device else "Yoto Player"

    # Merge updates
    config_dict = current_config.model_dump(exclude_none=True)
    if dayDisplayBrightness is not None:
        config_dict["dayDisplayBrightness"] = dayDisplayBrightness
    if nightDisplayBrightness is not None:
        config_dict["nightDisplayBrightness"] = nightDisplayBrightness
    if maxVolumeLimit is not None:
        config_dict["maxVolumeLimit"] = maxVolumeLimit

    new_config = DeviceConfig(**config_dict)
    await yoto_client.update_device_config(device_id, name, new_config)
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
