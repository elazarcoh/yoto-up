"""
MQTT Service for real-time device control and updates.

This service handles the connection to the Yoto MQTT broker for sending
device commands and receiving real-time status updates from players.

Note: This is a placeholder implementation. The actual MQTT connection logic
requires obtaining MQTT credentials from the Yoto API, which is currently
handled by the closed-source `yoto_api` library in Home Assistant.

MQTT Topics:
- yoto/devices/{device_id}/commands - Commands sent to devices (play, pause, volume, etc.)
- yoto/devices/{device_id}/state - State updates received from devices
"""

import json
from typing import Any, Callable, Dict, Optional

from loguru import logger
import aiomqtt

from yoto_web_server.services.session_aware_api_service import SessionAwareApiService


class MqttService:
    """Service for handling MQTT connections and device control via MQTT."""

    def __init__(self, api_service: SessionAwareApiService):
        self.api_service = api_service
        self.client: Optional[aiomqtt.Client] = None
        self._running = False
        self._callbacks: Dict[str, Callable] = {}
        self._broker: str = "mqtt.yotoplay.com"  # TODO: Get from API
        self._port: int = 1883

    async def start(self):
        """Start the MQTT service and connect to broker."""
        if self._running:
            return

        self._running = True
        # TODO: Implement MQTT connection logic
        # 1. Get MQTT credentials from API (endpoint unknown)
        # 2. Connect to broker with credentials
        # 3. Subscribe to device state topics
        logger.info("MQTT Service started (Placeholder - awaiting credential endpoint)")

    async def stop(self):
        """Stop the MQTT service."""
        self._running = False
        if self.client:
            try:
                # aiomqtt client uses async context manager, not explicit disconnect
                pass
            except Exception as e:
                logger.error(f"Error disconnecting MQTT: {e}")
        logger.info("MQTT Service stopped")

    def subscribe(self, topic: str, callback: Callable):
        """Subscribe to a topic for state updates."""
        self._callbacks[topic] = callback

    async def _publish_command(self, device_id: str, command: str, payload: Dict[str, Any]):
        """
        Publish a command to a device via MQTT.

        Args:
            device_id: Device ID
            command: Command name (play, pause, volume, etc.)
            payload: Command payload
        """
        if not self._running or not self.client:
            raise RuntimeError("MQTT service not connected")

        topic = f"yoto/devices/{device_id}/commands"
        message = {
            "command": command,
            "payload": payload,
        }

        try:
            await self.client.publish(topic, json.dumps(message))
            logger.debug(f"Published {command} to {device_id}: {payload}")
        except Exception as e:
            logger.error(f"Error publishing MQTT command: {e}")
            raise

    # ========================================================================
    # Device Control Commands (via MQTT)
    # ========================================================================

    async def play_card(
        self,
        device_id: str,
        card_id: str,
        chapter_index: Optional[int] = None,
        track_index: Optional[int] = None,
        seconds: Optional[int] = 0,
    ) -> None:
        """
        Play a card on a device via MQTT.

        Args:
            device_id: Device ID
            card_id: Card ID to play
            chapter_index: Optional chapter index (0-based)
            track_index: Optional track index (0-based)
            seconds: Start position in seconds
        """
        payload = {
            "cardId": card_id,
            "seconds": seconds or 0,
        }
        if chapter_index is not None:
            payload["chapter"] = chapter_index
        if track_index is not None:
            payload["track"] = track_index

        await self._publish_command(device_id, "play", payload)

    async def pause_player(self, device_id: str) -> None:
        """Pause playback on device via MQTT."""
        await self._publish_command(device_id, "pause", {})

    async def resume_player(self, device_id: str) -> None:
        """Resume playback on device via MQTT."""
        await self._publish_command(device_id, "resume", {})

    async def stop_player(self, device_id: str) -> None:
        """Stop playback on device via MQTT."""
        await self._publish_command(device_id, "stop", {})

    async def next_track(self, device_id: str) -> None:
        """Skip to next track via MQTT."""
        await self._publish_command(device_id, "next", {})

    async def previous_track(self, device_id: str) -> None:
        """Skip to previous track via MQTT."""
        await self._publish_command(device_id, "previous", {})

    async def set_volume(self, device_id: str, volume: int) -> None:
        """
        Set device volume via MQTT.

        Args:
            device_id: Device ID
            volume: Volume level (0-16)
        """
        if not 0 <= volume <= 16:
            raise ValueError(f"Volume must be 0-16, got {volume}")
        await self._publish_command(device_id, "volume", {"volume": volume})

    async def set_sleep_timer(self, device_id: str, seconds: int) -> None:
        """
        Set sleep timer via MQTT.

        Args:
            device_id: Device ID
            seconds: Seconds until sleep (0 to disable)
        """
        if seconds < 0:
            raise ValueError(f"Sleep timer must be >= 0, got {seconds}")
        await self._publish_command(device_id, "sleep", {"seconds": seconds})

    async def _handle_message(self, message: aiomqtt.Message):
        """Handle incoming MQTT state messages."""
        topic = str(message.topic)
        payload = message.payload

        logger.debug(f"Received MQTT message on {topic}")

        if topic in self._callbacks:
            try:
                if isinstance(payload, (bytes, bytearray)):
                    data = json.loads(payload.decode("utf-8"))
                else:
                    data = json.loads(str(payload))
                await self._callbacks[topic](data)
            except Exception as e:
                logger.error(f"Error handling MQTT message: {e}")
